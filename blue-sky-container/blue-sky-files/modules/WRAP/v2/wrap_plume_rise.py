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

from plume_rise import PlumeRise
from kernel.types import construct_type
from kernel.bs_datetime import BSDateTime
from datetime import timedelta
import math

__all__ = ["WRAPPlumeRise"]

# Buoyant Efficiency as Function of Hour of Day
# Data from WRAP 2002 EI Report
BUOYANT_EFFICIENCY = [ 0.03, 0.03, 0.03, 0.03, 0.03, 0.03,
                       0.03, 0.03, 0.06, 0.10, 0.20, 0.40,
                       0.70, 0.80, 0.90, 0.95, 0.99, 0.80,
                       0.70, 0.40, 0.06, 0.03, 0.03, 0.03 ]

class FireSizeClass(object):
    def __init__(self, classnum, min_size, max_size, be_size, p_top_max, p_bot_max):
        self.classnum = classnum
        self.min_size = min_size
        self.max_size = max_size
        self.be_size = be_size
        self.p_top_max = p_top_max
        self.p_bot_max = p_bot_max

EMPTY_FIRE_CLASS = FireSizeClass(0, 0, 0, 0, 0, 0)
   
FIRE_CLASSES = [ FireSizeClass(1,    0,   10, 0.40,  160,    0),
                 FireSizeClass(2,   10,  100, 0.60, 2400,  900),
                 FireSizeClass(3,  100, 1000, 0.75, 6400, 2200),
                 FireSizeClass(4, 1000, 5000, 0.85, 7200, 3000),
                 FireSizeClass(5, 5000, None, 0.90, 8000, 3000) ]

def getFireClassBySize(size):
    if size == 0:
        return EMPTY_FIRE_CLASS
    for cls in FIRE_CLASSES:
        if size >= cls.min_size and (cls.max_size is None or size < cls.max_size):
            return cls


class WRAPPlumeRise(PlumeRise):

    def run(self, context):
        fireInfo = self.get_input("fires")
        
        for fireLoc in fireInfo.locations():
            if fireLoc["fuels"] is None:
                self.log.debug("Fire %s has no fuel loading; skip...", fireLoc["id"])
                continue
            
            if fireLoc["plume_rise"] is not None:
                self.log.debug("Skipping %s because it already has plume rise" % fireLoc)
                continue

            acres = fireLoc["area"]
            fuel_keys = [ "fuel_1hr", "fuel_10hr", "fuel_100hr", "fuel_1khr", 
                          "fuel_10khr", "fuel_gt10khr", "shrub", "grass", "rot",
                          "duff", "litter" ]
            total_fuel_loading = 0
            for k in fuel_keys:
                total_fuel_loading += fireLoc["fuels"][k]
                
            if fireLoc["type"] in ("WF", "WFU"):
                fuel_loading_normalizer = 13.8
            else:
                fuel_loading_normalizer = 5.0
                            
            virtual_acres = acres * math.sqrt(total_fuel_loading / fuel_loading_normalizer)
            
            plumeRise = construct_type("PlumeRise")
            plumeRise.hours = []
            
            for hour in range(24):
                # This is the actual plume rise calcuation
                cls = getFireClassBySize(virtual_acres)
                be_hour = BUOYANT_EFFICIENCY[hour]
                
                p_top = (be_hour ** 2) * (cls.be_size ** 2) * cls.p_top_max
                p_bot = (be_hour ** 2) * (cls.be_size ** 2) * cls.p_bot_max
                lay1_frac = 1.0 - (be_hour * cls.be_size)
                if cls.classnum == 0:
                    lay1_frac = 0.0
                
                # Construct a PlumeRiseHour structure from lay1_frac (smoldering_fraction), 
                # p_bot (plume_bottom_meters), and p_top (plume_top_meters).
                plumeRiseHour = construct_type("PlumeRiseHour", lay1_frac, p_bot, p_top)
                plumeRise.hours.append(plumeRiseHour)
                
            fireLoc["plume_rise"] = plumeRise
        
        self.set_output("fires", fireInfo)

