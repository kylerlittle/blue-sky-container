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

from time_profile import TimeProfile
from kernel.bs_datetime import BSDateTime
from kernel.types import construct_type
from datetime import timedelta
import csv

__all__ = ["WRAPTimeProfile"]


class WRAPTimeProfile(TimeProfile):
    """ WRAP Time Profile class

    This class applies a 24 hour time profile of fire growth to each fire
    in the run.  Time profiles are specified in an ascii file which defines
    the fraction of acres burned per hour for a wildfire over a 24 hour period
    from midnight (hr 0) to 11 pm local time.

    Default data are from the Air Sciences Report to the WRAP:  "Integrated
    Assessment Update and 2018 Emissions Inventory for Prescribed Fire, 
    Wildfire, and Agricultural Burning."

    Files must match the default file format with each column summing up to ~ 1.0.

        hour, area_fract, flame, smolder, residual
        0, 0.005700, 0.005700, 0.005700, 0.005700
        1, 0.005700, 0.005700, 0.005700, 0.005700
        2, 0.005700, 0.005700, 0.005700, 0.005700
        3, 0.005700, 0.005700, 0.005700, 0.005700
        4, 0.005700, 0.005700, 0.005700, 0.005700
        5, 0.005700, 0.005700, 0.005700, 0.005700
        6, 0.005700, 0.005700, 0.005700, 0.005700
        7, 0.005700, 0.005700, 0.005700, 0.005700
        8, 0.005700, 0.005700, 0.005700, 0.005700
        9, 0.005700, 0.005700, 0.005700, 0.005700
        10, 0.020000, 0.020000, 0.020000, 0.020000
        11, 0.040000, 0.040000, 0.040000, 0.040000
        12, 0.070000, 0.070000, 0.070000, 0.070000
        13, 0.100000, 0.100000, 0.100000, 0.100000
        14, 0.130000, 0.130000, 0.130000, 0.130000
        15, 0.160000, 0.160000, 0.160000, 0.160000
        16, 0.170000, 0.170000, 0.170000, 0.170000
        17, 0.120000, 0.120000, 0.120000, 0.120000
        18, 0.070000, 0.070000, 0.070000, 0.070000
        19, 0.040000, 0.040000, 0.040000, 0.040000
        20, 0.005700, 0.005700, 0.005700, 0.005700
        21, 0.005700, 0.005700, 0.005700, 0.005700
        22, 0.005700, 0.005700, 0.005700, 0.005700
        23, 0.005700, 0.005700, 0.005700, 0.005700

    Alternative files located in the WRAP module directory can be specified in 
    the ini files with:

        [WRAPTimeProfile]
        WRAP_TIME_PROFILE_FILE = ${PACKAGE_DIR}/~YOUR_PROFILE_HERE~.txt
    """

    def run(self, context):
        fireInfo = self.get_input("fires")
        
        self.log.info("Running WRAP Time Profile")

        # Get Filenames
        profileFile = self.config("WRAP_TIME_PROFILE_FILE")
        self.log.debug("WRAP_TIME_PROFILE_FILE = '%s'.", profileFile)

        for fireLoc in fireInfo.locations():
            
            # Adjust the start time to midnight local time
            fire_dt = fireLoc["date_time"]
            start_of_fire_day = BSDateTime(fire_dt.year, fire_dt.month, fire_dt.day,
                                           0, 0, 0, 0, 
                                           tzinfo=fire_dt.tzinfo)
            fireLoc["date_time"] = start_of_fire_day
            time_profile = self.readProfile(profileFile)
            fireLoc["time_profile"] = time_profile
        
        self.set_output("fires", fireInfo)

    def readProfile(self, profileFile):
        """ Read a time profile file.  (same code as in FEPS module) """
        time_profile = construct_type("TimeProfileData")
        for k in ["area_fract", "flame_profile", "smolder_profile", "residual_profile"]:
            time_profile[k] = []
        for i, row in enumerate(csv.DictReader(open(profileFile, 'r'), skipinitialspace=True)):
            assert int(row["hour"]) == i, "Invalid time profile file format (hour %s is on line %d)" % (row["hour"], i)
            time_profile["area_fract"].append(float(row["area_fract"]))
            time_profile["flame_profile"].append(float(row["flame"]))
            time_profile["smolder_profile"].append(float(row["smolder"]))
            time_profile["residual_profile"].append(float(row["residual"]))

        # TODO:  Should we sum up the elements to see if they are approximately 1.0?
        # TOTO:  How close to 1.0 should we enforce?  (default_profile sums to 0.9998)

        return time_profile
