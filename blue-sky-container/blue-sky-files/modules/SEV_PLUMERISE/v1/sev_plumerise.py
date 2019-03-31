#******************************************************************************
#
#  BlueSky Framework - Controls the estimation of emissions, incorporation of
#                      meteorology, and the use of dispersion models to
#                      forecast smoke impacts from fires.
#  Copyright (C) 2003-2006  USDA Forest Service - Pacific Northwest Wildland
#                           Fire Sciences Laboratory
#  Copyright (C) 2007-2009  USDA Forest Service - Pacific Northwest Wildland Fire
#                      Sciences Laboratory and Sonoma Technology, Inc.
#                      All rights reserved.
#
# See LICENSE.TXT for the Software License Agreement governing the use of the
#
# Contributors to the BlueSky Framework are identified in ACKNOWLEDGEMENTS.TXT
#
#******************************************************************************

_bluesky_version_ = "3.5.1"

from plume_rise import PlumeRise
from kernel.types import construct_type
from kernel.bs_datetime import BSDateTime
import math


class SEVPlumeRise(PlumeRise):
    """ SEV Plume Rise Module """

    def init(self):
        self.declare_input("local_met", "LocalMetInformation")
        self.declare_input("fires", "FireInformation")
        self.declare_output("fires", "FireInformation")

    def run(self, context):
        local_met_info = self.get_input("local_met")
        fireInfo = self.get_input("fires")
        self.log.info("Running SEV Plume Rise model")

        all_local_met_locations = local_met_info.locations()

        # loop through all fires
        for fireLoc in fireInfo.locations():
            this_local_met_location = []
            for met_data in all_local_met_locations:
                if met_data['id'] == fireLoc['id']:
                    this_local_met_location.append(met_data)
            this_local_met_location.sort(key=lambda d: d.date_time)

            plume_rise = construct_type("PlumeRise")
            plume_rise.hours = []

            # loop over ordered list of hourly met data
            for met_loc in this_local_met_location:
                if not met_loc.HGTS or not met_loc.RELH or not met_loc.TPOT:
                    continue
                hourly_data = {}
                hourly_data['pressure'] = met_loc.pressure           # mb or hPa
                hourly_data['height'] = met_loc.HGTS                 # m
                hourly_data['relative_humidity'] = met_loc.RELH      # %
                hourly_data['potential_temperature'] = met_loc.TPOT  # Kelvin
                hourly_data['wind_speed'] = met_loc.WSPD             # m/s
                hourly_data['wind_direction'] = met_loc.WDIR         # degrees
                hourly_data['temperature'] = met_loc.TEMP            # Celsius
                hourly_data['press_vertical_v'] = met_loc.WWND       # mb/h
                hourly_data['temp_at_2m'] = met_loc.TO2M             # Kelvin
                hourly_data['rh_at_2m'] = met_loc.RH2M               # %
                hourly_data['accum_precip_3hr'] = met_loc.TPP3       # m
                hourly_data['accum_precip_6hr'] = met_loc.TPP6       # m
                # The met file may spell this variable one of two ways
                pbl = met_loc.HPBL if met_loc.PBLH is None else met_loc.PBLH
                hourly_data['height_abl'] = pbl                      # m

                # Get FRP value (in units of Watts)
                if fireLoc["metadata"] is None or 'frp' not in fireLoc["metadata"].keys():
                    # Default value approximated by averaging the max values here:
                    # http://www.gmes-atmosphere.eu/d/services/gac/nrt/fire_radiative_power
                    hourly_data['frp'] = 4180.8 * fireLoc["area"]
                else:
                    hourly_data['frp'] = float(fireLoc["metadata"]["frp"])
                    if hourly_data['frp'] < 0.0:
                        hourly_data['frp'] = 0.0
                        self.log.info("FRP value was below zero: setting it to zero.")
                fireLoc["metadata"]["frp"] = hourly_data['frp']

                if fireLoc["consumption"] is None or "smoldering" not in fireLoc["consumption"].keys():
                  smolder_fraction = 0.0
                else:
                  smolder_fraction = float(fireLoc["consumption"].get("smoldering", 0.0))

                plume_height = self.cal_smoke_height(hourly_data)
                plume_top_meters = plume_height
                plume_bottom_meters = plume_height * float(self.config("PLUME_BOTTOM_OVER_TOP"))

                plume_rise_hr = construct_type("PlumeRiseHour", smolder_fraction, plume_bottom_meters, plume_top_meters)
                plume_rise.hours.append(plume_rise_hr)

            fireLoc["plume_rise"] = plume_rise

        self.set_output("fires", fireInfo)

    # The two methods below represent all of the science in this model.
    # This master method calculates the height of the top of a smoke plume.
    def cal_smoke_height(self, hourly_data):
        """ Calculate the smoke height. This is the where most of the science happens. """
        alpha = float(self.config("ALPHA"))    # <1, Portion (fraction) of the abl passed freely
        beta = float(self.config("BETA"))      # >0 m, the contribution of fire intensity
        ref_power = float(self.config("REF_POWER"))  # reference fire power, Pf0 in paper
        gamma = float(self.config("GAMMA"))    # <0.5, determines power law dependence on FRP
        delta = float(self.config("DELTA"))    # > or = 0, defines dependence on stability in the free troposphere (FT)
        ref_n = float(self.config("REF_N"))    # Watts, Brunt-Vaisala reference frequency, N0^2 in paper

        nft = self.calc_brunt_vaisala(hourly_data)

        smoke_height = (alpha * float(hourly_data["height_abl"])) \
                       + (beta * math.pow(hourly_data["frp"] / ref_power, gamma)) \
                       * math.exp(-1.0 * delta * ((nft * nft) / ref_n))
        return smoke_height

    def calc_brunt_vaisala(self, hourly_data):
        """ The Brunt-Vaisala Frequency """
        gravity = float(self.config("GRAVITY"))  # m/s^2, gravitational constant

        theta_0 = hourly_data['potential_temperature'][0]
        theta_1 = hourly_data['potential_temperature'][1]

        nft = math.sqrt((gravity * 2) / (theta_0 + theta_1) * abs(theta_1 - theta_0) /
                        (hourly_data['height'][1] - hourly_data['height'][0]))
        return nft
