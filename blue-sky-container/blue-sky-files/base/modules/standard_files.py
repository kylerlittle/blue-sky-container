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

import csv
import os
import sys
import shutil
from kernel.core import Process
from kernel.bs_datetime import BSDateTime, timedelta
from kernel.utility import put

from kernel.types import construct_type, get_type_constructor
EmissionsTuple = get_type_constructor("EmissionsTuple")
EmissionsData = get_type_constructor("EmissionsData")
ConsumptionData = get_type_constructor("ConsumptionData")

    
class OutputStandardFiles(Process):
    """ Output fire information in BlueSky standard CSV format """

    def init(self):
        self.declare_input("fires", "FireInformation")
        #self.declare_output("fires", "FireInformation", cache=False)

    def run(self, context):
        self.write_standard_files()

        # Pass-through data
        #self.set_output("fires", self.get_input("fires"))
        
    def get_filenames(self):
        date = self.config("DATE", BSDateTime)

        locations_filename = os.path.join(
            self.config("OUTPUT_DIR"), 
            self.config("LOCATIONS_FILE"))
        if "%" in locations_filename:
            locations_filename = date.strftime(locations_filename)

        events_filename = os.path.join(
            self.config("OUTPUT_DIR"), 
            self.config("EVENTS_FILE"))
        if "%" in events_filename:
            events_filename = date.strftime(events_filename)
                        
        hourly_filename = os.path.join(
            self.config("OUTPUT_DIR"), 
            self.config("HOURLY_FILE"))
        if "%" in hourly_filename:
            hourly_filename = date.strftime(hourly_filename)
        
        dispersion_filename = os.path.join(
            self.config("OUTPUT_DIR"),
            self.config("DISPERSION_FILE"))
        if "%" in dispersion_filename:
            dispersion_filename = date.strftime(dispersion_filename)
        
        return events_filename, locations_filename, hourly_filename, dispersion_filename
    
    def get_events_table(self, fireInfo):
        table = list()
        for event in fireInfo.events():
            rowdict = dict()
            rowdict["id"] = event["event_id"]
            rowdict["total_area"] = event.sum("area")
            for param in EmissionsData.validKeyNames:
                if param == "time": continue
                rowdict["total_" + param] = sum(
                    L.emissions.sum(param) 
                    for L in event.locations() 
                    if L.emissions is not None
                    and L.emissions[param] is not None)
            rowdict["event_name"] = event["event_name"]
            table.append(rowdict)
        return table
    
    def get_locations_table(self, fireInfo):
        # Build a mapping of location IDs to event IDs
        if len(fireInfo.events()) > 0:
            eventIDs = dict(reduce(lambda a, b: a + b,
                        [ [(loc["id"], e["event_id"]) for loc in e.locations()] 
                         for e in fireInfo.events() ]))
        else:
            eventIDs = dict()
    
        table = list()
        for loc in fireInfo.locations():        
            # Call FireLocation.flatten() to build the row
            rowdict = loc.flatten(hour=None)
            
            # Look up the event_id and add it to the row
            try:
                rowdict["event_id"] = eventIDs[loc["id"]]
            except KeyError:
                pass

            # Add total emissions columns
            if loc.emissions is not None:
                for param in EmissionsData.validKeyNames:
                    if param == "time": continue
                    if loc.emissions[param] is not None:
                        rowdict[param] = loc.emissions.sum(param) 
                    
            table.append(rowdict)
        return table
    
    def get_hourly_table(self, fireInfo):
        table = list()
        for fireLoc in fireInfo.locations():
            if fireLoc["time_profile"] is None:
                self.log.debug("%s has no time_profile" % fireLoc)
                continue
            
            for hour in range(len(fireLoc["time_profile"]["area_fract"])):
                rowdict = dict()
                
                # Populate some additional fields for the hourly table
                rowdict["fire_id"] = fireLoc["id"]
                rowdict["ignition_date_time"] = fireLoc["date_time"].bs_strftime()
                rowdict["date_time"] = (fireLoc["date_time"] + timedelta(hours=hour)).bs_strftime()
                rowdict["hour"] = hour
                
                # Copy the hourly data from the sub-objects
                subrow = fireLoc.flatten(hour=hour)
                if "time" in subrow:
                    subrow.pop("time")
                rowdict.update(subrow)
                
                table.append(rowdict)
        return table
        
    def sort_table(self, table, sort_by):
        for sortopt in reversed(sort_by.split(',')):
            sortopt = sortopt.split()
            sort_field = sortopt[0]
            reverse = False
            if len(sortopt) == 2:
                sort_dir = sortopt[1].lower()
                if sort_dir == 'desc':
                    reverse = True
                elif sort_dir != 'asc':
                    raise ValueError("Unexpected sort order in sort_by clause")
            elif len(sortopt) > 2:
                raise ValueError("Unexpected white space in sort_by clause")
            
            sort_key = lambda o: o[sort_field]
            table.sort(key=sort_key, reverse=reverse)
        return None # table has been mutated in place
                
        
    def write_table(self, filename, table, keyseq):
        # Build keys dict (for header line)
        keys = set()
        for row in table:
            keys.update(row.keys())
        sort_keys = sorted(keys)
        sort_keys.sort(key=lambda k: k not in keyseq and 9999 or keyseq.index(k))
        
        # Open a DictWriter to write the CSV file
        f = open(filename, "wb")
        writer = csv.DictWriter(f, sort_keys)
        
        # Write header line
        writer.writerow(dict(zip(sort_keys, sort_keys)))
        
        # Write table data
        writer.writerows(table)
        
        # Clean up
        f.close()
    
    def write_standard_files(self):
        events_filename, locations_filename, hourly_filename, dispersion_filename = self.get_filenames()
        fireInfo = self.get_input("fires")
        
        self.log.info("Writing fire locations to standard format file")
        
        events_table = self.get_events_table(fireInfo)
        if len(events_table) > 0:
            self.sort_table(events_table, self.config("EVENTS_SORT_BY"))
            self.write_table(events_filename, events_table, STANDARD_EVENTS_KEYS)

        loc_table = self.get_locations_table(fireInfo)
        self.sort_table(loc_table, self.config("LOCATIONS_SORT_BY"))
        self.write_table(locations_filename, loc_table, STANDARD_LOCATIONS_KEYS)
                
        hourly_table = self.get_hourly_table(fireInfo)
        if len(hourly_table) > 0:
            self.sort_table(hourly_table, self.config("HOURLY_SORT_BY"))
            self.write_table(hourly_filename, hourly_table, STANDARD_HOURLY_KEYS)
        
        self.log.info("Successfully wrote %d fire locations", len(loc_table))
        
        if fireInfo.dispersion is not None:
            netcdf_file = fireInfo.dispersion.grid_filename
            shutil.copy(netcdf_file, dispersion_filename)
        

###############################################################################
# Standard keys for standard files
# These lists define the standard order that fields should appear in output
# files.  The set of actual keys that are output may be a subset (if the 
# corresponding value never appears in the output table) or a superset (if
# metadata keys are being used).

STANDARD_EVENTS_KEYS = ["id", "event_name", "total_area", "total_heat", 
                        "total_pm25", "total_pm10", "total_pm", "total_co", 
                        "total_co2", "total_ch4", "total_nmhc", "total_nox", 
                        "total_nh3", "total_so2", "total_voc"]
                        
STANDARD_LOCATIONS_KEYS = ["id", "event_id", "latitude", "longitude", "type", "area",
                           "date_time", "elevation", "slope", "state", "county", 
                           "country", "fips", "scc", "fuel_1hr", 
                           "fuel_10hr", "fuel_100hr", "fuel_1khr", 
                           "fuel_10khr", "fuel_gt10khr", "shrub", "grass", 
                           "rot", "duff", "litter", "moisture_1hr", "moisture_10hr", 
                           "moisture_100hr", "moisture_1khr", "moisture_live",
                           "moisture_duff", "consumption_flaming", 
                           "consumption_smoldering", "consumption_residual", 
                           "consumption_duff", "min_wind", "max_wind", 
                           "min_wind_aloft", "max_wind_aloft", "min_humid", 
                           "max_humid", "min_temp", "max_temp", "min_temp_hour", 
                           "max_temp_hour", "sunrise_hour", "sunset_hour", 
                           "snow_month", "rain_days", "heat", "pm25", "pm10", "pm", 
                           "co", "co2", "ch4", "nmhc", "nox", "nh3", "so2",
                           "voc"]

STANDARD_HOURLY_KEYS = ["fire_id", "hour", "ignition_date_time", "date_time",
                        "area_fract", "flame_profile",
                        "smolder_profile", "residual_profile",
                        "heat_emitted", "pm25_emitted", "pm10_emitted", 
                        "pm_emitted", "co_emitted", "co2_emitted", 
                        "ch4_emitted", "nmhc_emitted", "nox_emitted", 
                        "nh3_emitted", "so2_emitted", "voc_emitted",
                        "pm25_flame", "pm10_flame", 
                        "pm_flame", "co_flame", "co2_flame", 
                        "ch4_flame", "nmhc_flame", "nox_flame", 
                        "nh3_flame", "so2_flame", "voc_flame",
                        "pm25_smold", "pm10_smold", 
                        "pm_smold", "co_smold", "co2_smold", 
                        "ch4_smold", "nmhc_smold", "nox_smold", 
                        "nh3_smold", "so2_smold", "voc_smold",
                        "pm25_resid", "pm10_resid", 
                        "pm_resid", "co_resid", "co2_resid", 
                        "ch4_resid", "nmhc_resid", "nox_resid", 
                        "nh3_resid", "so2_resid", "voc_resid",
                        "smoldering_fraction", "plume_bottom_meters",
                        "plume_top_meters"]
                        
###############################################################################

class InputStandardFiles(Process):
    """ Read fire information from BlueSky standard CSV format """
    def init(self):
        self.declare_input("fires", "FireInformation")
        self.declare_output("fires", "FireInformation", cache=False)

    def run(self, context):
        fireInfo = self.get_input("fires")
        if fireInfo is None:
            fireInfo = construct_type("FireInformation")
        
        input_files = self.get_input_files(fireInfo)
        
        for fileInfo in input_files:
            eventFile = fileInfo["events_filename"]
            locFile = fileInfo["locations_filename"]
            hourlyFile = fileInfo["hourly_filename"]
            
            self.read_fire_locations(locFile, fireInfo)
            if eventFile is not None:
                self.read_fire_events(eventFile, fireInfo)
            if hourlyFile is not None:
                self.read_fire_hourly(hourlyFile, fireInfo)

        self.set_output("fires", fireInfo)
        
    def get_input_files(self, fireInfo):
        inputFiles = list()
        
        if self.config("USE_DAILY_FILE_PATTERNS", asType=bool):
            eventspattern = self.config("EVENTS_PATTERN")
            locationspattern = self.config("LOCATIONS_PATTERN")
            hourlypattern = self.config("HOURLY_PATTERN")
            
            date = fireInfo["emissions_start"]
            while date < fireInfo["emissions_end"]:
                f = date.strftime(locationspattern)
                if os.path.exists(f):
                    info = construct_type("InputFileInfo")
                    info["locations_filename"] = f
                    
                    f = date.strftime(eventspattern)
                    if os.path.exists(f):
                        info["events_filename"] = f
                        
                    f = date.strftime(hourlypattern)
                    if os.path.exists(f):
                        info["hourly_filename"] = f
                    
                    inputFiles.append(info)
                date += timedelta(days=1)
                
        else:
            inputDir = self.config("INPUT_DIR")
            eventsfile = self.config("EVENTS_FILE")
            locationsfile = self.config("LOCATIONS_FILE")
            hourlyfile = self.config("HOURLY_FILE")
            
            f = os.path.join(inputDir, locationsfile)
            if os.path.exists(f):
                info = construct_type("InputFileInfo")
                info.locations_filename = f
                
                f = os.path.join(inputDir, eventsfile)
                if os.path.exists(f):
                    info.events_filename = f
                    
                f = os.path.join(inputDir, hourlyfile)
                if os.path.exists(f):
                    info.hourly_filename = f
                
                inputFiles.append(info)
            
        return inputFiles

    def check_record(self, record, required_keys):
        # Convert all keys to lowercase
        for k in record.keys():
            v = record[k]
            new_k = k.lower()
            del record[k]
            if v != "":
                record[new_k] = v
        for k in required_keys:
            assert k in record, 'Record does not contain value for "%s", which is required' % k
        return record
        
    def read_fire_events(self, events_filename, fireInfo):
        self.log.info("Reading fire events from standard format file")
        event_special_keys = ["id", "event_name"]
        num_events = 0
        f = open(events_filename, "rb")
        for row in csv.DictReader(f):
            row = self.check_record(row, event_special_keys)
            try:
                event_id = row["id"]
                num_events += 1

                fireEvent = fireInfo.event(event_id)
                if fireEvent is None:
                    fireEvent = construct_type("FireEventData")
                    fireEvent["event_id"] = event_id
                    fireInfo.addEvent(fireEvent)
                fireEvent["event_name"] = row["event_name"]

                for (key, value) in row.iteritems():
                    if key in event_special_keys:
                        continue
                    fireEvent["metadata"][key] = value
        
            except StandardError, err:
                self.log.warn("WARNING: %s %s", type(err), err)
        f.close()
        self.log.info("Successfully read %d fire events", num_events)
    
    def read_fire_locations(self, locations_filename, fireInfo):
        self.log.info("Reading fire locations from standard format file")
        num_fires = 0
        
        f = open(locations_filename, "rb")
        for row in csv.DictReader(f):
            try:
                row = self.check_record(row, ["id", "latitude", "longitude", "date_time", "area"])
                
                num_fires += 1
                fireLoc = construct_type("FireLocationData", (row["id"]))
                
                # Populate the FireLocationData object
                for k, v in row.iteritems():
                    # Treat date_time as a special case.  This is the only time that we consider
                    # date/time strings with no suffix to be local time, not UTC.
                    if k == "date_time":
                        fireLoc["date_time"] = BSDateTime.bs_strptime(row["date_time"], tzinfo=None)
                        continue
                    
                    # Skip event_id (we will handle it separately below)
                    if k == "event_id":
                        continue
                        
                    # Skip emissions totals
                    if k in EmissionsData.validKeyNames:
                        continue
                        
                    # Try to set the value into an object field; if we can't, it's metadata
                    found_it = fireLoc.set_value(k, v, hour=None)
                    if not found_it:
                        self.log.debug('Unable to set value for "%s" field, assuming it is metadata', k)
                        fireLoc.metadata[k] = v
                
                # Add our new location to the FireInformation object
                fireInfo.addLocation(fireLoc)
                
                # Look up the corresponding event and add this location to it
                if "event_id" in row:
                    try:
                        event = (e for e in fireInfo.events() if e["event_id"] == row["event_id"]).next()
                    except StopIteration:
                        event = construct_type("FireEventData")
                        event["event_id"] = row["event_id"]
                        fireInfo.addEvent(event)
                else:
                    event = construct_type("FireEventData")
                    event["event_id"] = row["id"]
                    fireInfo.addEvent(event)
                    
                event.addLocation(fireLoc)
            except StandardError, err:
                self.log.warn("WARNING: %s %s", type(err), err)
        f.close()
        self.log.info("Successfully read %d fire locations", num_fires)
        
    def read_fire_hourly(self, hourly_filename, fireInfo):
        self.log.info("Reading hourly fire data from standard format file")
        hourly_special_keys = ["fire_id", "hour", "ignition_date_time"]
        f = open(hourly_filename, "rb")
        unmatched_locs = set()
        matched_locs = set()
        countRecs = 0
        for row in csv.DictReader(f):
            row = self.check_record(row, hourly_special_keys)
            try:
                fire_id = row["fire_id"]
                hour = int(row["hour"])
                fire_dt = BSDateTime.bs_strptime(row["ignition_date_time"], tzinfo=None)
                
                fireLoc = fireInfo.location(fire_id, fire_dt)
                if fireLoc is None:
                    unmatched_locs.add((fire_id, fire_dt))
                    continue
                matched_locs.add(fireLoc)
                countRecs += 1
                self.log.debug("Setting values for %s hour %d", fire_id, hour)
                
                # Populate the FireLocationData object
                for k, v in row.iteritems():
                    if k in ("height_abl", "temperature_2"):
                        continue
                    if k in hourly_special_keys:
                        continue
                    if k == "date_time":
                        continue
                    if k.endswith('_emitted'):
                        continue
                    if not fireLoc.set_value(k, v, hour=hour):
                        self.log.warn('Unable to set value for "%s" field', k)
                    
            except StandardError, err:
                self.log.warn("WARNING: %s %s", type(err), err)
                
        f.close()
        
        for fire_id, fire_dt in unmatched_locs:
            self.log.warn('WARNING: No FireLocation with ID "%s" ignited at %s; ignoring', fire_id, fire_dt.bs_strftime())
        self.log.info("Read %d records of hourly data for %d fires", countRecs, len(matched_locs))
            
