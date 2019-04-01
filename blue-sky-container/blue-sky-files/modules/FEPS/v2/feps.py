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

from consumption import Consumption
from emissions import Emissions
from time_profile import TimeProfile
from plume_rise import PlumeRise

from kernel.types import construct_type
from kernel.bs_datetime import BSDateTime
import csv
from datetime import timedelta

# Setup the array that defines percentage of acres burned per hour for a
# wildfire.  The array goes from midnight (hr 0) to 11 pm local time, in
# decimal %, and total = 1.0.
# Data from the Air Sciences Report to the WRAP. "Integrated Assessment Update
# and 2018 Emissions Inventory for Prescribed Fire, Wildfire, and Agricultural
# Burning."
WRAP_TIME_PROFILE = [ 0.0057, 0.0057, 0.0057, 0.0057, 0.0057, 0.0057,
                    0.0057, 0.0057, 0.0057, 0.0057, 0.0200, 0.0400,
                    0.0700, 0.1000, 0.1300, 0.1600, 0.1700, 0.1200,
                    0.0700, 0.0400, 0.0057, 0.0057, 0.0057, 0.0057 ]

class FEPSConsumption(Consumption):
    """ FEPS Consumption Module """

    def run(self, context):
        fireInfo = self.get_input("fires")
        FEPS_CONSUMPTION = self.config("FEPS_CONSUMPTION_BINARY")

        self.log.info("Running FEPS Consumption model")

        for fireLoc in fireInfo.locations():
            if fireLoc["consumption"] is not None:
                self.log.debug("Skipping %s because it already has consumption data" % fireLoc["id"])
                continue

            if fireLoc["fuels"] is None:
                self.log.debug("Fire %s has no fuel loading; skip...", fireLoc["id"])
                continue

            context.push_dir(fireLoc.uniqueid())

            fuelsFile = context.full_path("fuels.txt")
            consumptionFile = context.full_path("cons.txt")
            context.archive_file(fuelsFile)
            context.archive_file(consumptionFile)

            self.writeFuels(fireLoc, fuelsFile)
            context.execute(FEPS_CONSUMPTION,
                            "-f", fuelsFile,
                            "-o", consumptionFile)
            consumption = self.readConsumption(consumptionFile)

            fireLoc["consumption"] = consumption

            context.pop_dir()

        self.set_output("fires", fireInfo)

    def writeFuels(self, fireLoc, fuelsFile):
        val = lambda x : (fireLoc["fuels"][x] and [float(fireLoc["fuels"][x])] or [0.0])[0]
        woody = sum((fireLoc["fuels"]["fuel_1hr"],
                    fireLoc["fuels"]["fuel_10hr"],
                    fireLoc["fuels"]["fuel_100hr"],
                    fireLoc["fuels"]["fuel_1khr"],
                    fireLoc["fuels"]["fuel_10khr"],
                    fireLoc["fuels"]["fuel_gt10khr"]))
        if fireLoc['type'] in ('WF', 'WFU', 'Unknown'):
            canopyFlag = 1
        else:
            canopyFlag = 0
        f = open(fuelsFile, 'w')
        f.write("canopy=%f\n" % val("canopy"))
        f.write("shrub=%f\n" % val("shrub"))
        f.write("grassy=%f\n" % val("grass"))
        f.write("woody=%f\n" % woody)
        f.write("litter=%f\n" % val("litter"))
        f.write("scattered=0\n")
        f.write("piled=0\n")
        f.write("duff=%f\n" % val("duff"))
        f.write("moist_duff=%f\n" % fireLoc.fuel_moisture.moisture_duff)
        f.write("canopy_flag=%f\n" % 1)
        f.close()

    def readConsumption(self, consumptionFile):
        data = dict()
        f = open(consumptionFile, 'r')
        for line in f:
            key, val = line.split('=')
            data[key] = val
        f.close()

        cons = construct_type("ConsumptionData")

        cons["flaming"] = float(data["cons_flm"])
        cons["smoldering"] = float(data["cons_sts"])
        cons["residual"] = float(data["cons_lts"])
        cons["duff"] = float(data["cons_duff"])

        return cons


def getDiurnalFile(self, context, fireLoc):
    FEPS_WEATHER = self.config("FEPS_WEATHER_BINARY")
    if "extra:diurnal_file" in fireLoc["metadata"]:
        diurnalFile = fireLoc["metadata"]["extra:diurnal_file"]
    else:
        weatherFile = context.full_path("weather.txt")
        diurnalFile = context.full_path("diurnal.txt")
        context.archive_file(weatherFile)
        context.archive_file(diurnalFile)
        f = open(weatherFile, 'w')
        f.write("sunsetTime=%d\n" % fireLoc.local_weather.sunset_hour)  # Time of sun set
        f.write("middayTime=%d\n" % fireLoc.local_weather.max_temp_hour)  # Time of max temp
        f.write("predawnTime=%d\n" % fireLoc.local_weather.min_temp_hour)   # Time of min temp
        f.write("minHumid=%f\n" % fireLoc.local_weather.min_humid)  # Min humid
        f.write("maxHumid=%f\n" % fireLoc.local_weather.max_humid)  # Max humid
        f.write("minTemp=%f\n" % fireLoc.local_weather.min_temp)  # Min temp
        f.write("maxTemp=%f\n" % fireLoc.local_weather.max_temp)  # Max temp
        f.write("minWindAtFlame=%f\n" % fireLoc.local_weather.min_wind) # Min wind at flame height
        f.write("maxWindAtFlame=%f\n" % fireLoc.local_weather.max_wind) # Max wind at flame height
        f.write("minWindAloft=%f\n" % fireLoc.local_weather.min_wind_aloft) # Min transport wind aloft
        f.write("maxWindAloft=%f\n" % fireLoc.local_weather.max_wind_aloft) # Max transport wind aloft
        f.close()
        context.execute(FEPS_WEATHER,
                        "-w", weatherFile,
                        "-o", diurnalFile)
        fireLoc["metadata"]["extra:diurnal_file"] = diurnalFile
    return diurnalFile


def getPlumeFile(self, context, fireLoc):
    FEPS_PLUMERISE = self.config("FEPS_PLUMERISE_BINARY")
    if "extra:plume_file" in fireLoc["metadata"]:
        plumeFile = fireLoc["metadata"]["extra:plume_file"]
    else:
        profileFile = context.full_path("profile.txt")
        consumptionFile = context.full_path("cons.txt")
        plumeFile = context.full_path("plume.txt")
        context.archive_file(profileFile)
        context.archive_file(plumeFile)

        diurnalFile = getDiurnalFile(self, context, fireLoc)

        # TODO: This is rather hackish... is there a better way?
        self.writeProfile(fireLoc, profileFile)
        self.writeConsumption(fireLoc, consumptionFile)

        context.execute(FEPS_PLUMERISE,
                        "-w", diurnalFile,
                        "-p", profileFile,
                        "-c", consumptionFile,
                        "-a", str(fireLoc["area"]),
                        "-o", plumeFile)
        fireLoc["metadata"]["extra:plume_file"] = plumeFile
    return plumeFile


class FEPSTimeProfile(TimeProfile):
    """ FEPS Time Profile Module """

    def run(self, context):
        fireInfo = self.get_input("fires")
        FEPS_WEATHER = self.config("FEPS_WEATHER_BINARY")
        FEPS_TIMEPROFILE = self.config("FEPS_TIMEPROFILE_BINARY")

        self.log.info("Running FEPS Time Profile model")

        for fireLoc in fireInfo.locations():
            if fireLoc["consumption"] is None:
                self.log.debug("Fire %s has no consumption information; skip... ", fireLoc["id"])
                continue

            context.push_dir(fireLoc.uniqueid())

            diurnalFile = getDiurnalFile(self, context, fireLoc)

            consumptionFile = context.full_path("cons.txt")
            growthFile = context.full_path("growth.txt")
            profileFile = context.full_path("profile.txt")

            context.archive_file(consumptionFile)
            context.archive_file(growthFile)
            context.archive_file(profileFile)

            self.writeConsumption(fireLoc, consumptionFile)
            self.writeGrowth(fireLoc, growthFile)

            # What interpolation mode are we using?
            interpType = self.config("INTERPOLATION_TYPE", int)
            if not interpType: interpType = 1
            normalize = self.config("NORMALIZE", bool)
            if normalize:
                normSwitch = "-n"
            else:
                normSwitch = "-d"

            context.execute(FEPS_TIMEPROFILE,
                            "-c", consumptionFile,
                            "-w", diurnalFile,
                            "-g", growthFile,
                            "-i", str(interpType),
                            normSwitch,
                            "-o", profileFile)

            time_profile = self.readProfile(profileFile)

            # Adjust the start time to midnight local time
            fire_dt = fireLoc["date_time"]
            start_of_fire_day = BSDateTime(fire_dt.year, fire_dt.month, fire_dt.day,
                                           0, 0, 0, 0,
                                           tzinfo=fire_dt.tzinfo)
            fireLoc["date_time"] = start_of_fire_day

            fireLoc["time_profile"] = time_profile

            context.pop_dir()

        self.set_output("fires", fireInfo)

    def writeConsumption(self, fireLoc, filename):
        f = open(filename, 'w')
        f.write("cons_flm=%f\n" % fireLoc["consumption"]["flaming"])
        f.write("cons_sts=%f\n" % fireLoc["consumption"]["smoldering"])
        f.write("cons_lts=%f\n" % fireLoc["consumption"]["residual"])
        f.write("cons_duff=%f\n" % fireLoc["consumption"]["duff"])
        f.write("moist_duff=%f\n" % fireLoc.fuel_moisture.moisture_duff)
        f.close()

    def writeGrowth(self, fireLoc, filename):
        f = open(filename, 'w')
        f.write("day, hour, size\n")
        cumul_size = 0
        if fireLoc["type"] in ("WF", "WFU", "Unknown"):
            # Write area measurements using WRAP curve
            for h, size_fract in enumerate(WRAP_TIME_PROFILE):
                day = h // 24
                hour = h % 24
                size = fireLoc["area"] * size_fract
                cumul_size += size
                f.write("%d, %d, %f\n" %(day, hour, cumul_size))
        else:
            # Write area measurements (single curve, since we only have one area)
            start_size = 0
            end_size = fireLoc["area"]
            
            new_start_hour = fireLoc["date_time"].hour
            
            if new_start_hour == 0 or new_start_hour > 17:
                start_hour = 9
                end_hour = 18
            else:
                start_hour = new_start_hour
                end_hour = 18
            
            f.write("0, %d, %f\n" % (start_hour, start_size))
            f.write("0, %d, %f\n" % (end_hour, end_size))
        f.close()

    def readProfile(self, profileFile):
        time_profile = construct_type("TimeProfileData")
        for k in ["area_fract", "flame_profile", "smolder_profile", "residual_profile"]:
            time_profile[k] = []
        for i, row in enumerate(csv.DictReader(open(profileFile, 'r'), skipinitialspace=True)):
            assert int(row["hour"]) == i, "Invalid time profile file format (hour %s is on line %d)" % (row["hour"], i)
            time_profile["area_fract"].append(float(row["area_fract"]))
            time_profile["flame_profile"].append(float(row["flame"]))
            time_profile["smolder_profile"].append(float(row["smolder"]))
            time_profile["residual_profile"].append(float(row["residual"]))

        return time_profile


class FEPSEmissions(Emissions):
    """ FEPS Emissions Module """

    def run(self, context):
        fireInfo = self.get_input("fires")
        FEPS_EMISSIONS = self.config("FEPS_EMISSIONS_BINARY")
        FEPS_OUTPUT = self.config("FEPS_OUTPUT_BINARY")

        self.log.info("Running FEPS Emissions model")

        for fireLoc in fireInfo.locations():
            if fireLoc["consumption"] is None:
                self.log.debug("Fire %s has no consumption information; skip...", fireLoc["id"])
                continue
            if fireLoc["time_profile"] is None:
                self.log.debug("Fire %s has no time profile information; skip...", fireLoc["id"])
                continue

            context.push_dir(fireLoc.uniqueid())

            consumptionFile = context.full_path("cons.txt")
            totalEmissionsFile = context.full_path("total_emissions.txt")
            context.archive_file(consumptionFile)
            context.archive_file(totalEmissionsFile)

            self.writeConsumption(fireLoc, consumptionFile)

            context.execute(FEPS_EMISSIONS,
                            "-c", consumptionFile,
                            "-a", str(fireLoc["area"]),
                            "-o", totalEmissionsFile)

            if not len(fireLoc["time_profile"]):
                self.log.warn("Skipping fire %s because it has an invalid time profile", fireLoc["id"])
                emissions = None
            else:
                profileFile = context.full_path("profile.txt")
                emissionsFile = context.full_path("emissions.txt")
                context.archive_file(profileFile)
                context.archive_file(emissionsFile)
                self.writeProfile(fireLoc, profileFile)

                context.execute(FEPS_OUTPUT,
                                "-e", totalEmissionsFile,
                                "-p", profileFile,
                                "-o", emissionsFile)

                emissions = self.readEmissions(emissionsFile)

                plumeFile = getPlumeFile(self, context, fireLoc)
                heat = []
                for row in csv.DictReader(open(plumeFile, 'r'), skipinitialspace=True):
                    heat.append(float(row["heat"]))

                emissions["heat"] = heat

            # OK, these are our output emissions
            fireLoc["emissions"] = emissions
            
            # If FEPS_EMIS_HAP set to be true, output HAPs emission
            if self.config("FEPS_EMIS_HAP")== "true":
                ##AddHAP calculation
                # these emission factors are in lbs/ton consumed
                # consumption is in tons/acre burned
                total_consumption = ((fireLoc["consumption"]["flaming"] +
                    fireLoc["consumption"]["smoldering"] +
                    fireLoc["consumption"]["residual"]) *
                    fireLoc["area"] / 2000.0)
                fireLoc["metadata"]["hap_106990"] = total_consumption * 0.405 # 1,3-butadiene
                fireLoc["metadata"]["hap_75070"] = total_consumption * 0.40825 # acetaldehyde
                fireLoc["metadata"]["hap_107028"] = total_consumption * 0.424 # acrolein
                fireLoc["metadata"]["hap_120127"] = total_consumption * 0.005 # anthracene
                fireLoc["metadata"]["hap_56553"] = total_consumption * 0.0062 # benz(a)anthracene
                fireLoc["metadata"]["hap_71432"] = total_consumption * 1.125 # benzene
                fireLoc["metadata"]["hap_203338"] = total_consumption * 0.0026 # benzo(a)fluoranthene
                fireLoc["metadata"]["hap_50328"] = total_consumption * 0.00148 # benzo(a)pyrene
                fireLoc["metadata"]["hap_195197"] = total_consumption * 0.0039 # benzo(c)phenanthrene
                fireLoc["metadata"]["hap_192972"] = total_consumption * 0.00266 # benzo(e)pyrene
                fireLoc["metadata"]["hap_191242"] = total_consumption * 0.00508 # benzo(ghi)perlyene
                fireLoc["metadata"]["hap_207089"] = total_consumption * 0.0026 # benzo(k)fluoranthene
                #remove benzofluoranthenes as it's the total of benzo(a)fluoranthene & benzo(k)fluoranthene
                #fireLoc["metadata"]["hap_56832736"] = total_consumption * 0.00514 # benzofluoranthenes
                fireLoc["metadata"]["hap_463581"] = total_consumption * 0.000534 # carbonyl sulfide
                fireLoc["metadata"]["hap_218019"] = total_consumption * 0.0062 # chrysene
                fireLoc["metadata"]["hap_206440"] = total_consumption * 0.00673 # fluoranthene
                fireLoc["metadata"]["hap_50000"] = total_consumption * 2.575 # formaldehyde
                fireLoc["metadata"]["hap_193395"] = total_consumption * 0.00341 # indeno(1,2,3-cd)pyrene
                fireLoc["metadata"]["hap_74873"] = total_consumption * 0.128325 # methyl chloride
                fireLoc["metadata"]["hap_26914181"] = total_consumption * 0.00823 # methylanthracene
                fireLoc["metadata"]["hap_247"] = total_consumption * 0.00296 # methylbenzopyrenes
                fireLoc["metadata"]["hap_248"] = total_consumption * 0.0079 # methylchrysene
                fireLoc["metadata"]["hap_2381217"] = total_consumption * 0.00905 # methylpyrene,-fluoranthene
                fireLoc["metadata"]["hap_110543"] = total_consumption * 0.0164025 # n-hexane
                # replace o,m,p-xylene total with individual isomers 
                #fireLoc["metadata"]["hap_1330207"] = total_consumption * 0.242 # o,m,p-xylene
                fireLoc["metadata"]["hap_108383"] = total_consumption * 0.242 * 0.5907 # m-xylene
                fireLoc["metadata"]["hap_106423"] = total_consumption * 0.242 * 0.1925 # p-xylene
                fireLoc["metadata"]["hap_95476"] = total_consumption * 0.242 * 0.2168 # o-xylene
                fireLoc["metadata"]["hap_198550"] = total_consumption * 0.000856 # perylene
                fireLoc["metadata"]["hap_85018"] = total_consumption * 0.005 # phenanthrene
                fireLoc["metadata"]["hap_129000"] = total_consumption * 0.00929 # pyrene
                fireLoc["metadata"]["hap_108883"] = total_consumption * 0.56825 # toluene            

            context.pop_dir()
        self.set_output("fires", fireInfo)

    def writeConsumption(self, fireLoc, filename):
        f = open(filename, 'w')
        f.write("cons_flm=%f\n" % fireLoc["consumption"]["flaming"])
        f.write("cons_sts=%f\n" % fireLoc["consumption"]["smoldering"])
        f.write("cons_lts=%f\n" % fireLoc["consumption"]["residual"])
        f.write("cons_duff=%f\n" % fireLoc["consumption"]["duff"])
        f.write("moist_duff=%f\n" % fireLoc.fuel_moisture.moisture_duff)
        f.close()

    def writeProfile(self, fireLoc, timeProfileFile):
        f = open(timeProfileFile, 'w')
        f.write("hour, area_fract, flame, smolder, residual\n")
        for h in range(len(fireLoc["time_profile"]["area_fract"])):
            f.write("%d, %f, %f, %f, %f\n" % (h,
                    fireLoc["time_profile"]["area_fract"][h],
                    fireLoc["time_profile"]["flame_profile"][h],
                    fireLoc["time_profile"]["smolder_profile"][h],
                    fireLoc["time_profile"]["residual_profile"][h]))
        f.close()

    def readEmissions(self, filename):
        emissions = construct_type("EmissionsData")
        for k in ("time", "heat", "pm25", "pm10", "co", "co2", "ch4", "nox",
                  "nh3", "so2", "voc", "pm", "nmhc"):
            emissions[k] = []

        for k in ("heat", "pm", "nmhc"):
            emissions[k] = None

        def val_tuple(x):
            v = construct_type("EmissionsTuple")
            v.flame = float(row["flame_" + x])
            v.smold = float(row["smold_" + x])
            v.resid = float(row["resid_" + x])
            return v

        for row in csv.DictReader(open(filename, 'r'), skipinitialspace=True):
            emissions["time"].append(int(row["hour"]))
            #emissions["heat"].append(0.0) # Now calculated in plume split module
            emissions["pm25"].append(val_tuple("PM25"))
            emissions["pm10"].append(val_tuple("PM10"))
            emissions["co"].append(val_tuple("CO"))
            emissions["co2"].append(val_tuple("CO2"))
            emissions["ch4"].append(val_tuple("CH4"))
            emissions["nox"].append(val_tuple("NOx"))
            emissions["nh3"].append(val_tuple("NH3"))
            emissions["so2"].append(val_tuple("SO2"))
            emissions["voc"].append(val_tuple("VOC"))

            # TODO: we should find a way to use None instead of zero here!
            #emissions["pm"].append(construct_type("EmissionsTuple", (0.0, 0.0, 0.0)))
            #emissions["nmhc"].append(construct_type("EmissionsTuple", (0.0, 0.0, 0.0)))

        return emissions


class FEPSPlumeRise(PlumeRise):
    """ FEPS Plume Rise Module """

    def run(self, context):
        fireInfo = self.get_input("fires")
        FEPS_WEATHER = self.config("FEPS_WEATHER_BINARY")
        FEPS_PLUMERISE = self.config("FEPS_PLUMERISE_BINARY")

        self.log.info("Running FEPS Plume Rise model")

        for fireLoc in fireInfo.locations():
            if fireLoc["time_profile"] is None:
                self.log.debug("Fire %s has no time profile; skip... " % fireLoc["id"])
                continue
            if fireLoc["consumption"] is None:
                self.log.debug("Fire %s has no consumption information; skip... ", fireLoc["id"])
                continue

            context.push_dir(fireLoc.uniqueid())

            plumeFile = getPlumeFile(self, context, fireLoc)

            behave = self.config("PLUME_TOP_BEHAVIOR").lower()
            heat, plume_rise = self.readPlumeRise(fireLoc["id"], plumeFile, behave)

            fireLoc["emissions"]["heat"] = heat
            fireLoc["plume_rise"] = plume_rise

            context.pop_dir()

        self.set_output("fires", fireInfo)

    def writeConsumption(self, fireLoc, filename):
        f = open(filename, 'w')
        f.write("cons_flm=%f\n" % fireLoc["consumption"]["flaming"])
        f.write("cons_sts=%f\n" % fireLoc["consumption"]["smoldering"])
        f.write("cons_lts=%f\n" % fireLoc["consumption"]["residual"])
        f.write("cons_duff=%f\n" % fireLoc["consumption"]["duff"])
        f.write("moist_duff=%f\n" % fireLoc.fuel_moisture.moisture_duff)
        f.close()

    def writeProfile(self, fireLoc, timeProfileFile):
        f = open(timeProfileFile, 'w')
        f.write("hour, area_fract, flame, smolder, residual\n")
        for h in range(len(fireLoc["time_profile"]["area_fract"])):
            f.write("%d, %f, %f, %f, %f\n" % (h,
                    fireLoc["time_profile"]["area_fract"][h],
                    fireLoc["time_profile"]["flame_profile"][h],
                    fireLoc["time_profile"]["smolder_profile"][h],
                    fireLoc["time_profile"]["residual_profile"][h]))
        f.close()

    def readPlumeRise(self, id, plumeFile, behave):
        plumeRise = construct_type("PlumeRise")
        plumeRise.hours = []
        heat = []

        hour = 0
        for row in csv.DictReader(open(plumeFile, 'r'), skipinitialspace=True):
            # Save the heat (returned as emissions, not plume rise)
            heat.append(float(row["heat"]))

            # Construct a PlumeRiseHour structure from smold_frac, plume_bot,
            # and plume_top.
            smoldering_fraction = float(row["smold_frac"])
            plume_bottom_meters = float(row["plume_bot"])
            plume_top_meters = float(row["plume_top"])

            if heat == 0:
                plume_top_meters = 0.0
                plume_bottom_meters = 0.0

            if behave == "briggs":
                pass
            elif behave == "feps":
                plume_top_meters = plume_bottom_meters * 2
            elif behave == "auto":
                if plume_top_meters < plume_bottom_meters:
                    self.log.debug("Adjusting plume_top for %s hour %d from Briggs to FEPS equation value", id, hour)
                    plume_top_meters = plume_bottom_meters * 2
            else:
                raise Exception("Unknown value for PLUME_TOP_BEHAVIOR: %s", behave)

            plumeRiseHour = construct_type("PlumeRiseHour", smoldering_fraction, plume_bottom_meters, plume_top_meters)
            plumeRise.hours.append(plumeRiseHour)
            hour += 1



        return heat, plumeRise
