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
import csv
from cStringIO import StringIO
from datetime import timedelta
from glob import glob

from kernel.core import Process
from kernel.types import construct_type
from kernel.bs_datetime import BSDateTime
from kernel.log import SUMMARY
from kernel import location

class InputMM5(Process):
    """ Input MM5-format meteorological data
    
    Uses the MM5_PATTERN config variable to find MM5 format files containing
    meteorological data.  Uses the mm5size program (specified by the 
    MM5SIZE_BINARY config variable) to examine the MM5 header on each file and
    gather information about available timesteps.  Outputs a MetInfo object
    containing a list of MM5-format files together with date/time information.
    """
    def init(self):
        self.declare_input("met_info", "MetInfo")
        self.declare_output("met_info", "MetInfo")
    
    def run(self, context):
 
        met = self.get_input("met_info")
        if met is None:
            met = construct_type("MetInfo")
        
        if self.config("MM5_NEST", bool):
            mm5pattern = self.config("MM5_NEST_PATTERN")
            self.populate_files_nest(context, mm5pattern, met)

        mm5pattern = self.config("MM5_PATTERN")
        self.populate_files(context, mm5pattern, met)

        met_start = min([f["start"] for f in met["files"]])
        met_end = max(f["end"] for f in met["files"])
                
        self.log.log(SUMMARY, "Available meteorology: " + met_start.strftime('%Y%m%d %HZ') + 
                      " to " + met_end.strftime('%Y%m%d %HZ'))        
        
        assert met_start <= met["dispersion_start"], "Insufficient MM5 data to run selected dispersion period"
        assert met_end >= met["dispersion_start"], "Insufficient MM5 data to run selected dispersion period"

        if met_end < met["dispersion_end"]:
            self.log.warn("WARNING: Insufficient MM5 data to run full dispersion period; truncating dispersion")

        disp_end = min(met["dispersion_end"], met_end)
        disp_time = disp_end - met["dispersion_start"]
        disp_hours = ((disp_time.days * 86400) + disp_time.seconds) / 3600
        self.log.info("Dispersion will run for %d hours", disp_hours)

        met["met_start"] = met_start
        met["met_end"] = met_end
        met["file_type"] = "MM5"
        self.set_output("met_info", met)
 
    def populate_files(self, context, mm5pattern, met):
        MM5SIZE_BINARY = self.config("MM5SIZE_BINARY")
        mm5files = list()
        
        if "%" in mm5pattern:
            date = met["dispersion_start"]
            while date < met["dispersion_end"]:
                mm5glob = date.strftime(mm5pattern)
                mm5files += sorted(glob(mm5glob))
                date += timedelta(days=1)
        else:
            mm5files = sorted(glob(mm5pattern))
         
        if not len(mm5files):
            if self.config("STOP_IF_NO_MET", bool):
                raise Exception("Found no matching MM5 files. Stop.")
            self.log.warn("Found no matching MM5 files; meteorological data are not available")
            self.log.debug("No MM5 files matched '%s'", os.path.basename(mm5pattern))
            self.set_output("met_info", met)
            return
            
        self.log.info("Got %d MM5 files" % len(mm5files))
        
        using_restart = False
        for mm5file in mm5files:
            if not context.file_exists(mm5file): 
                raise IOError("Missing required file: %s" % mm5file)
            
            self.binary_output = ""
            context.execute(MM5SIZE_BINARY, mm5file, 
                            output_handler=self.output_handler)
            assert len(self.binary_output), "Got no output from mm5size"
            assert ("ERROR" not in self.binary_output), self.binary_output
            
            try:
                row = csv.DictReader(StringIO(self.binary_output)).next()
            except:
                raise Exception("Unable to parse output: '%s'" % self.binary_output)
            start = BSDateTime.bs_strptime(row['start_date'])
            dur = timedelta(minutes=int(float(row['simulation_minutes'])))
            end = start + dur
            
            if row["is_restart"] == "1":
                if not using_restart:
                    if len(met["files"]) == 1 and met["files"][0]["start"] == start:
                        using_restart = True
                    else:
                        self.log.warn("Ignoring restarted file %s because we have multiple MM5 runs",
                                      os.path.basename(mm5file))
                        continue
                last_end = start
                for f in met["files"]:
                    if f["end"] > last_end:
                        last_end = f["end"]
                start = last_end
            
            info = construct_type("MetFileInfo")
            info["filename"] = mm5file
            info["start"] = start
            info["end"] = end
            
            if end >= met["dispersion_start"] and start <= met["dispersion_end"]:
                met["files"].append(info)
            else:
                self.log.debug("Ignoring file %s because it's outside the dispersion range", 
                               os.path.basename(mm5file))
        
        if not len(met["files"]):
            self.log.warn("No matching MM5 files fit the requested dispersion interval")
            self.set_output("met_info", met)
            return
            
    def populate_files_nest(self, context, mm5pattern, met):
        MM5SIZE_BINARY = self.config("MM5SIZE_BINARY")
        mm5files = list()
        
        if "%" in mm5pattern:
            date = met["dispersion_start"]
            while date < met["dispersion_end"]:
                mm5glob = date.strftime(mm5pattern)
                mm5files += sorted(glob(mm5glob))
                date += timedelta(days=1)
        else:
            mm5files = sorted(glob(mm5pattern))
         
        if not len(mm5files):
            if self.config("STOP_IF_NO_MET", bool):
                raise Exception("Found no matching nested MM5 files. Stop.")
            self.log.warn("Found no matching nested MM5 files; meteorological data are not available")
            self.log.debug("No nested MM5 files matched '%s'", os.path.basename(mm5pattern))
            self.set_output("met_info", met)
            return
            
        self.log.info("Got %d nested MM5 files" % len(mm5files))
        
        using_restart = False
        for mm5file in mm5files:
            if not context.file_exists(mm5file): 
                raise IOError("Missing required file: %s" % mm5file)
            
            self.binary_output = ""
            context.execute(MM5SIZE_BINARY, mm5file, 
                            output_handler=self.output_handler)
            assert len(self.binary_output), "Got no output from mm5size"
            assert ("ERROR" not in self.binary_output), self.binary_output
            
            try:
                row = csv.DictReader(StringIO(self.binary_output)).next()
            except:
                raise Exception("Unable to parse output: '%s'" % self.binary_output)
            start = BSDateTime.bs_strptime(row['start_date'])
            dur = timedelta(minutes=int(float(row['simulation_minutes'])))
            end = start + dur
            
            if row["is_restart"] == "1":
                if not using_restart:
                    if len(met["files_nest"]) == 1 and met["files_nest"][0]["start"] == start:
                        using_restart = True
                    else:
                        self.log.warn("Ignoring restarted file %s because we have multiple nested MM5 runs",
                                      os.path.basename(mm5file))
                        continue
                last_end = start
                for f in met["files_nest"]:
                    if f["end"] > last_end:
                        last_end = f["end"]
                start = last_end
            
            info = construct_type("MetFileInfo")
            info["filename"] = mm5file
            info["start"] = start
            info["end"] = end
            
            if end >= met["dispersion_start"] and start <= met["dispersion_end"]:
                met["files_nest"].append(info)
            else:
                self.log.debug("Ignoring file %s because it's outside the dispersion range", 
                               os.path.basename(mm5file))
        
        if not len(met["files_nest"]):
            self.log.warn("No matching nested MM5 files fit the requested dispersion interval")
            self.set_output("met_info", met)
            return
            
            
    def output_handler(self, logger, output, is_stderr):
        if is_stderr:
            logger.error(output)
            self.binary_output += output + "\n"
        else:
            self.binary_output += output + "\n"


class MM5LocalMet(Process):
    """ Extract fire-local meteorological data
    
    Takes a MetInfo object (which must contain information about MM5-format
    meteorological data files) and a FireInformation object containing fires, 
    and fills data for each FireLocationData object with values from the MM5
    data.  Currently, only elevation values are filled; in the future more
    data will be extracted.
    
    Also, if the REMOVE_INVALID_LOCATIONS config variable is set to true, then
    any FireLocations outside of the given MM5 modeling extent will be removed
    from the FireInformation dataset.
    
    As a byproduct of running the mm52geo program (using the executable 
    specified by the MM52GEO_BINARY config variable), two additional files get
    generated: wt.dat and geo.dat, which are used by CALMET.  The paths to
    these files are stored in the metadata dictionary of the output MetInfo
    object.  This behavior may change in future versions.
    """
    def init(self):
        self.declare_input("met_info", "MetInfo")
        self.declare_input("fires", "FireInformation")
        self.declare_output("met_info", "MetInfo")
        self.declare_output("fires", "FireInformation")

    def run(self, context):
        met_info = self.get_input("met_info")
        fireInfo = self.get_input("fires")
        
        if met_info.file_type != "MM5":
            raise Exception("MM5LocalMet can only be used with MM5-format met data")
        
        if not len(met_info["files"]):
            self.log.debug("Skip MM5toGeo because met_info files list is empty")
            metDomainInfo = construct_type("MetDomainInfo")
            met_info.met_domain_info = metDomainInfo
            fireInfo = self.fillLocationData(fireInfo, metDomainInfo, "")
            self.set_output("met_info", met_info)
            self.set_output("fires", fireInfo)
            return

        mm5dataFilename = met_info["files"][0]["filename"]
        if not context.file_exists(mm5dataFilename): 
            raise IOError("Missing required file: %s" % mm5dataFilename)

        MM52GEO_BINARY = self.config("MM52GEO_BINARY")
        context.execute(MM52GEO_BINARY, mm5dataFilename)
        context.archive_file("geo_CRS_2d")
        context.archive_file("geo_metDomain.dat")
        context.archive_file("wt.dat")
        
        # Build MetDomainInfo structure
        metDomainInfo = self.readMetDomainInfo(context.full_path("metDomainParams.csv"))
        met_info.met_domain_info = metDomainInfo
        
        # Fill location data into FireInformation
        elevation_data_filename = context.full_path("geo_CRS_2d")
        fireInfo = self.fillLocationData(fireInfo, metDomainInfo, elevation_data_filename)
        
        # Fill local weather data
        self.fillLocalWeather(fireInfo)
        
        # Fill in some metadata fields (TO DO: is there a better way to do this?)
        met_info.metadata["extra:geo_metDomain"] = context.full_path("geo_metDomain.dat")
        met_info.metadata["extra:wt_dat"] = context.full_path("wt.dat")
        
        self.set_output("met_info", met_info)
        self.set_output("fires", fireInfo)
        
    def readMetDomainInfo(self, filename):
        info = construct_type("MetDomainInfo")
        row = csv.DictReader(open(filename, 'r')).next()
        for (key,value) in row.iteritems():
            info[key] = float(value)
        return info

    def fillLocalWeather(self, fireInfo):
        for fireLoc in fireInfo.locations():
            if fireLoc.local_weather is None:
                fireLoc.local_weather = construct_type("LocalWeatherData")

            # NOTE: This currently just duplicates the code from fill_data.py.
            # TO DO: Instead, we should read/compute values from met data!
                
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
        
    def fillLocationData(self, fireInfo, met_domain_info, elevation_data_filename):
        removeInvalidLocs = self.config("REMOVE_INVALID_LOCATIONS",bool)
        if met_domain_info["domainID"] == None:
            removeInvalidLocs = False

        nFires = len(fireInfo.locations())
        if nFires == 0:
            self.log.warn("Data set contains no fires! Skip...")
            return fireInfo
        
        if elevation_data_filename == "":
            self.log.info("No elevation file; elevation is undefined")
        
        nRemoved = 0
        nFilled = 0
        for fireLoc in fireInfo.locations():
            if elevation_data_filename == "":
                fireLoc["elevation"] = 0
                continue
        
            fireLoc["elevation"] = location.elevation(fireLoc["latitude"],
                                                      fireLoc["longitude"],
                                                      met_domain_info,
                                                      elevation_data_filename)
            if fireLoc["elevation"] == -99999:
                if removeInvalidLocs:
                    self.log.debug("Removing %s: invalid location (not in modeled domain)", fireLoc)
                    fireInfo.removeLocation(fireLoc)
                    nRemoved += 1
                else:
                    self.log.debug("Unable to find elevation, using 0 instead")
                    fireLoc["elevation"] = 0
            else:
                nFilled += 1

        if nRemoved >= nFires:
            raise AssertionError("All input fires are outside the modeled domain.  Stop.")
            
        if removeInvalidLocs:
            self.log.info("Filled elevation data for %d fires", nFilled)
            self.log.info("Removed %d fires that were outside the modeled domain", nRemoved)
        else:
            self.log.info("Filled elevation data for %d of %d fires", nFilled, nFires)
        
        return fireInfo
        
