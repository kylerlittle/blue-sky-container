#******************************************************************************
#
#  BlueSky Framework - Controls the estimation of emissions, incorporation of
#                      meteorology, and the use of dispersion models to
#                      forecast smoke impacts from fires.
#  Copyright (C) 2003-2006  USDA Forest Service - Pacific Northwest Wildland
#                           Fire Sciences Laboratory
#  BlueSky Framework - Version 3.5.1
#  Copyright (C) 2007-2009  USDA Forest Service - Pacific Northwest Wildland Fire
#                      Sciences Laboratory and Sonoma Technology, Inc.
#                      All rights reserved.
#
# See LICENSE.TXT for the Software License Agreement governing the use of the
# BlueSky Framework - Version 3.5.1.
#
# Contributors to the BlueSky Framework are identified in ACKNOWLEDGEMENTS.TXT
#
#******************************************************************************

_bluesky_version_ = "3.5.1"

from kernel.core import Process
from kernel import location
from kernel.config import config as kernel_config
from kernel.log import corelog, SUMMARY
from kernel.types import construct_type
from kernel.bs_datetime import BSDateTime, utc, timezone_from_str, FixedOffset
from kernel.statuslog import Statuses, Actions
from local_met_information import Sun
from datetime import datetime, timedelta
import mapscript
try:
  from osgeo import ogr, osr
except ImportError:
  import ogr, osr

class FillDefaultData(Process):
    """ Provide defaults for missing input fields """

    def init(self):
        self.declare_input("fires", "FireInformation")
        self.declare_output("fires", "FireInformation")

    def run(self, context):
        fireInfo = self.get_input("fires")
        pre_filtering_counts = self._log_counts(fireInfo)
        fireInfo = self.fillLocationData(fireInfo)
        self.filterFiresByDispersionDomain(fireInfo)
        self.filterFiresByArea(fireInfo)
        fireInfo = self.fillDateTimeTimeZoneData(fireInfo)
        fireInfo = self.fillFireTimeZoneData(fireInfo)
        fireInfo = self.fillTimeData(fireInfo)
        fireInfo = self.fillBurnSpecificData(fireInfo)
        fireInfo = self.fillLocalWeather(fireInfo)
        self.filterEmptyFireEvents(fireInfo)
        self.set_output("fires", fireInfo)
        self._log_counts(fireInfo, pre_filtering_counts=pre_filtering_counts)

    def _log_counts(self, fireInfo, pre_filtering_counts=None):
        counts = {
            "number_of_events": fireInfo.eventsCount(),
            "number_of_locations": fireInfo.locationsCount()
        }
        if pre_filtering_counts:
            counts.update(
                number_of_events_removed=pre_filtering_counts["number_of_events"] - fireInfo.eventsCount(),
                number_of_locations_removed=pre_filtering_counts["number_of_locations"] - fireInfo.locationsCount()
            )

        # post to status log
        note = "{} fire information".format(
            "Filtered" if pre_filtering_counts else "Found")
        extra_fields = dict(notes=note, **counts)
        self._log_status(Statuses.GOOD, Actions.CONTINUE, **extra_fields)

        # write to log file
        self.log.debug("{} filling in fire data: {}".format(
            "After" if pre_filtering_counts else "Before", counts))

        # write to summary.json
        if pre_filtering_counts:
            corelog.log(SUMMARY,{"fire_filtering": {
                "before": {k.replace('number_of_',''):v for k,v in pre_filtering_counts.items()},
                "after": {k.replace('number_of_',''):v for k,v in counts.items()}
            }})

        return counts

    def fillLocalWeather(self, fireInfo):
        for loc in fireInfo.locations():
            if loc.local_weather is None:
                loc.local_weather = construct_type("LocalWeatherData")
            loc.local_weather.setdefault("min_wind", 6)
            loc.local_weather.setdefault("max_wind", 6)
            loc.local_weather.setdefault("min_wind_aloft", 6)
            loc.local_weather.setdefault("max_wind_aloft", 6)
            loc.local_weather.setdefault("min_humid", 40)
            loc.local_weather.setdefault("max_humid", 80)
            loc.local_weather.setdefault("min_temp", 13)
            loc.local_weather.setdefault("max_temp", 30)
            loc.local_weather.setdefault("min_temp_hour", 4)
            loc.local_weather.setdefault("max_temp_hour", 14)
            loc.local_weather.setdefault("snow_month", 5)
            loc.local_weather.setdefault("rain_days", 8)

            # Use NOAA-standard sunrise/sunset calculations
            dt = loc['date_time']
            tz = loc['timezone']
            tmidday = datetime(dt.year, dt.month, dt.day, int(12))
            try:
                s = Sun(lat=float(loc['latitude']), long=float(loc['longitude']))
                sunrise = s.sunrise_hr(tmidday) + tz
                sunset = s.sunset_hr(tmidday) + tz
            except:
                # these calculations can fail near the North/South poles
                sunrise = 6
                sunset = 18

            loc.local_weather.setdefault("sunrise_hour", sunrise)
            loc.local_weather.setdefault("sunset_hour", sunset)
        return fireInfo

    def fillLocationData(self, fireInfo):
        for fireLoc in fireInfo.locations():
            # Set some defaults:
            fireLoc.setdefault("slope", 10)

            if fireLoc["latitude"] is None or fireLoc["longitude"] is None:
                err = '"%s" has no latitude/longitude' % fireLoc
                if self.config("REJECT_INVALID_LOCATIONS", bool):
                    raise AssertionError(err)
                elif self.config("REMOVE_INVALID_LOCATIONS", bool):
                    self.log.warn(err)
                    fireInfo.removeLocation(fireLoc)
                else:
                    fireLoc["elevation"] = 0
                    continue

            if self.config("WESTHEMS", bool):
                if fireLoc["longitude"] > 0:
                    self.log.debug("Positive burn longitude in western hemisphere for %s" % location)
                    fireLoc["longitude"] *= -1
                    self.log.debug("Burn longitude is now negative for %s" % location)

            if fireLoc["state"] is None or fireLoc["state"] is "":
                fireLoc["state"] = location.state(fireLoc["latitude"], fireLoc["longitude"])
                if fireLoc["state"] != "Unknown":
                    fireLoc.setdefault("country", "USA")
                else:
                    fireLoc.setdefault("country", "Unknown")

            if fireLoc["fips"] is None or fireLoc["fips"] is "":
                fireLoc["fips"] = location.fips(fireLoc["latitude"], fireLoc["longitude"])

        return fireInfo

    def filterFiresByDispersionDomain(self, fireInfo):
        count = 0
        if kernel_config.getboolean("DEFAULT", "REMOVE_LOCATIONS_OUTSIDE_DISPERSION_DOMAIN"):
            model_configuration = kernel_config.get("DEFAULT", "DISPERSION")
            if model_configuration:
                if (kernel_config.has_option(model_configuration, "CENTER_LATITUDE") and
                        kernel_config.has_option(model_configuration, "HEIGHT_LATITUDE")):
                    # Note: this code does not support domains that include a pole
                    center_lat = kernel_config.getfloat(model_configuration, "CENTER_LATITUDE")
                    height_lat = kernel_config.getfloat(model_configuration, "HEIGHT_LATITUDE")
                    self.log.info("Filtering fire locations by dispersion domain latitude window -"
                        " center lat %f, height lat %f" % (center_lat, height_lat))
                    lat_radius = height_lat / 2.0
                    for fireLoc in fireInfo.locations():
                        if fireLoc["latitude"] and abs(fireLoc["latitude"] - center_lat) > lat_radius:
                            self.log.info("Filtered out fire location with lat %f" % (fireLoc["latitude"]))
                            count += 1
                            fireInfo.removeLocation(fireLoc)

                if (kernel_config.has_option(model_configuration, "CENTER_LONGITUDE") and
                        kernel_config.has_option(model_configuration, "WIDTH_LONGITUDE")):
                    # Note: this code does not domains that span >= 360
                    # degrees longitude (which should never occur)
                    center_lon = kernel_config.getfloat(model_configuration, "CENTER_LONGITUDE")
                    width_lon = kernel_config.getfloat(model_configuration, "WIDTH_LONGITUDE")
                    self.log.info("Filtering fire locations by dispersion domain longitude window -"
                        " center lon %f, width lon %f" % (center_lon, width_lon))
                    lon_radius = width_lon / 2.0

                    # TODO: this works for anything other than domains that cross GMT.
                    # Update to handle all possible domains (namely those that cross GMT
                    # and/or the international dateline)

                    def adjust_lon(lon):
                        return (lon + 360.0) % 360

                    adjusted_west_lon = adjust_lon(center_lon - lon_radius)
                    adjusted_east_lon = adjust_lon(center_lon + lon_radius)
                    for fireLoc in fireInfo.locations():
                        adjusted_fire_lon = adjust_lon(fireLoc["longitude"])
                        if fireLoc["longitude"] and not adjusted_west_lon <= adjusted_fire_lon <= adjusted_east_lon:
                            self.log.info("Filtered out fire location with lon %f" % (fireLoc["longitude"]))
                            count += 1
                            fireInfo.removeLocation(fireLoc)

        return count

    def filterFiresByArea(self, fireInfo):
        count = 0
        if kernel_config.getboolean("DEFAULT", "REMOVE_LOCATIONS_BELOW_AREA_THRESHOLD"):
            threshold = kernel_config.getfloat("DEFAULT", "LOCATION_AREA_THRESHOLD")
            self.log.info("Filtering fire locations by area - threshold: %f" % (threshold))
            for fireLoc in fireInfo.locations():
                if fireLoc['area'] < threshold:
                    self.log.info("Filtered out fire location with area %f" % (fireLoc["area"]))
                    count += 1
                    fireInfo.removeLocation(fireLoc)

        return count

    def filterEmptyFireEvents(self, fireInfo):
        count = 0
        location_ids = map(lambda l: l.id, fireInfo.locations())
        for fireEvent in fireInfo.events():
            if not any(l.id in location_ids for l in fireEvent.locations()):
                fireInfo.removeEvent(fireEvent)
                self.log.info("Filtered out fire event with no fire locations")
                count += 1
        return count

    def fillDateTimeTimeZoneData(self, fireInfo):
        """ Each fire has a time zone associated with the reporting time the fire started.
            This method fills in those time zones.
        """
        nFires = len(fireInfo.locations())
        nFilled = 0
        nGuessed = 0
        for fireLoc in fireInfo.locations():
            if fireLoc["date_time"] is None:
                err = '"%s" has no date_time' % fireLoc
                if self.config("REJECT_INVALID_LOCATIONS", bool):
                    raise AssertionError(err)
                elif self.config("REMOVE_INVALID_LOCATIONS", bool):
                    self.log.warn(err)
                    fireInfo.removeLocation(fireLoc)
            if fireLoc["date_time"].tzinfo is not None:
                self.log.debug("%s already has time zone %s" % (fireLoc, str(fireLoc["date_time"].tzinfo)))
                continue
            tzstr = location.latlon_timeZone(fireLoc["latitude"], fireLoc["longitude"], location.TZ_COMMON)
            tz = timezone_from_str(tzstr)
            if tz is not None:
                self.log.debug("Setting time zone for %s to %s" % (fireLoc, tz))
                nFilled += 1
            else:
                lon = fireLoc["longitude"]
                hours_offset = int(lon / (360/24))
                tzdesc = "GMT%+03d:00" % hours_offset
                tz = FixedOffset(hours_offset * 60, tzdesc)
                self.log.debug("Could not determine time zone for %s (guessing %s)" % (fireLoc, tzdesc))
                nGuessed += 1
            fireLoc["date_time"] = fireLoc["date_time"].replace(tzinfo=tz)

        if nGuessed > 0:
            self.log.warn("Filled time zone for %d of %d fires (guessed for %d)" % (nFilled, nFires, nGuessed))

        return fireInfo

    def fillFireTimeZoneData(self, fireInfo):
        """ Each fire has a time zone associated with the lat/lon of it's physical location.
            This method fills in those time zones.
        """
        # Instantiate mapscript shapefileObj
        # will later be used to read features in the shapefile
        global_tz_data = self.config("GLOBAL_TZ_DATA")
        shpfile = mapscript.shapefileObj(global_tz_data, -1)  # -1 indicates file already exists
        num_shapes = shpfile.numshapes

        # get the shapefile driver
        driver = ogr.GetDriverByName('ESRI Shapefile')

        # open the data source
        datasource = ogr.Open(global_tz_data)
        if datasource is None:
            self.log.info("Could not open time zone shapefile")

        for loc in fireInfo.locations():
            try:
                # store fire location longitude, latitude in mapscript pointOb
                # used to determine if pointObj is within global region features
                point = mapscript.pointObj(loc["longitude"], loc["latitude"])

                # determine if feature in shpfile contains fire location point
                FID = 0
                while (FID < num_shapes):
                    shape = shpfile.getShape(FID)
                    if shape.contains(point):
                        break
                    else:
                        FID += 1

                # get the data layer
                layer = datasource.GetLayerByIndex(0)
                layer.ResetReading()

                feature = layer.GetFeature(FID)
                hours_offset = feature.GetFieldAsString('ZONE')
            except:
                hours_offset = int(lon / (360.0 / 24.0))
                self.log.debug("Unable to find a global time zone for fire %s." % loc['id'])

            loc['timezone'] = hours_offset

        return fireInfo

    def fillTimeData(self, fireInfo):
        emisStart = fireInfo["emissions_start"]
        emisEnd = fireInfo["emissions_end"]
        emisDur = emisEnd - emisStart

        earliestStart = emisEnd

        locs = fireInfo.locations()
        if len(locs) == 1:
            fireLoc = locs[0]
            if fireLoc["date_time"] < emisStart:
                self.log.debug("%s is before emissions period. Adjusting emissions period." % fireLoc)
                emisStart = fireLoc["date_time"]
                emisEnd = emisStart + emisDur
            elif fireLoc["date_time"] > emisEnd:
                self.log.warn("%s is before emissions period. Adjusting emissions period." % fireLoc)
                emisStart = fireLoc["date_time"]
                emisEnd = emisStart + emisDur
            earliestStart = fireLoc["date_time"]
        else:
            for fireLoc in locs:
                if fireLoc["date_time"] < emisStart:
                    self.log.warn("%s is before emissions period. Removing fire." % fireLoc)
                    fireInfo.removeLocation(fireLoc)
                    continue
                elif fireLoc["date_time"] > emisEnd:
                    self.log.warn("%s is after emissions period. Removing fire." % fireLoc)
                    fireInfo.removeLocation(fireLoc)
                    continue
                if fireLoc["date_time"] < earliestStart:
                    earliestStart = fireLoc["date_time"]

        emisDiff = fireInfo["dispersion_start"] - earliestStart
        hours = ((emisDiff.days * 86400) + emisDiff.seconds) / 3600
        if hours >= 0:
            beforeafter = "before"
        else:
            hours = -hours
            beforeafter = "after"
            self.log.warn("WARNING: First %d hours of dispersion results will be empty", hours)
        self.log.info("Earliest fire in data set ignites %d hours %s analysis period", hours, beforeafter)

        return fireInfo

    def fillBurnSpecificData(self, fireInfo):
        for fireLoc in fireInfo.locations():

            # Assign SCC codes
            if fireLoc["scc"] is None or fireLoc["scc"] is "":

                if fireLoc["type"] == "WF":
                    fireLoc["scc"] = "2810001000" # Wildfires

                elif fireLoc["type"] == "WFU":
                    fireLoc["scc"] = "2810001001" # Wildland Fire Use

                elif fireLoc["type"] == "AG":
                    fireLoc["scc"] = "2801500000" # Agricultural Field Burning - Unspecified

                elif fireLoc["type"] == "RX":
                    fireLoc["scc"] = "2810015000" # Prescribed Forest Burning - Unspecified

                else:
                    fireLoc["scc"] = "2810090000" # Unspecified open fire

            fireLoc.set_if_undefined("type", "Unknown")
            fireLoc.set_if_undefined("area", 10)

        return fireInfo
