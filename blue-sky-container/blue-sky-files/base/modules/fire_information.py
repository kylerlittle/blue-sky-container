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

import re
import inspect
from copy import deepcopy
from datetime import timedelta
from kernel.bs_datetime import BSDateTime, utc
from kernel.types import construct_type, is_list_of, get_type_constructor
from kernel.structure import Structure, TemporalStructure
from kernel.config import config
from kernel.log import corelog, SUMMARY

##############################################################################
class FuelsData(Structure):    
    """ Fuels information dictionary """    
    
    def __init__(self, otherdata=None):
        Structure.__init__(self, otherdata)
        self.setdefault("metadata", dict())

##############################################################################
class ConsumptionData(Structure):
    """ Consumption information dictionary """
    
    def __init__(self, otherdata=None):
        Structure.__init__(self, otherdata)

    def flatten(self, **kwargs):
        rowdict = dict()
        for x in self.keys():            
            rowdict["consumption_" + x] = self[x]
        return rowdict
        
##############################################################################
class EmissionsTuple(Structure):
    """ Emissions flaming/smoldering/residual tuple """
    
    def __init__(self, initvalue=None):
        flame, smold, resid = None, None, None
        if isinstance(initvalue, tuple):
            try:
                flame, smold, resid = initvalue
            except:
                pass
        if flame is None:
            Structure.__init__(self, initvalue)
        else:
            Structure.__init__(self)
            self.flame = flame
            self.smold = smold
            self.resid = resid
            
    def __getitem__(self, key):
        if key in (0, 1, 2):
            key = ("flame", "smold", "resid")[key]
        return Structure.__getitem__(self, key)
        
    def __iter__(self):
        for x in ("flame", "smold", "resid"):
            yield self[x]
            
    def sum(self):
        return self.flame + self.smold + self.resid
        
    def flatten(self, **kwargs):
        rowdict = dict()
        for x in ("flame", "smold", "resid"):
            rowdict[x] = self[x]
        rowdict["emitted"] = self.sum()
        return rowdict

##############################################################################
class EmissionsData(TemporalStructure):
    """ Emissions information dictionary """
    
    def __init__(self, otherdata=None):
        TemporalStructure.__init__(self, otherdata)

    def sum(self, key):
        """ If the given key is a list (temporally allocated), return the sum
        of all the values.  Otherwise, just returns the single stored value.
        """
        if self[key] is None:
            return None
        elif is_list_of(EmissionsTuple)(self[key]):
            return sum([tup.sum() for tup in self[key]])
        elif is_list_of(float)(self[key]):
            return sum(self[key])
        else:
            return self[key]
    
    def flatten(self, **kwargs):
        kwargs["alwaysQualify"] = True
        return TemporalStructure.flatten(self, **kwargs)


##############################################################################
class PlumeRise(TemporalStructure):
    """ Plume Rise information dictionary """

    def __init__(self, otherdata=None):
        TemporalStructure.__init__(self, otherdata)

##############################################################################
class TimeProfileData(TemporalStructure):
    """ Time Profile information dictionary """

    def __init__(self, otherdata=None):
        TemporalStructure.__init__(self, otherdata)
        
##############################################################################
class PlumeRiseHour(Structure):
    """ Plume Rise hourly structure """
    
    def __init__(self, otherdata=None, plume_bottom_meters=None, plume_top_meters=None):
        if plume_top_meters is not None and plume_bottom_meters is not None:
            smoldering_fraction = otherdata
            Structure.__init__(self)
            self.smoldering_fraction = smoldering_fraction
            self.percentile_000 = plume_bottom_meters
            self.percentile_100 = plume_top_meters
            
            interp_percentile = lambda p : (plume_bottom_meters + ((plume_top_meters - plume_bottom_meters) / 100.0) * p)
            for p in range(5, 100, 5):
                self["percentile_%03d" % p] = interp_percentile(p)
           
        else:
            Structure.__init__(self, otherdata)
        
##############################################################################
class FireLocationData(TemporalStructure):
    """ Fire information at a single, atomic location """

    def __init__(self, otherdata=None):
        if hasattr(otherdata, 'iteritems') or hasattr(otherdata, 'keys'):
            TemporalStructure.__init__(self, otherdata)
        else:
            TemporalStructure.__init__(self)
            if otherdata is not None:
                self["id"] = otherdata                
            else:
                self["id"] = "UNKNOWN"
        # Clean up ID field.  Removes non-word chars and changes to 
        # all caps.
        self["id"] = re.sub(r"\W+", "", str(self["id"])).upper()
        self.setdefault("metadata", dict())

    def __repr__(self):
        return "<%s>" % self.__str__()

    def __str__(self):
        return "FireLocationData: %s" % self["id"]  
        
    def uniqueid(self):
        if self["date_time"] is None:
            return self["id"]
        run_day = (self["date_time"] - config.get("DEFAULT", "DATE", asType=BSDateTime)).days
        return "%s.%s" % (self['id'], run_day)
    
    def clone(self):
        clone = type(self)(self["id"])
        for k, v in self.iteritems():
            if isinstance(v, Structure):
                value = v.clone()
            elif isinstance(v, dict):
                value = dict(v)
            elif isinstance(v, list):
                value = v[:]
            else:
                value = v
            clone[k] = value
        return clone


##############################################################################
class FireEventData(Structure):
    """ The aggregate of one or more FireLocation instances constituting
        a single event.
    """

    def __init__(self, otherdata=None):
        Structure.__init__(self, otherdata)
        self.setdefault("metadata", dict())
        self.setdefault("fire_locations", list())

    def locations(self):
        """ Return a COPY of the locations in this event 

        This is a safeguard against calling removeLocation() while looping
        over this list.  Because the items in the list are just references to the
        real FireLocationData object instances, this is OK.
        """
        return self.fire_locations[:]    

    def removeLocation(self, locationData):
        """ Remove the given location from this event """
        assert isinstance(locationData, FireLocationData)
        self.fire_locations.remove(locationData)

    def addLocation(self, locationData):
        """ Add the given location to this event. """
        assert isinstance(locationData, FireLocationData)

        # Check to make sure the location isn't already in this event.
        id = locationData["id"]
        dt = locationData["date_time"]
        if not filter(lambda loc: loc["id"] == id and loc["date_time"] == dt, self.fire_locations):
            self.fire_locations.append(locationData)

    def sum(self, key):
        """ Return the sum of the given key for all FireLocationData instances
        in this event.  Note: This will only work for objects for which the 
        addition (+) operator is defined.
        """
        return reduce(lambda x, y: x + y, [loc[key] for loc in self.fire_locations])

##############################################################################
_globalDateInfo = None

class DateInfoStructure(Structure):
    """ Structure that contains date/time information about the current run """
    
    def __init__(self, otherdata=None):
        Structure.__init__(self, otherdata)
        
        if self.start_date is None or self.hours_to_run is None:
            self.getGlobalDateInfo()
        elif any(self[k] is None 
               for k in ("start_date", "hours_to_run", 
                "emissions_offset", "dispersion_offset", 
                "emissions_start", "emissions_end",
                "dispersion_start", "dispersion_end")):
            self.populateDateInfo()

    def populateDateInfo(self):
        dateInfo = dict()
        if self.start_date.tzinfo is None:
            corelog.warn("WARNING: Configured DATE has no associated time zone information")
        start_date = self.start_date.astimezone(utc)
        hours_to_run = self.hours_to_run
        is_emis_spinup = config.get("DEFAULT", "SPIN_UP_EMISSIONS", asType=bool)
        disp_offset = config.get("DEFAULT", "DISPERSION_OFFSET", asType=int)

        if is_emis_spinup:
            emis_offset = disp_offset + config.get("DEFAULT", "EMISSIONS_OFFSET", asType=int)
        else:
            emis_offset = disp_offset
        
        dateInfo["start_date"] = start_date
        dateInfo["hours_to_run"] = hours_to_run
        dateInfo["emissions_offset"] = emis_offset
        dateInfo["dispersion_offset"] = disp_offset
        dateInfo["emissions_start"] = start_date + timedelta(hours=emis_offset)
        dateInfo["emissions_end"] = start_date + timedelta(hours=hours_to_run)
        dateInfo["dispersion_start"] = start_date + timedelta(hours=disp_offset)
        dateInfo["dispersion_end"] = start_date + timedelta(hours=hours_to_run)
        
        self.update(dateInfo)
        return dateInfo
            
    def getGlobalDateInfo(self):
        global _globalDateInfo
        if _globalDateInfo is None:
            dateInfo = dict()
            if self.start_date is None:
                self.start_date = config.get("DEFAULT", "DATE", asType=BSDateTime)
            
            if self.hours_to_run is None:
                self.hours_to_run = config.get("DEFAULT", "HOURS_TO_RUN", asType=int)
            
            dateInfo = self.populateDateInfo()

            corelog.log(SUMMARY, "Emissions period: %s to %s", 
                        dateInfo["emissions_start"].strftime('%Y%m%d %HZ'), 
                        dateInfo["emissions_end"].strftime('%Y%m%d %HZ'))
            corelog.log(SUMMARY, "Dispersion period: %s to %s", 
                        dateInfo["dispersion_start"].strftime('%Y%m%d %HZ'), 
                        dateInfo["dispersion_end"].strftime('%Y%m%d %HZ'))
            
            _globalDateInfo = dateInfo
        self.update(_globalDateInfo)

##############################################################################
class MetInfo(DateInfoStructure):
    """ Structure that contains information about available meteorological data """
    
    def __init__(self, otherdata=None):
        DateInfoStructure.__init__(self, otherdata)
        self.setdefault("files", list())
        self.setdefault("files_nest", list())
        self.setdefault("metadata", dict())
                    
##############################################################################
class FireInformation(DateInfoStructure):
    """ The aggregate of one or more FireLocation or FireEvent instances 
        constituting all the fires within the scope of the current BlueSky run. """

    def __init__(self, otherdata=None):
        DateInfoStructure.__init__(self, otherdata)
        self.setdefault("fire_locations", list())
        self.setdefault("fire_events", list())
        self.setdefault("metadata", dict())

    def set_value(self, k, v, **kwargs):
        found_it = False
        if self.has_key(k):
            if self.type_of(k).isArray:
                if isinstance(v, list):
                    v = [self.type_of(k).itemType.convertValue(vv) for vv in v]
                    self[k] = v
                else:
                    # Subclasses can override to use kwargs here
                    raise ValueError("Unable to assign scalar value to %s array" % k)
            else:
                self[k] = v
            return True
        else:
            # Well, we don't have a key by the given name on this object,
            # but we may be able to set the corresponding value on a subobject
            if self.fire_events is None:
                self.fire_events = list()
            if self.fire_locations is None:
                self.fire_locations = list()
            for dataList, constructor in (
                (self.fire_events, get_type_constructor("FireEventData")), 
                (self.fire_locations, get_type_constructor("FireLocationData"))):
                
                # Construct the subobject if needed
                if len(dataList) == 0:
                    obj = constructor()
                elif len(dataList) == 1:
                    obj = dataList[0]
                else:
                    continue
                # Recursively set the value on the subobject
                found_it = obj.set_value(k, v, **kwargs)
                
                # If we were able to set a value, keep the object
                if found_it and len(dataList) == 0:
                    dataList.append(obj)
                    
                if found_it:
                    return True
                
        # Well, we don't have a key by the given name on this object,
        # but we may be able to set the corresponding value on a subobject
        for key in self.keys():
            cls = self.type_of(key).constructor
            if hasattr(cls, 'validKeyNames'):
                # Clean any prefix off the key name
                if k.startswith(key + "_"):
                    k = k[(len(key) + 1):]
                # Construct the subobject if needed
                if self[key] is None:
                    obj = cls()
                else:
                    obj = self[key]
                # Recursively set the value on the subobject
                found_it = obj.set_value(k, v, **kwargs)
                
                # If we were able to set a value, keep the object
                if found_it:
                    self[key] = obj
                    return True
        return found_it
        
    def addLocation(self, locationData):
        assert isinstance(locationData, FireLocationData)
        self["fire_locations"].append(locationData)

    def addEvent(self, eventData):
        assert isinstance(eventData, FireEventData)
        self["fire_events"].append(eventData)

    def removeLocation(self, locationData):
        assert isinstance(locationData, FireLocationData)
        self["fire_locations"].remove(locationData)

    def removeEvent(self, eventData):
        assert isinstance(eventData, FireEventData)
        self["fire_events"].remove(eventData)
    
    def location(self, fire_id, dt):
        """ Returns the given FireLocationData object (or None)"""
        for loc in self["fire_locations"]:
            if loc["id"] == fire_id and loc["date_time"] == dt:
                return loc
        return None

    def event(self, event_id):
        """ Returns the given FireEventData object (or None)"""
        for e in self["fire_events"]:
            if e["event_id"] == event_id:
                return e
        return None
    
    def events(self):
        """ IMPORTANT: Returns a COPY of the list of events 

        This is a safeguard against calling removeEvent() while looping
        over this list.  Because the items in the list are just references to the
        real FireEventData object instances, this is OK.
        """
        return self["fire_events"][:]
    
    def locations(self):
        """ IMPORTANT: Returns a COPY of the list of locations

        This is a safeguard against calling removeLocation() while looping
        over this list.  Because the items in the list are just references to the
        real FireEventData object instances, this is OK.
        """
        return self["fire_locations"][:]
    
    def iterLocations(self):
        # Build a mapping of location IDs to event IDs
        if len(self["fire_events"]) > 0:
            eventIDs = dict(reduce(lambda a, b: a + b,
                        [[(loc["id"], e["event_id"]) for loc in e.locations()] 
                         for e in self["fire_events"]]))
        else:
            eventIDs = dict()
        
        for fireLoc in self.locations():
            try:
                event = self.event(eventIDs[fireLoc["id"]])
            except:
                event = None
            yield (event, fireLoc)
        
    def addEventLocation(self, fireEvent, fireLoc):
        event = self.event(fireEvent["event_id"])
        if event is None:
            event = construct_type("FireEventData")
            for k in fireEvent.keys():
                event[k] = fireEvent[k]
            self.addEvent(event)
        
        loc = self.location(fireLoc["id"], fireLoc["date_time"])                
        if loc is None:
            event.addLocation(fireLoc)
            self.addLocation(fireLoc)
