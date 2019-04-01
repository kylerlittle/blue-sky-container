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

import os.path
from cStringIO import StringIO
from datetime import timedelta
from glob import glob

from kernel.core import Process
from kernel.types import construct_type
from kernel.bs_datetime import BSDateTime
from kernel.log import SUMMARY
from kernel import location

# gdal and numpy are needed in fillMetDomainInfo
from osgeo import gdal
import numpy as np


class InputWRF(Process):
    """ Input WRF-format meteorological data
    
    Uses the WRF_PATTERN config variable to find WRF format files containing
    
    the datetime string at the end of each WRF file.  Outputs a MetInfo object
    containing a list of WRF-format files together with date/time information.
    """
    def init(self):
        self.declare_input("met_info", "MetInfo")
        self.declare_output("met_info", "MetInfo")
    
    def run(self, context):
        
        met = self.get_input("met_info")
        if met is None:
            met = construct_type("MetInfo")

        if self.config("WRF_NEST", bool):
            wrfpattern = self.config("WRF_NEST_PATTERN")
            delta = timedelta(seconds=self.config("WRF_NEST_TIME_DELTA", int))
            self.populate_files(context, wrfpattern, met, delta, nest=True)

        wrfpattern = self.config("WRF_PATTERN")
        delta = timedelta(seconds=self.config("WRF_TIME_DELTA", int))
        self.populate_files(context, wrfpattern, met, delta, nest=False)

        # Determine the MetInfo "met_start" and "met_end"
        met_start = min([f["start"] for f in met["files"]])
        met_end = max(f["end"] for f in met["files"])
                
        self.log.log(SUMMARY, "Available meteorology: " + met_start.strftime('%Y%m%d %HZ') + 
                      " to " + met_end.strftime('%Y%m%d %HZ'))        
        
        # Check against the dispersion times
        assert met_start <= met["dispersion_start"], "Insufficient WRF data to run selected dispersion period"
        assert met_end >= met["dispersion_start"], "Insufficient WRF data to run selected dispersion period"

        if met_end < met["dispersion_end"]:
            self.log.warn("WARNING: Insufficient WRF data to run full dispersion period; truncating dispersion")

        disp_end = min(met["dispersion_end"], met_end)
        disp_time = disp_end - met["dispersion_start"]
        disp_hours = ((disp_time.days * 86400) + disp_time.seconds) / 3600
        self.log.info("Dispersion will run for %d hours", disp_hours)

        # Fill in the MetInfo object
        met["met_start"] = met_start
        met["met_end"] = met_end
        met["file_type"] = "WRF"
        self.set_output("met_info", met)


    def populate_files(self, context, wrfpattern, met, delta=3600, nest=False):
        wrffiles = list()
        
        # Decide where in the MetInfo object to store information
        if nest:
            met_files = "files_nest"
            msg_files = "nested WRF files"
            msg_pattern = "WRF_NEST_PATTERN"
        else:
            met_files = "files"
            msg_files = "WRF files"
            msg_pattern = "WRF_PATTERN"

        # NOTE: Standard WRF files always consist of a single timestep and their 
        # NOTE: filenames always end with the 19 character datetime string
        # NOTE: representing their start time, e.g.  "wrfout_d01_2012-12-21_00:00:00"

        # Find all of the files within the date range that match the pattern
        if "%" in wrfpattern:
            date = met["dispersion_start"]
            while date < met["dispersion_end"]:
                wrfglob = date.strftime(wrfpattern)
                wrffiles += sorted(glob(wrfglob))
                date += delta
        else:
            self.log.warn("Found no matching %s; meteorological data are not available" % (msg_files))
            self.log.debug("%s '%s' must contain a percent sign." % 
                           (msg_pattern, os.path.basename(wrfpattern)))
            self.set_output("met_info", met)
            return
         
        # Check that we got some met data
        if not len(wrffiles):
            if self.config("STOP_IF_NO_MET", bool):
                raise Exception("Found no matching WRF files. Stop.")
            self.log.warn("Found no matching %s; meteorological data are not available" % (msg_files))
            self.log.debug("No %s matched '%s'" % (msg_files, os.path.basename(wrfpattern)))
            self.set_output("met_info", met)
            return
            
        self.log.info("Got %d %s" % (len(wrffiles), msg_files))
        
        # NOTE: Assumption 1)  WRF files only have one timestep
        # NOTE: Assumption 2)  WRF filenames end with a datetime string
        # NOTE: Assumption 3)  temporal spacing between WRF files does not change
        
        # Fill in the MetInfo object with a list of MetFileInfo objects.
        # Each MetFileInfo object contains: "filename", "start", "end"
                
        using_restart = False
        for wrffile in wrffiles:
            if not context.file_exists(wrffile): 
                raise IOError("Missing required file: %s" % wrffile)
            
            start = BSDateTime.bs_strptime(wrffile[-19:].replace("_"," "))
            end = start + delta
            
            # NOTE: Section with 'is_restart' in mm5data.py is unique to MM5 and not included here.
            
            # Create the MetFileInfo object for this file
            info = construct_type("MetFileInfo")
            info["filename"] = wrffile
            info["start"] = start
            info["end"] = end
            
            if end >= met["dispersion_start"] and start <= met["dispersion_end"]:
                met[met_files].append(info)
            else:
                self.log.debug("Ignoring file %s because it's outside the dispersion range" % 
                               os.path.basename(wrffile))
        
        if not len(met[met_files]):
            self.log.warn("No matching %s fit the requested dispersion interval" %
                          (msg_files))
            self.set_output("met_info", met)
            return
            
            
    def output_handler(self, logger, output, is_stderr):
        if is_stderr:
            logger.error(output)
            self.binary_output += output + "\n"
        else:
            self.binary_output += output + "\n"


class WRFLocalMet(Process):
    """ Extract fire-local meteorological data

    Takes a MetInfo object (which must contain information about WRF-format
    meteorological data files) and a FireInformation object containing fires, 
    and *SHOULD* fill in data for each FireLocationData object with values 
    from the WRF data.  For MM5 data, only elevation values are filled.
    For ARL data and WRF data, no elevation information is available so
    zero is used as the fill value.
    
    Also, if the REMOVE_INVALID_LOCATIONS config variable is set to true, then
    any FireLocations outside of the given WRF modeling extent *SHOULD* be
    removed from the FireInformation dataset.
    """
    
    def init(self):
        self.declare_input("met_info", "MetInfo")
        self.declare_input("fires", "FireInformation")
        self.declare_output("met_info", "MetInfo")
        self.declare_output("fires", "FireInformation")

    def run(self, context):
        met_info = self.get_input("met_info")
        fireInfo = self.get_input("fires")
        
        if met_info.file_type != "WRF":
            raise Exception("WRFLocalMet can only be used with WRF-format met data")
        
        if not len(met_info["files"]):
            raise Exception("WRFLocalMet stopped because met_info.files is empty")

        # Get the first met file filename
        wrfdataFilename = met_info["files"][0]["filename"]
        if not context.file_exists(wrfdataFilename): 
            raise IOError("Missing required file: %s" % wrfdataFilename)

        # Build MetDomainInfo structure based on information from the first met file
        self.fillMetDomainInfo(context, met_info, wrfdataFilename)

        # Fill location data into FireInformation
        # TODO: How to provide fireLoc["elevation"] info in WRFLocalMet
        self.log.info("Unable to extract local met from WRF data; elevation is undefined")
        for fireLoc in fireInfo.locations():
            fireLoc["elevation"] = 0
            
        # Fill local weather data
        self.fillLocalWeather(fireInfo)

        # TODO: Do we need this 'extra' information?
        #met_info.metadata["extra:geo_metDomain"] = context.full_path("geo_metDomain.dat")
        #met_info.metadata["extra:wt_dat"] = context.full_path("wt.dat")

        self.set_output("met_info", met_info)
        self.set_output("fires", fireInfo)

    def fillMetDomainInfo(self, context, met_info, wrfdataFilename):
        """Fill the met_info.met_domain_info structure.

        This function uses the osgeo.gdal and numpy modules to extract
        information from the WRF NetCDF met files.  Only the first met
        file in the list is examined as all are assumed to be on the
        same grid.
        """

        # The met_domain_infor structure is filled with information
        # describing the domain of the met grids used.  When MM5 files
        # are used, this information includes:
        #
        #   'domainID': 4.0
        #   'lonC': -95.0       # central lon
        #   'latC': 40.0        # central lat
        #   'alpha': 30.0       # standard latitude
        #   'beta': 60.0
        #   'gamma': -95.0
        #   'yllM': -474000.0
        #   'xllM': 1320000.0
        #   'nyCRS': 108.0      # number of lat gridpoints
        #   'nxCRS': 108.0      # number of lon gridpoints
        #   'dxKM': 1.333       # grid spacing in km
        #   'lon_min': -80.2540
        #   'lon_max': -78.3774
        #   'lat_min': 34.26299
        #   'lat_max': 35.79939
        #
        # For CALPuff, the following components are needed:
        #   alpha
        #   beta
        #   domainID
        #   dxKM
        #   latC
        #   lonC
        #   nxCRS
        #   nyCRS
        #   xllM
        #   yllM
        #
        # For HYSPLIT, only the following are needed:
        #    lat_max
        #    lat_min
        #    lon_max
        #    lon_min
        #    nxCRS
        #    nyCRS
        
        met_info.met_domain_info = construct_type("MetDomainInfo")
        
        self.log.info("Obtaining met_domain_info from %s" % (wrfdataFilename))

        # NOTE: GDAL uses ':' as special filename syntax so we have to
        # NOTE: rename wrfdataFilename to something without ':'.

        gdalBasename = os.path.basename(wrfdataFilename).replace(":","_")
        context.link_file(wrfdataFilename, gdalBasename)
        gdalFilename = context.full_path(gdalBasename)

        lat_dataset = gdal.Open("NETCDF:"+gdalFilename+":XLAT")
        lat = lat_dataset.ReadAsArray()

        lon_dataset = gdal.Open("NETCDF:"+gdalFilename+":XLONG")
        lon = lon_dataset.ReadAsArray()

        (nyCRS, nxCRS) = np.shape(lat)

        met_info.met_domain_info["nxCRS"] = nxCRS
        met_info.met_domain_info["nyCRS"] = nyCRS
        met_info.met_domain_info["lat_min"] = np.min(lat)
        met_info.met_domain_info["lat_max"] = np.max(lat)
        met_info.met_domain_info["lon_min"] = np.min(lon)
        met_info.met_domain_info["lon_max"] = np.max(lon)


    def fillLocalWeather(self, fireInfo):
        """Fill the fireLoc.local_weather structure with default values."""
        # NOTE: Code copied verbatim from MM5data/v2/mm5data.py
        for fireLoc in fireInfo.locations():
            if fireLoc.local_weather is None:
                fireLoc.local_weather = construct_type("LocalWeatherData")
            
            # NOTE: This currently just duplicates the code from fill_data.py.
            # TODO: Instead, we should read/compute values from met data!
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


