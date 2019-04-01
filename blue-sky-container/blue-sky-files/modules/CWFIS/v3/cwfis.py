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

import getpass
import sys
import os
import csv
import string
from kernel import dbf
import ftplib
from cStringIO import StringIO
from kernel.log import corelog
from kernel.types import construct_type
from kernel.core import Process
from kernel.bs_datetime import BSDateTime, FixedOffset
from datetime import timedelta
import mapscript
try:
  from osgeo import ogr, osr
except ImportError:
  import ogr, osr

class InputCWFIS(Process):
    """ Canadian Wild Fire Information System input module """

    def init(self):
        self.declare_input("fires", "FireInformation")
        self.declare_output("fires", "FireInformation", cache=False)

    def run(self, context):
        fireInfo = self.get_input("fires")
        if fireInfo is None:
            fireInfo = construct_type("FireInformation")
        try:
            username = self.config("USERNAME")
            password = self.config("PASSWORD")
            if password is None:
                self.log.info('Need password for CWFIS user "%s"', username)
                password = getpass.getpass()

            dateStart = fireInfo["emissions_start"]
            dateEnd = fireInfo["emissions_end"]
            fireInfo, num_fires = self.get_cwfis(context, dateStart, dateEnd, username, password, fireInfo)

        except KeyboardInterrupt:
            num_fires = 0

        if num_fires == 0:
            if self.config("ERROR_ON_ZERO_FIRES", bool):
                raise Exception("CWFIS download returned zero fires")
            elif self.config("WARN_ON_ZERO_FIRES", bool):
                self.log.warn("CWFIS download returned zero fires")
        self.log.info("Successfully imported data for %s fire locations", num_fires)
            
        self.set_output("fires", fireInfo)

    def get_timezones(self):
        """Define a generic Canaidan timezone timezone (approximate and not all-inclusive)"""

        timezones = dict()
        timezones["BC"] = -8  # British Columbia
        timezones["YT"] = -8  # Yukon (CWFIS designation)
        timezones["YU"] = -8  # Yukon (SMOKE designation)
        timezones["AB"] = -7  # Alberta (CWFIS designation)
        timezones["AL"] = -7  # Alberta (SMOKE designation)
        timezones["SK"] = -6  # Saskatchewan (CWFIS designation)
        timezones["SA"] = -6  # Saskatchewan (SMOKE designation)
        timezones["MB"] = -6  # Manitoba (CWFIS designation)
        timezones["MA"] = -6  # Manitoba (SMOKE designation)
        timezones["ON"] = -5  # Ontario
        timezones["QC"] = -5  # Quebec (CWFIS designation)
        timezones["QU"] = -5  # Quebec
        timezones["NB"] = -4  # New Brunswick
        timezones["NS"] = -4  # Nova Scotia
        timezones["NF"] = -4  # Newfoundland/Labrador
        timezones["NL"] = -4  # Newfoundland/Labrador
        timezones["PE"] = -4  # Prince Edward Island
        return timezones
        
    def get_timezones_global(self, latitude, longitude, inData):
        """
        Return the time zone for this location as a float.

        Returns the string "Unknown" if the time zone could not be determined.

        Raises an exception if the time zone data file could not be opened.
        """
        
        # Instantiate mapscript shapefileObj
        # will later be used to read features in the shapefile
        shpfile = mapscript.shapefileObj(inData, -1)     # -1 indicates file already exists
        numShapes = shpfile.numshapes                            # stores the number of shapes from the shapefileObj
    
        # store fire location longitude, latitude in mapscript pointOb
        # used to determine if pointObj is within global region features
        point = mapscript.pointObj(longitude, latitude)
    
        # determine if feature in shpfile contains fire location point
        FID = 0
        while (FID < numShapes):
            shape = shpfile.getShape(FID)
            if shape.contains(point):
                break
            else:
                FID += 1
        
        # get the shapefile driver
        driver = ogr.GetDriverByName('ESRI Shapefile')

        # open the data source
        datasource = ogr.Open(inData)
        if datasource is None:
            self.log.info("Could not open time zone shapefile")

        # get the data layer
        layer = datasource.GetLayerByIndex(0)
        layer.ResetReading()
    
        feature = layer.GetFeature(FID)
        val = feature.GetFieldAsString('ZONE')

        # close the data source
        datasource.Destroy()

        return val

    def get_fipscodes(self):
        """Define a Canadian FIPS code lookup"""

        #  This generic FIPS lookup can be used in-lieu of a detailed geographic lookup.
        #  Codes will be province-specific, with county code of 000.
        #  SMOKE county file should already contain corresponding "Entire Province" entries.
                
        fipscodes = dict()
        fipscodes["NF"] = 10000  # Newfoundland/Labrador
        fipscodes["NL"] = 10000  # Newfoundland/Labrador
        fipscodes["PE"] = 11000  # Prince Edward Island
        fipscodes["NS"] = 12000  # Nova Scotia
        fipscodes["NB"] = 13000  # New Brunswick
        fipscodes["QC"] = 24000  # Quebec
        fipscodes["QU"] = 24000  # Quebec
        fipscodes["ON"] = 35000  # Ontario
        fipscodes["MB"] = 46000  # Manitoba (CWFIS designation)
        fipscodes["MA"] = 46000  # Manitoba (SMOKE designation)
        fipscodes["SK"] = 47000  # Saskatchewan (CWFIS designation)
        fipscodes["SA"] = 47000  # Saskatchewan (SMOKE designation)
        fipscodes["AB"] = 48000  # Alberta (CWFIS designation)
        fipscodes["AL"] = 48000  # Alberta (SMOKE designation)
        fipscodes["BC"] = 59000  # British Columbia
        fipscodes["YT"] = 60000  # Yukon (CWFIS designation)
        fipscodes["YU"] = 60000  # Yukon (SMOKE designation)
        fipscodes["NW"] = 61000  # Northwest Territories
        return fipscodes
        
    def get_cwfis(self, context, dtStart, dtEnd, username, password, info=None): 
   
        if not isinstance(dtStart, BSDateTime):
            raise ValueError("Expected BSDateTime object for start date, got " + type(dtStart))
        if not isinstance(dtEnd, BSDateTime):
            raise ValueError("Expected BSDateTime object for end date, got " + type(dtEnd))
        if info is None:
            info = construct_type("FireInformation")
    
        # Set FTP parameters
        hostname = self.config("HOSTNAME")
        hotspotFileLocation = self.config("FTPPATH")
        cwfis_hotspotfile = self.config("FTPFILE")
        inputDir = self.config("INPUT_DIR")

        # Try to locate a local hotspot file
        hotspotfile = None
        if self.config("USE_LOCAL_CWFIS_FILE",bool):
            hotspotfile = self.config("LOCAL_CWFIS_FILE")
            hotspotfile = os.path.join(inputDir,hotspotfile)
            if not os.path.exists(hotspotfile):
                self.log.info("LOCAL_CWFIS_FILE %s does not exist...using FTP instead" % hotspotfile)
                hotspotfile = None
            else:
                self.log.info("Using LOCAL_CWFIS_FILE %s" % hotspotfile)
                
        # FTP the hotspot file if a local copy is not being used
        if hotspotfile is None:
            hotspotfile = context.full_path("hotspots.csv")
            self.log.info("Downloading fire data from CWFIS...")     
            try:
                ftp = ftplib.FTP(hostname, username, password)
            except ftplib.all_errors, e:
                 self.log.error("Error opening CWFIS FTP to %s: %s", hostname,e)
                 return info, 0
            
            try:
                ftp.cwd(hotspotFileLocation)
                ftp.retrbinary("RETR %s" % cwfis_hotspotfile, open(hotspotfile,"wb").write)
            except ftplib.all_errors, e:
                self.log.error("Error downloading %s %s from %s: %s", 
                               hotspotFileLocation,hotspotfile,hostname,e)
                ftp.quit()
                return info, 0
            ftp.quit()
    
        # Load data from the csv file
        f = open(hotspotfile, "rb")
        
        # path to global time zone shapefile
        TZ_GLOBAL_DATA = self.config("TZ_GLOBAL_DATA")

        # Hotspot geometry (assume circular)
        hotspotRadius = float(self.config("HOTSPOT_RADIUS"))  # meters
        self.log.debug("Using hotspot radius of %s meters" % str(hotspotRadius))
        hotspotArea = 3.14159*hotspotRadius*hotspotRadius  # m^2

        # Unit conversions
        m2_per_acre = 4046.8564
        kg_per_ton = 907.1847

        # Generate timezone and FIPS code lookups
        #timezones = self.get_timezones()
        #fipscodes = self.get_fipscodes()

        # Set default duff consumption ratio
        duffConsumptionRatio = float(self.config("DUFF_CONSUMPTION_RATIO"))
            
        # Set default flaming/smoldering consumption ratio
        flamingConsumptionRatio = float(self.config("FLAMING_SMOLDERING_CONSUMPTION_RATIO"))
        
        # Determine if we write out all hotspots, or omit those with no TFC data
        INCLUDE_ALL_HOTSPOTS = self.config("INCLUDE_ALL_HOTSPOTS",bool)

        # Fill the fire information data structure for all
        #   hotspots for the current date
        hotspotNumber = 0
        num_fires = 0

        # each record in CWFIS hotspot file
        for row in csv.DictReader(f):
            
            hotspotNumber += 1

            try:
                deletechars = ["-", " ", ":"]
                datetimestr = (row[" rep_date"].strip())[:16]
                for item in deletechars:
                    datetimestr = datetimestr.replace(item, "")
            except:
                self.log.debug("Skipping hotspot with no date at hotspot %s of input file" % str(hotspotNumber))
                continue

            # Timezone naive object gets written into FireInformation structure
            #   so FillTimeZoneData can make a timezone conversion downstream.
            #   We are more ultimately more interested in whether or not fires were detected
            #   on a given day, as opposed to what time they were detected, but we 
            #   need the time info temporarily to determine the local date of
            #   hotspot detects.

            #   NOTE: As of 9/16/2008, BlueSky does not have conversions for Canada.
            #         Instead, FillTimeZoneData will guess based on longitude.

            dateObj = BSDateTime.strptime(datetimestr,"%Y%m%d%H%M",tzinfo=None)

            # Need a timezone aware datetime object for comparisons against other
            #   timezone aware objects.
            dateObjAware = BSDateTime.strptime(datetimestr,"%Y%m%d%H%M")

            # Filter around emission_start and emission_end to prevent thousands of 
            #    unnecessary fires from being passed around the Framework.
            #    Use EMISSIONS_OFFSET (with SPIN_UP_EMISSIONS=true) in the configuration 
            #    file to change the emissions start time.  The emissions end time depends 
            #    on HOURS_TO_RUN. 
            
            if dateObjAware >= dtStart - timedelta(days=1) and dateObjAware <= dtEnd + timedelta(days=1):
    
                # Create a fire identification string
                hotspotID = "CF%8.8d" % hotspotNumber

                # Create a new fire fire event.  With no way to associate fires to events,
                #   each hotspot is also an event.
                event = construct_type("FireEventData")
                event["event_id"] = "%6.6d" % hotspotNumber
                event["event_name"] = "Unknown"
    
                # Make a new FireLocation object to hold data from this row 
                loc = construct_type("FireLocationData",hotspotID)            
    
                # All hotspots must have a location to be processed
                try:
                    loc["latitude"] = float(row["lat"])
                    loc["longitude"] = float(row[" lon"])
                except:
                    self.log.debug("Skipped fire %s because it has no latitude/longitude" % hotspotID)
                    continue
                
                # Provinces are helpful, but not requred unless you need SMOKEReadyFiles
                #if row[dbfFieldIndex["PROVINCE"]] is not None:
                #    province = str(row[dbfFieldIndex["PROVINCE"]])
                #else:
                #    province = None
                #loc["state"] = province        

                # Figure out which local day the hotspot was detected.  Use value
                #   at location in global shapefile when possible, 
                #   otherwise guess based on longitude.
                #   BlueSky will ignite a fire at midnight local time for 
                #   each hotspot detected on that day.

                lon = loc["longitude"]
                lat = loc["latitude"]
                try:
                    hours_offset = self.get_timezones_global(lat, lon, TZ_GLOBAL_DATA)
                except:
                    hours_offset = int(lon / (360/24))
                    self.log.info("Unable to find a global time zone.")
                dateObj = dateObj + timedelta(hours=float(hours_offset))

                # Just keep the date part of dateObj as a timezone naive object
                datestr2 = dateObj.strftime("%Y%m%d%H%M")
                tzdesc = "GMT%+03d:00" % float(hours_offset)
                tz = FixedOffset(float(hours_offset) * 60, tzdesc)
                loc["date_time"] = BSDateTime.strptime(datestr2,"%Y%m%d%H%M",tzinfo=tz)

                # FIPS code assignment
                #try:
                #    loc["fips"] = fipscodes[province]
                #except KeyError:
                #    loc["fips"] = -9999

                # Other hotspot information
                loc["area"] = hotspotArea/m2_per_acre
                loc["country"] = "CANADA"
                loc["type"] = "Unknown"
                loc["owner"] = None
                loc["elevation"] = None
                loc["slope"] = None
                loc["county"] = None
                loc["time_profile"] = None
                loc["fuels"] = None
                loc["emissions"] = None

                #  Consumption
                if row[" tfc"] is not None:                  
                    consumption = construct_type("ConsumptionData")

                    scalingFactor = m2_per_acre/kg_per_ton

                    # Total fuel consumption (convert from kg/m^2 to tons/acre)
                    tfc = float(row[" tfc"]) * scalingFactor

                    # Apply flaming/smoldering consumption ratio
                    #    If required data are null, or not in hotspot file, use default
                    try:
                        ratio = float(row[" sfc"])/float(row[" bfc"])
                        sfc = float(row[" sfc"]) * scalingFactor
                        if ratio > 1.0:
                            ratio = 1.0
                        consumption["flaming"] = (tfc - sfc) + (sfc * ratio)
                    except:
                        self.log.warn("Using default flaming/smoldering consumption ratio of %s for hotspot %s" % 
                                      (str(flamingConsumptionRatio),hotspotID))
                        consumption["flaming"] = tfc*flamingConsumptionRatio

                    consumption["smoldering"] = tfc - consumption["flaming"]
                    consumption["residual"] = 0.0

                    # Duff consumption (use BORFire fuel consumption when present)
                    #   If required data are null, or not in hotspot file, use default
                    try:
                        duff = float(row[" bfc"]) * scalingFactor
                    except:
                        self.log.warn("Using default duff consumption ratio of %s for hotspot %s" % 
                                      (str(duffConsumptionRatio),hotspotID))
                        duff = tfc*duffConsumptionRatio

                    consumption["duff"] = duff
                    
                    loc["consumption"] = consumption

                # Add this event and location into the structure
                if self.config("INCLUDE_ALL_HOTSPOTS",bool) or row[" tfc"] is not None:
                    event.addLocation(loc)
                    info.addEvent(event)
                    info.addLocation(loc)
                    
                    num_fires += 1
                else:
                    self.log.debug("fire %s omitted because it does not have TFC data" % loc["id"])
    
        return info, num_fires
