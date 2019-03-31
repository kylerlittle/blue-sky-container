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

from datetime import timedelta
from kernel.core import Process

class Growth(Process):
    def init(self):
        self.declare_input('fires', 'FireInformation')
        self.declare_output('fires', 'FireInformation')

class NoGrowth(Growth):
    _version_ = '1.0.0'

    def run(self, context):
        self.set_output('fires', self.get_input('fires'))

class Persistence(Growth):
    _version_ = '2.0.0'

    def run(self, context):
        fireInfo = self.get_input('fires')

        fire_dict = Persistence._collect_event_locations(fireInfo)
        n_created = self._fill_missing_fires(fire_dict, fireInfo)

        self.log.info('Persistence model created %d new fire records' % n_created)
        self.set_output('fires', fireInfo)

    @staticmethod
    def _collect_event_locations(fireInfo):
        """Collect event locations by unique fire ID"""
        fire_dict = {}
        for fireEvent, fireLoc in fireInfo.iterLocations():
            _id = fireLoc['id']
            if _id not in fire_dict:
                fire_dict[_id] = []
            fire_dict[_id].append((fireEvent, fireLoc))

        return Persistence._sort_fire_events(fire_dict)

    @staticmethod
    def _sort_fire_events(fire_dict):
        """Sort fires (with the same unique ID) by date_time"""
        for fire_locs in fire_dict.values():
            if len(fire_locs) == 1: continue
            fire_locs.sort(key=lambda f: f[1]['date_time'])
        
        return fire_dict

    def _fill_missing_fires(self, fire_dict, fireInfo):
        """Fill-in (persist) that do not extend to the end of the emissions period"""
        n_created = 0

        for fire_locs in fire_dict.values():
            dt = fire_locs[-1][1]['date_time'] + timedelta(days=1)
            while dt <= fireInfo['emissions_end']:
                n_created += 1
                new_loc = fire_locs[-1][1].clone()
                new_loc['date_time'] = dt
                fireInfo.addEventLocation(fire_locs[-1][0], new_loc)
                dt += timedelta(days=1)

        return n_created
