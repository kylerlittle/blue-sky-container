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
from cStringIO import StringIO
from kernel.log import corelog
try:
    from SOAPpy import WSDL
    from SOAPpy.Types import faultType
    from SOAPpy.Config import SOAPConfig
except:
    corelog.warn("SOAP interface not found. SMARTFIRE support is not available")
    WSDL = None
from kernel.types import construct_type
from kernel.core import Process
from kernel.bs_datetime import BSDateTime
from datetime import timedelta

def get_smartfire(dt, username, password, info=None):
    if not isinstance(dt, BSDateTime):
        raise ValueError("Expected BSDateTime object, got " + type(dt))
    if info is None:
        info = construct_type("FireInformation")
        
    if WSDL is None:
        return info, 0

    saved_stdout = sys.stdout
    try:
        sys.stdout = StringIO()
        smartfire = WSDL.Proxy("http://www.getbluesky.org/smartfire/smartfire.wsdl", config=SOAPConfig(dumpFaultInfo=0))
        soapdata = smartfire.getBlueSkyBurnsByDate(username, password, dt.strftime("%Y%m%d"))
    finally:
        sys.stdout = saved_stdout
    
    data = []
    num_fires = len(soapdata)
    for i in range(num_fires):
        dataobj = soapdata[i][0]
        row = dict([(r.key, r.value) for r in dataobj])
        data += [row]
    
    eventIDs = sorted(set([row["EVENT_ID"] for row in data]))
    for eventID in eventIDs:
        rows = [row for row in data if row["EVENT_ID"]==eventID]
        
        event = construct_type("FireEventData")
        event["event_id"] = str(eventID)
        event["event_name"] = rows[0]["EVENT_NAME"]
        info.addEvent(event)
        
        for row in rows:

            fireID = row["PERIMETER_ID"]
                
            # Make a new FireLocationData object to hold the data from this row
            loc = construct_type("FireLocationData", fireID)
    
            # Set the standard fields            
            loc["owner"] = None
            loc["latitude"] = float(row["LATITUDE"])
            loc["longitude"] = float(row["LONGITUDE"])
            loc["elevation"] = None
            loc["slope"] = None
            loc["state"] = row["STATE"]
            if isinstance(row["COUNTY"], unicode):
                loc["county"] = row["COUNTY"].encode("ascii", "replace")
            else:
                loc["county"] = row["COUNTY"]
            loc["country"] = row["COUNTRY"]
            loc["fips"] = row["FIPS"]
            
            dt = BSDateTime.strptime(row["DATE_TIME"] + "0900", "%Y%m%d%H%M", tzinfo=None)
            loc["date_time"] = dt

            loc["type"] = row["TYPE"]
            
            area_meters = float(row["AREA_METERS"])
            # According to Google Calculator, 1 square meter = 0.000247105381 acres
            area_acres = area_meters * 0.000247105381
            loc["area"] = area_acres
            
            loc["time_profile"] = None
            loc["fuels"] = None
            loc["consumption"] = None
            loc["emissions"] = None
    
            # Set additional metadata
            loc["metadata"]["fuel_model"] = row["FUEL_MODEL"]
            loc["metadata"]["growth_potential"] = row["GROWTH_POTENTIAL"]
            loc["metadata"]["percent_contained"] = row["PERCENT_CONTAINED"]
            loc["metadata"]["percent_or_mma"] = row["PERCENT_OR_MMA"]
            
            # Note: This is commented out now as well.  See burn_data.py for how
            #       to extract this without using metadata.
            #loc["metadata"]["event_id"] = str(eventID)
            
            # Note: I've commented this out for now.  The OBJECTID is useless
            #       unless you're trying to debug the actual SMARTFIRE
            #       PredictionAlgorithm.  The PERIMETER_ID is a far more 
            #       useful value, and we preserve that as the FireLocation's
            #       ID field.
            #loc["metadata"]["smartfire_objectid"] = row["OBJECTID"]
            
            # Add this location into the structure
            event.addLocation(loc)
            info.addLocation(loc)
            
    return info, num_fires

class InputSMARTFIRE(Process):
    _version_ = "1.0.0"

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
            if username is None:
                sys.stderr.write('Need username for SMARTFIRE user\n')
                username = raw_input('Username: ')
            if password is None:
                sys.stderr.write('Need password for SMARTFIRE user "%s"\n' % username)
                password = getpass.getpass()
            
            num_fires = 0
            date = fireInfo["emissions_start"]
            while date < fireInfo["emissions_end"]:
                self.log.info("Downloading fire data for %s from SMARTFIRE...", date.strftime('%Y-%m-%d'))
                fireInfo, nFires = get_smartfire(date, username, password, fireInfo)
                num_fires += nFires
                date += timedelta(days=1)
                
        except KeyboardInterrupt:
            if self.config("ERROR_ON_ZERO_FIRES", bool) and len(fireInfo.locations()) == 0:
                raise
            num_fires = 0
        except faultType, e:
            if(len(e) > 1 and "Invalid username or password" in e[1]):
                self.log.warn("Error retrieving data from SMARTFIRE:\n>>> Invalid username or password")
                self.log.info("For more information, see http://www.getbluesky.org/smartfire/")
                if self.config("ERROR_ON_ZERO_FIRES", bool) and len(fireInfo.locations()) == 0:
                    raise Exception("Invalid username or password for SMARTFIRE web service")   
            else:
                self.log.warn("Error retrieving data from SMARTFIRE: %s", e[0])
                self.log.warn("SMARTFIRE Error: %s", e[1])
                self.log.info("For more information, see http://www.getbluesky.org/smartfire/")
            num_fires = 0

        if num_fires == 0 and len(fireInfo.locations()) == 0:
            if self.config("ERROR_ON_ZERO_FIRES", bool):
                raise Exception("SMARTFIRE web service returned zero fires")
            elif self.config("WARN_ON_ZERO_FIRES", bool):
                self.log.warn("SMARTFIRE web service returned zero fires")
        self.log.info("Successfully downloaded data for %s fire locations", num_fires)
        self.set_output("fires", fireInfo)

__all__ = ["InputSMARTFIRE", "get_smartfire"]
