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
from kernel.types import construct_type
from kernel.bs_datetime import BSDateTime, utc, timezone_from_str, FixedOffset
from datetime import timedelta

class FillDefaultData(Process):
    """ Provide defaults for missing input fields
    
    """
    
    def init(self):
        self.declare_input("fires", "FireInformation")
        self.declare_output("fires", "FireInformation")
   
    def run(self, context):
        fireInfo = self.get_input("fires")
        fireInfo = self.fillLocationData(fireInfo)
        fireInfo = self.fillTimeZoneData(fireInfo)
        fireInfo = self.fillTimeData(fireInfo)
        fireInfo = self.fillBurnSpecificData(fireInfo)
        fireInfo = self.fillLocalWeather(fireInfo)
        self.set_output("fires", fireInfo)
        
    def fillLocalWeather(self, fireInfo):
        for fireLoc in fireInfo.locations():
            if fireLoc.local_weather is None:
                fireLoc.local_weather = construct_type("LocalWeatherData")
            fireLoc.local_weather.setdefault("min_wind", 6)
            fireLoc.local_weather.setdefault("max_wind", 6)
            fireLoc.local_weather.setdefault("min_wind_aloft", 6)
            fireLoc.local_weather.setdefault("max_wind_aloft", 6)
            fireLoc.local_weather.setdefault("min_humid", 40)
            fireLoc.local_weather.setdefault("max_humid", 80)
            fireLoc.local_weather.setdefault("min_temp", 13)
            fireLoc.local_weather.setdefault("max_temp", 30)
            fireLoc.local_weather.setdefault("min_temp_hour", 4)
            fireLoc.local_weather.setdefault("max_temp_hour", 14)
            fireLoc.local_weather.setdefault("sunrise_hour", 6)
            fireLoc.local_weather.setdefault("sunset_hour", 18)
            fireLoc.local_weather.setdefault("snow_month", 5)
            fireLoc.local_weather.setdefault("rain_days", 8)
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
        
    def fillTimeZoneData(self, fireInfo):
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
