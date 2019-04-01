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

import sys
from cStringIO import StringIO
from kernel.log import corelog

import urllib
import csv

from kernel.types import construct_type
from kernel.core import Process
from kernel.bs_datetime import BSDateTime
from datetime import timedelta


def get_smartfire2(Process, dt, url, stream, export, min_area, info=None):
    if not isinstance(dt, BSDateTime):
        raise ValueError("Expected BSDateTime object, got " + type(dt))
    if info is None:
        info = construct_type("FireInformation")

    # connect to SF2 and download stream
    # url looks like this: http://playground.dri.edu/smartfire/streams/realtime/20130701/blueskycsv
    sf2_url = "%s/streams/%s/%s/%s" % (url, stream, dt.strftime("%Y%m%d"), export)
    try:
        f = urllib.urlopen(sf2_url)
    except:
        Process.log.warn("Error retrieving data from SmartFire2: %s", sys.exc_info()[0])
        Process.log.warn("SmartFire2 Error: %s", sys.exc_info()[1])
        Process.log.info("For more information, see http://smartfire.sonomatechdata.com/")
        num_fires = 0
        return info, num_fires

    d = csv.DictReader(f)
    data = []
    for row in d:
        data.append(row)

    # Construct the event first
    eventIDs = sorted(set([row["event_id"] for row in data]))
    num_events = len(eventIDs)
    num_fires = 0

    for eventID in eventIDs:
        rows = [row for row in data if row['event_id']==eventID]

        event = construct_type("FireEventData")
        event["event_id"] = str(eventID)
        event["event_name"] = rows[0]["event_name"]
        event["metadata"]["event_url"] = rows[0]["event_url"]
        info.addEvent(event)

        for row in rows:
            fireID = row['id']

            # TODO: need to confirm proper time zone handling here
            try:
                #dt = BSDateTime.strptime(row["date_time"][:16], "%Y-%m-%dT%H:%M", tzinfo=None)
                dt = BSDateTime.bs_strptime(row["date_time"])
            except:
                Process.log.warn('Error parsing date for id:%s', fireID)
                Process.log.warn('Skipping...')
                continue

            # Check area is above minimum size
            if float(row["area"]) <= float(min_area):
                Process.log.warn('Fire area: %s is below the minimum (%s acres) for id:%s', row["area"], min_area, fireID)
                Process.log.warn('Skipping...')
                continue

            # Make a new FireLocationData object to hold the data from this row
            loc = construct_type("FireLocationData", fireID)

            # Set the standard fields SF2 is guaranteed to have
            loc["latitude"] = float(row["latitude"])
            loc["longitude"] = float(row["longitude"])

            loc["date_time"] = dt
            loc["type"] = row["type"]
            loc["area"] = row["area"]
            loc["metadata"]["event_url"] = row["event_url"]

            # Set the other fields that SF2 might have
            for key in ["owner", "fips", "state", "county", "country", "scc"]:
                if row.has_key(key):
                    loc[key] = row[key]
            for key in ["elevation", "slope"]:
                if row.has_key(key):
                    loc[key] = float(row.get(key))
                else:
                    loc[key] = None

            # Add data for fuels objects
            if row.has_key("fuel_1hr"):
                fuels = construct_type("FuelsData")
                fuels[fuel_1hr] = float(row["fuel_1hr"])
                for key in ["fuel_10hr", "fuel_100hr", "fuel_1khr", "fuel_10khr",
                            "fuel_gt10khr", "shrub", "grass", "rot", "duff",
                            "litter", "canopy"]:
                    fuels[key] = float(row.get(key, 0.0))
                loc["fuels"] = fuels
            else:
                loc["fuels"] = None

            # Add data for consumption objects
            if row.has_key("consumption_flaming"):
                cons = construct_type("ConsumptionData")
                cons["flaming"] = float(row["consumption_flaming"])
                for key in ["consumption_smoldering", "consumption_residual", "consumption_duff"]:
                    cons[key[12:]] = float(row.get(key, 0.0))
                loc["consumption"] = cons
            else:
                loc["consumption"] = None

            # We don't expect emissions or time profile from SF2
            loc["time_profile"] = None
            loc["emissions"] = None

            # check the dictionaries for list of keys
            keysList = []
            for item in (event.keys()+loc.keys()): keysList.append(item)
            if loc["fuels"]:
                for item in loc["fuels"].keys(): keysList.append(item)
            if loc["consumption"]:
                for item in loc["consumption"].keys(): keysList.append("consumption_" + item)
            if loc["metadata"]:
                for item in loc["metadata"].keys(): keysList.append(item)
                
            # assign remaining fields to metadata
            for key in row.keys():
                if key in set(keysList): continue
                else: loc["metadata"]["sf_" + str(key)] = row[key]

            # Add this location into the structure
            num_fires += 1
            event.addLocation(loc)
            info.addLocation(loc)

        if len(event.locations()) < 1:
            info.removeEvent(event)

    f.close()
    return info, num_fires


class InputSmartFire2(Process):
    _version_ = "1.0.0"

    def init(self):
        self.declare_input("fires", "FireInformation")
        self.declare_output("fires", "FireInformation", cache=False)

    def run(self, context):
        fireInfo = self.get_input("fires")
        if fireInfo is None:
            fireInfo = construct_type("FireInformation")
        try:
            stream = self.config("STREAM")
            url = self.config("URL")
            export = self.config("EXPORT")
            min_area = self.config("MINIMUM_AREA")

            num_fires = 0
            date = fireInfo["emissions_start"]
            while date < fireInfo["emissions_end"]:
                self.log.info("Downloading fire data for %s from SmartFire2...", date.strftime('%Y-%m-%d'))
                fireInfo, nFires = get_smartfire2(self, date, url, stream, export, min_area, fireInfo)
                num_fires += nFires
                date += timedelta(days=1)

        except KeyboardInterrupt:
            if self.config("ERROR_ON_ZERO_FIRES", bool) and len(fireInfo.locations()) == 0:
                raise
            num_fires = 0
        except:
            self.log.warn("Error retrieving data from SmartFire2: %s", sys.exc_info()[0])
            self.log.warn("SmartFire2 Error: %s", sys.exc_info()[1])
            self.log.info("For more information, see http://smartfire.sonomatechdata.com/")
            num_fires = 0

        if num_fires == 0 and len(fireInfo.locations()) == 0:
            if self.config("ERROR_ON_ZERO_FIRES", bool):
                raise Exception("SmartFire2 request returned zero fires")
            elif self.config("WARN_ON_ZERO_FIRES", bool):
                self.log.warn("SmartFire2 request returned zero fires")
        self.log.info("Successfully downloaded data for %s fire locations", num_fires)
        self.set_output("fires", fireInfo)


__all__ = ["InputSmartFire2", "get_smartfire2"]
