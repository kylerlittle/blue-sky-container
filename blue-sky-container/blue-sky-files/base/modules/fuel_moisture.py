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
from kernel.types import construct_type

class FuelMoisture(Process):
    def init(self):
        self.declare_input("fires", "FireInformation")
        self.declare_output("fires", "FireInformation")

# Default fuel moisture table
#                                 1-hr  10-hr  100-hr  1000-hr  live  duff
MOISTURE_PROFILES = [("Very Dry",    4,     6,      8,       8,   60,   25),
                     ("Dry",         7,     8,      9,      12,   80,   40),
                     ("Moderate",    8,     9,     11,      15,  100,   70),
                     ("Moist",      10,    12,     12,      22,  130,  150),
                     ("Wet",        18,    20,     22,      31,  180,  250),
                     ("Very Wet",   28,    30,     32,      75,  300,  400)]

class DefaultFuelMoisture(FuelMoisture):
    """ Provide default fuel moisture information
    """
    
    def run(self, context):
        fireInfo = self.get_input("fires")
        for fireLoc in fireInfo.locations():
            
            if fireLoc.fuel_moisture is None:
                # If there is no moisture info at all, just fill in one of our
                # default moisture profiles.
                self.fillDefaultMoisture(fireLoc)
            else:
                # If we already have a FuelMoistureData object, just make sure
                # all of its fields are correctly populated.
                self.populateMissingFields(fireLoc)
            
        self.set_output("fires", fireInfo)
        
    def buildMoisture(self, profile_tuple):
        name, m1hr, m10hr, m100hr, m1khr, mlive, mduff = profile_tuple
        result = construct_type("FuelMoistureData")
        result.moisture_1hr = m1hr
        result.moisture_10hr = m10hr
        result.moisture_100hr = m100hr
        result.moisture_1khr = m1khr
        result.moisture_live = mlive
        result.moisture_duff = mduff
        return result
        
    def fillDefaultMoisture(self, fireLoc):
        if fireLoc.type in ("WF", "WFU"):
            profile = MOISTURE_PROFILES[1] # Dry
        else:
            profile = MOISTURE_PROFILES[3] # Moist
        fireLoc.fuel_moisture = self.buildMoisture(profile)
        
    def populateMissingFields(self, fireLoc):
        fm = fireLoc.fuel_moisture
        
        keys = [None, "moisture_1hr", "moisture_10hr", "moisture_100hr", 
                "moisture_1khr", "moisture_live", "moisture_duff"]
    
        # Figure out which key we will be using to come up with the 
        # matching profile.
        key_idx = None
        for i, key in enumerate(keys):
            if key is not None and fm[key] is not None:
                key_idx = i
        if key_idx is None:
            self.fillDefaultMoisture(fireLoc)
            return
    
        # Find the profile that matches the given key.
        profile = None
        for profile_tuple in reversed(MOISTURE_PROFILES):
            if fm[keys[key_idx]] >= profile_tuple[key_idx]:
                profile = profile_tuple
                break
        if profile is None:
            profile = MOISTURE_PROFILES[0]
        
        # Populate missing values in the fuel_moisture structure from
        # the corresponding values in the matching profile.
        for i, key in enumerate(keys):
            if key is not None and fm[key] is None:
                fm[key] = profile[i]
   