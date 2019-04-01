#*****************************************************************************
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
#***************************************************************************************
_bluesky_version_ = "3.5.1"

from kernel.core import Process
from kernel.bs_datetime import BSDateTime, UTC
from kernel.types import construct_type
from kernel.log import SUMMARY

from hysplitIndexedDataLocation import CatalogIndexedData
from datetime import timedelta
from glob import glob
import os.path
import shutil
import tarfile
from dispersion import Dispersion


def aquipt_date_str(date):
    """Return the "AQUIPT standard" hysplit initialization date string"""
    return date.strftime("%Y%m%d%H")

    
class InputAquiptARL(Process):
    """Read ARL-format meteorological data for AQUIPT"""

    def init(self):
        self.declare_input("aquipt_info", "AquiptInfo")      
        self.declare_output("aquipt_info", "AquiptInfo")

    def run(self, context):

        # Acquire some basic inputs
        ARL_PATTERN = self.config("ARL_PATTERN")
        hoursToRun = self.config("HOURS_TO_RUN", int)

        # Construct a new AquiptInfo object
        aquipt_info = construct_type("AquiptInfo")

        # This input node works with ARL data
        aquipt_info["met_file_type"] = "ARL"

        # Build the list of model initialization dates (BSDateTime objects)
        aquipt_info["dispersion_dates"] = list()

        if not self.config("USE_LIST_OF_DATES", bool):  # Case 1: no list of dates
            self.log.info("Generating AQUIPT run dates from config settings")

            # Pull the AQUIPT datetime info for this run
            year  = self.config("AQUIPT_START_YEAR", int)
            sdate = self.config("AQUIPT_START_DATE", str)
            eyear = self.config("AQUIPT_END_YEAR", int)
            edate = self.config("AQUIPT_END_DATE", str)
            hour  = self.config("AQUIPT_START_HOUR", int)
            interval = self.config("AQUIPT_INIT_INTERVAL", int)

            while year <= eyear:  # loop over AQUIPT-years
                date = BSDateTime(year, int(sdate[0:2]), int(sdate[2:4]), hour, 0, 0, tzinfo=UTC())

                if int(sdate <= edate):  # no year cross-over
                    end_date = BSDateTime(year, int(edate[0:2]), int(edate[2:4]), 23, 0, 0, tzinfo=UTC())
                else:  # year cross-over
                    end_date = BSDateTime(year+1, int(edate[0:2]), int(edate[2:4]), 23, 0, 0, tzinfo=UTC())

                while date <= end_date:  # loop over days within each AQUIPT-year
                    aquipt_info["dispersion_dates"].append(date)
                    date += timedelta(hours=interval)

                year += 1

        else:  # Case 2: Use list of dates processed from input file
            DATES_FILENAME = self.config("AQUIPT_DATES_FILENAME")
            self.log.info("Reading AQUIPT run dates from " + DATES_FILENAME)

            if not context.file_exists(DATES_FILENAME):
                raise AssertionError("Failed to find %s...Check AQUIPT_DATES_FILNAME setting." % DATES_FILENAME)

            for d in file(DATES_FILENAME, "r"):
                aquipt_info["dispersion_dates"].append(BSDateTime.strptime(d.strip(), "%Y%m%d%H", tzinfo=UTC()))

        # Build the ARL filenames dictionary (key = initialization date string; value = list of ARL met files)
        aquipt_info["met_files"] = dict()

        nmet = 0
        for init_date in aquipt_info["dispersion_dates"]:
            metfiles = []

            if self.config("ARL_TWO_FILES_PER_MONTH", bool):  # TODO: Not tested yet
                date = init_date
                dispersion_end = init_date + timedelta(hours=hoursToRun+24)  # 24-hr buffer here to ensure adequate data coverage.
                file_pattern = os.path.basename(ARL_PATTERN)
                while date <= dispersion_end:
                    metglob = date.strftime(os.path.dirname(ARL_PATTERN))
                    if "%b" in file_pattern:
                        metglob = os.path.join(metglob, date.strftime(file_pattern).lower())
                    else:
                        metglob = os.path.join(metglob, date.strftime(file_pattern))
                    if date.day < 16:
                        metglob += ".001"
                    else:
                        metglob += ".002"
                    metfiles += glob(metglob)
                    date += timedelta(days=1)
                metfiles = sorted(list(set(metfiles)))  # Remove duplicates
                
            elif self.config("USE_CATALOG_INDEXING", bool):
                self.log.info("Using catalog indexed ARL data")
                date_naive = BSDateTime(init_date.year, init_date.month, init_date.day, init_date.hour,
                                        init_date.minute, init_date.second, init_date.microsecond, tzinfo=None)
                catalog_indexed_data = CatalogIndexedData(self.config("CATALOG_DATA_INDEX_FILE"))
                # Fix for situation when there are multiple paths to the same met file, causing said file to be listed more
                # than once.  Hysplit fails when given multiple references to the same met file.
                inputfiles = catalog_indexed_data.get_input_files(date_naive, hoursToRun)
                metfiles = list()
                for inputfile in inputfiles:
                    if os.path.basename(inputfile) not in [os.path.basename(metfile) for metfile in metfiles]:
                        metfiles.append(inputfile)
                
            else:
                metglob = init_date.strftime(ARL_PATTERN)
                metfiles += sorted(glob(metglob))

            if len(metfiles):
                aquipt_info["met_files"][aquipt_date_str(init_date)] = metfiles
                nmet += 1

        # Info and Debugging
        nruns = len(aquipt_info["dispersion_dates"])
        self.log.log(SUMMARY, "Found ARL data for %d out of %d initializations." % (nmet, nruns))
        self.log.info("Planning to run AQUIPT with %d HYSPLIT simulations" % nmet)
        if nruns != nmet:
            self.log.warn("ARL data not found for all requested HYSPLIT initializations.")

        if nmet == 0:
            if self.config("STOP_IF_NO_MET", bool):
                raise Exception("Found no matching ARL files for any of the requested AQUIPT runs. Stop.")
            self.log.warn("Found no matching ARL files; meteorological data are not available")
            self.log.debug("No ARL files matched '%s'", os.path.basename(ARL_PATTERN))

        # Finalize the outputs for this process
        self.set_output("aquipt_info", aquipt_info)


class AquiptARLLocalMet(Process):
    """Extract fire-local meteorological data"""

    def init(self):
        self.declare_input("aquipt_info", "AquiptInfo")
        self.declare_input("fires", "FireInformation")
        self.declare_output("aquipt_info", "AquiptInfo")
        self.declare_output("fires", "FireInformation")
        self.declare_output("met_info", "MetInfo")

    def run(self, context):
        aquipt_info = self.get_input("aquipt_info")
        fireInfo = self.get_input("fires")
        met_info = construct_type("MetInfo")

        if aquipt_info["met_file_type"] != "ARL":
            raise Exception("AquiptARLLocalMet can only be used with ARL-format met data")

        for fireLoc in fireInfo.locations():
            fireLoc["elevation"] = 0

        self.set_output("aquipt_info", aquipt_info)
        self.set_output("met_info", met_info)
        self.set_output("fires", fireInfo)


class OutputAquipt(Process):
    """Perform post-processing on AQUIPT dispersion runs and provide
    output in netCDF format.
    """

    def init(self):
        self.declare_input("aquipt_info", "AquiptInfo")

    def run(self, context):
        self.log.info("Running aquiptpost")
        aquiptInfo = self.get_input("aquipt_info")

        # Configuration inputs
        AQUIPTPOST_BINARY = self.config("AQUIPTPOST_BINARY")
        IMPACT_LEVELS = self.config("IMPACT_LEVELS", str)
        TIME_IMPACT_PCNT_LEVELS = self.config("TIME_IMPACT_PCNT_LEVELS", str)
        DATA_BINS = self.config("DATA_BINS", str)

        # Build aquiptpost input file list
        filelist_file = context.full_path("filelist.txt")
        with open(filelist_file, "w") as filelist:
            for i, f in enumerate(aquiptInfo["dispersion_files"]):
                target = "file%.9d.nc" % i
                context.link_file(f, target)
                filelist.write(target+"\n")
        context.archive_file(filelist_file)

        # Build aquiptpost input control file
        control_file = context.full_path("aquiptpost.inp")
        with open(control_file, "w") as controlfile:
            # Species
            controlfile.write("Species to process                     |" + "PM25"+"\n")

            # Impact levels
            num_impact_levels = len(IMPACT_LEVELS.split(","))
            controlfile.write("Number of Impact Levels                |" + str(num_impact_levels)+"\n")
            controlfile.write("Impact levels                          |" + IMPACT_LEVELS+"\n")

            # Time impact percentage levels
            num_pcnt_impact_levels = len(TIME_IMPACT_PCNT_LEVELS.split(","))
            controlfile.write("Number of time impact pcnt. levels     |" + str(num_pcnt_impact_levels)+"\n")
            controlfile.write("Impact levels                          |" + TIME_IMPACT_PCNT_LEVELS+"\n")

            # Data bins (for aquiptpost's concentration frequency distribution)
            num_bins = len(DATA_BINS.split(","))    # The input is "bin lower interfaces, which should include 0.0"
            controlfile.write("Number of data bins (nbins)            |" + str(num_bins)+"\n")
            controlfile.write("Bin interfaces (nbins)                 |" + DATA_BINS+"\n")

            # Scaling factor (smoke_dispersion.nc data are in ug/m3, and we want to keep it that way)
            controlfile.write("Concentration scale factor             |" + "1.0"+"\n")

            # Debugging options
            controlfile.write("Debugging flag                         |" + ".true."+"\n")
            controlfile.write("Debugging grid cell (i,j)              |" + "56,45"+"\n")

        context.archive_file(control_file)

        # Run aquiptpost program
        context.execute(AQUIPTPOST_BINARY, filelist_file)

        # Send off the aggregate output file
        netcdf_file = context.full_path("hysplit_stat_2d")
        dispersion_filename = os.path.join(self.config("OUTPUT_DIR"), self.config("DISPERSION_FILE"))
        if context.file_exists(netcdf_file):
            shutil.copy(netcdf_file, dispersion_filename)

        # Build an "ensemble" dispersion output with all the raw dispersion output
        # concatenated into a single file.
        if self.config("CREATE_ENSEMBLE_FILE", bool):
            self.log.info("Creating dispersion ensemble file.")
            netcdf_file = context.full_path("smoke_ensemble.nc")
            NCECAT = self.config("NCECAT")
            if context.file_exists(NCECAT):
                ensemble_filename = os.path.join(self.config("OUTPUT_DIR"), self.config("ENSEMBLE_FILE"))
                args = [NCECAT]
                for f in sorted(glob(context.full_path("file*.nc"))):
                    args.append(os.path.basename(f))
                args.append(netcdf_file)
                context.execute(args)
                if context.file_exists(netcdf_file):
                    shutil.copy(netcdf_file, ensemble_filename)
            else:
                self.log.warn("Failed to find NCO utility %s. Dispersion ensemble file not created." % NCECAT)


class AquiptHYSPLITDispersion(Dispersion):
    """ HYSPLIT Concentration model version 4.9 for AQUIPT"""

    def init(self):
        self.declare_input("aquipt_info", "AquiptInfo")
        self.declare_input("met_info", "MetInfo")
        self.declare_input("fires", "FireInformation")
        self.declare_output("aquipt_info", "AquiptInfo")
        self.declare_output("fires", "FireInformation")

    def run(self, context):
        self.log.info("Running the HYSPLIT49 Dispersion model in AQUIPT mode")

        fireInfo = self.get_input("fires")
        aquiptInfo = self.get_input("aquipt_info")

        if aquiptInfo["met_file_type"] != "ARL":
            raise Exception("HYSPLIT requires ARL-format meteorological data")

        # List of output files to be passed along
        aquiptInfo["dispersion_files"] = list()

        # Executables
        HYSPLIT_BINARY = self.config("HYSPLIT_BINARY")
        HYSPLIT_MPI_BINARY = self.config("HYSPLIT_MPI_BINARY")
        HYSPLIT2NETCDF_BINARY = self.config("HYSPLIT2NETCDF_BINARY")

        # Ancillary data files (note: HYSPLIT49 balks if it can't find ASCDATA.CFG).
        ASCDATA_FILE = self.config("ASCDATA_FILE")
        LANDUSE_FILE = self.config("LANDUSE_FILE")
        ROUGLEN_FILE = self.config("ROUGLEN_FILE")

        # Hours in each HYSPLIT simulation
        hoursToRun = self.config("HOURS_TO_RUN", int)

        # MPI prep
        if self.config("MPI", bool):
            NCPUS = self.config("NCPUS", int)
            self.log.info("Running MPI HYSPLIT with %s processors." % NCPUS)
            if NCPUS < 1:
                self.log.warn("Invalid NCPUS specified...resetting NCPUS to 1 for this run.")
                NCPUS = 1
            mpiexec = self.config("MPIEXEC")

            if not context.file_exists(mpiexec):
                raise AssertionError("Failed to find %s. Check MPIEXEC setting and/or your MPICH2 installation." % mpiexec)
            if not context.file_exists(HYSPLIT_MPI_BINARY):
                raise AssertionError("HYSPLIT MPI executable %s not found." % HYSPLIT_MPI_BINARY)

        # Default value for NINIT for use in set up file (no particle initialization support in AQUIPT)
        ninit_val = "0"

        # Number of quantiles in vertical emissions allocation scheme
        NQUANTILES = 20

        # Reduction factor for vertical emissions layer allocation
        reductionFactor, num_output_quantiles = self.getReductionFactor(NQUANTILES)

        # Fire filtering
        filteredFires = list(self.filterFires(fireInfo))

        if(len(filteredFires) == 0):
            raise Exception("No fires have data for HYSPLIT dispersion")

        # Progress tracking
        nruns_expected = len(aquiptInfo["met_files"])
        nruns_executed = 0

        for init_date in aquiptInfo["dispersion_dates"]:  # LOOP through each AQUIPT initialization
            try:
                arl_files = aquiptInfo["met_files"][aquipt_date_str(init_date)]
            except KeyError:
                continue

            context.push_dir(aquipt_date_str(init_date))

            modelStart = init_date

            # Ancillary data files
            context.link_file(ASCDATA_FILE)
            context.link_file(LANDUSE_FILE)
            context.link_file(ROUGLEN_FILE)

            # Native inputs and outputs
            emissionsFile = context.full_path("EMISS.CFG")
            controlFile = context.full_path("CONTROL")
            setupFile = context.full_path("SETUP.CFG")
            messageFiles = [context.full_path("MESSAGE")]
            pardumpFiles = [context.full_path("PARDUMP")]
            outputConcFile = context.full_path("hysplit.con")
            if self.config("MPI", bool):
                messageFiles = ["MESSAGE.%3.3i" % (i+1) for i in xrange(NCPUS)]
                pardumpFiles = ["PARDUMP.%3.3i" % (i+1) for i in xrange(NCPUS)]

            # Build the emissions file
            self.writeEmissions(filteredFires, modelStart, hoursToRun, emissionsFile, reductionFactor, num_output_quantiles)

            # Build the control file
            self.writeControlFile(filteredFires, arl_files, modelStart, hoursToRun, controlFile, outputConcFile, num_output_quantiles)

            # Build the setup file
            self.writeSetupFile(filteredFires, modelStart, emissionsFile, setupFile, num_output_quantiles, ninit_val)

            # Link up the ARL files for this run
            for f in arl_files:
                context.link_file(f)
                self.log.info(f)

            # Run HYSPLIT
            self.log.info("Running HYSPLIT for %s. AQUIPT simulation %s of %s" % 
                          (aquipt_date_str(init_date), nruns_executed + 1, nruns_expected))
            if self.config("MPI", bool):
                context.execute(mpiexec, "-n", str(NCPUS), HYSPLIT_MPI_BINARY)
            else:  # standard serial run
                context.execute(HYSPLIT_BINARY)
            nruns_executed += 1

            #if not os.path.exists(outputConcFile):
            #    raise AssertionError("HYSPLIT failed, check MESSAGE file for details")

            # Create the netCDF dispersion file
            self.log.info("Converting HYSPLIT output to NetCDF format")
            outputFile = "hysplit_conc.nc"  # hysplit2netcdf has 16 char limit due to Models3 IO/API limitations.
            context.execute(HYSPLIT2NETCDF_BINARY,
                "-I" + outputConcFile,
                "-O" + outputFile,
                "-X1000000.0", # Scale factor to convert from grams to micrograms
                "-D1", # Debug flag
                "-L-1" # Lx is x layers. x=-1 for all layers...breaks KML output for multiple layers
                )

            if not context.file_exists(outputFile):
                raise AssertionError("Unable to convert HYSPLIT concentration file to NetCDF format")

            # Archive data files
            context.archive_file(emissionsFile)
            context.archive_file(controlFile)
            context.archive_file(setupFile)
            for f in messageFiles:
                context.archive_file(f)
            if self.config("MAKE_INIT_FILE", bool):
                for f in pardumpFiles:
                    context.archive_file(f)

            # Dispersion output for AquiptInfo object
            # Create date-specific filename (hysplit2netcdf has 16-char output filename limit per ioapi limitations)
            outputFileFinal = "hysplit_conc_"+aquipt_date_str(init_date)+".nc"
            context.move_file(outputFile, outputFileFinal)
            aquiptInfo["dispersion_files"].append(context.full_path(outputFileFinal))

            context.pop_dir()

        # DispersionData output
        dispersion_tarball = context.full_path("smoke_dispersion.tar.gz")
        with tarfile.open(dispersion_tarball, 'w:gz') as tar:    
            for f in aquiptInfo["dispersion_files"]:
                tar.add(f, arcname=os.path.basename(f))

        dispersionData = construct_type("DispersionData")
        dispersionData["grid_filetype"] = "NETCDF"
        dispersionData["grid_filename"] = dispersion_tarball
        dispersionData["parameters"] = {"pm25": "PM25"}
        fireInfo.dispersion = dispersionData

        # Finalize the outputs
        self.set_output("fires", fireInfo)
        self.set_output("aquipt_info", aquiptInfo)

    def getReductionFactor(self,nquantiles):
        """Retrieve factor for reducing the number of vertical emission levels"""

        #    Ensure the factor divides evenly into the number of quantiles.
        #    For the 20 quantile vertical accounting scheme, the following values are appropriate:
        #       reductionFactor = 1 .... 20 emission levels (no change from the original scheme)
        #       reductionFactor = 2......10 emission levels
        #       reductionFactor = 4......5 emission levels
        #       reductionFactor = 5......4 emission levels
        #       reductionFactor = 10.....2 emission levels
        #       reductionFactor = 20.....1 emission level

        # Pull reduction factor from user input
        reductionFactor = self.config("VERTICAL_EMISLEVELS_REDUCTION_FACTOR")
        reductionFactor = int(reductionFactor)

        # Ensure a valid reduction factor
        if reductionFactor > nquantiles:
            reductionFactor = nquantiles
            self.log.debug("VERTICAL_EMISLEVELS_REDUCTION_FACTOR reset to %s" % str(nquantiles))
        elif reductionFactor <= 0:
            reductionFactor = 1
            self.log.debug("VERTICAL_EMISLEVELS_REDUCTION_FACTOR reset to 1")
        while (nquantiles % reductionFactor) != 0:  # make sure factor evenly divides into the number of quantiles
            reductionFactor -= 1
            self.log.debug("VERTICAL_EMISLEVELS_REDUCTION_FACTOR reset to %s" % str(reductionFactor))

        num_output_quantiles = nquantiles/reductionFactor

        if reductionFactor != 1:
            self.log.info("Number of vertical emission levels reduced by factor of %s" % str(reductionFactor))
            self.log.info("Number of vertical emission quantiles will be %s" % str(num_output_quantiles))

        return reductionFactor,num_output_quantiles

    def filterFires(self, fireInfo):
        for fireLoc in fireInfo.locations():
            if fireLoc.time_profile is None:
                self.log.debug("Fire %s has no time profile data; skip...", fireLoc.id)
                continue

            if fireLoc.plume_rise is None:
                self.log.debug("Fire %s has no plume rise data; skip...", fireLoc.id)
                continue

            if fireLoc.emissions is None:
                self.log.debug("Fire %s has no emissions data; skip...", fireLoc.id)
                continue

            if fireLoc.emissions.sum("heat") < 1.0e-6:
                self.log.debug("Fire %s has less than 1.0e-6 total heat; skip...", fireLoc.id)
                continue

            yield fireLoc

    def getVerticalMethod(self):
        # Vertical motion choices:
        verticalChoices = dict(DATA=0, ISOB=1, ISEN=2, DENS=3, SIGMA=4, DIVERG=5, ETA=6)
        VERTICAL_METHOD = self.config("VERTICAL_METHOD")

        try:
            verticalMethod = verticalChoices[VERTICAL_METHOD]
        except KeyError:
            verticalMethod = verticalChoices["DATA"]

        return verticalMethod

    def writeEmissions(self, filteredFires, modelStart, hoursToRun, emissionsFile, reductionFactor, num_quantiles):
        # Note: HYSPLIT can accept concentrations in any units, but for 
        # consistency with other dispersion models, we convert to grams here.
        GRAMS_PER_TON = 907184.74

        # Conversion factor for fire size
        SQUARE_METERS_PER_ACRE = 4046.8726

        # A value slightly above ground level at which to inject smoldering
        # emissions into the model.
        SMOLDER_HEIGHT = self.config("SMOLDER_HEIGHT", float)

        # For AQUIPT, track the earliest ignition date of each fire.  
        # The fire growth models create new fire records with same ID, 
        # but different date_time.  We'll use this as the "base" date_time
        # from which we'll apply any array index offsets for the current
        # modelDate.
        base_ignition_date = dict()
        for fireLoc in filteredFires:
            ignition_date = fireLoc["date_time"]
            try:
                if ignition_date < base_ignition_date[fireLoc["id"]]:
                    base_ignition_date[fireLoc["id"]] = ignition_date
            except KeyError:
                base_ignition_date[fireLoc["id"]] = ignition_date
            #print "KJC base ignition date ", fireLoc["id"], base_ignition_date[fireLoc["id"]]

        with open(emissionsFile, "w") as emis:
            # HYSPLIT skips past the first two records, so these are for comment purposes only
            emis.write("emissions group header: YYYY MM DD HH QINC NUMBER\n")
            emis.write("each emission's source: YYYY MM DD HH MM DUR_HHMM LAT LON RATE AREA HEAT\n")

            # Loop through the timesteps
            for hour in xrange(hoursToRun):
                dt = modelStart + timedelta(hours=hour)
                dt_str = dt.strftime("%y %m %d %H")

                num_fires = len(filteredFires)
                num_heights = num_quantiles + 1
                num_sources = num_fires * num_heights

                # TODO: What is this and what does it do?
                # A reasonable guess would be that it means a time increment of 1 hour
                qinc = 1

                # Write the header line for this timestep
                emis.write("%s %02d %04d\n" % (dt_str, qinc, num_sources))

                noEmis = 0

                # Loop through the fire locations
                for fireLoc in filteredFires:
                    dummy = False

                    # Get some properties from the fire location
                    lat = fireLoc.latitude
                    lon = fireLoc.longitude

                    # Figure out what index (h) to use into our hourly arrays of data,
                    # based on the hour in our outer loop and the fireLoc's available
                    # data.

                    # For AQUIPT, there is a disconnect between modelStart and fire date_time.
                    # The goal (for now) is to use identical emissions for each HYSPLIT run.
                    # To do this without ignoring the data added by a growth model, 
                    # calculate the padding based on the date_time and the earliest
                    # ignition date for the fire.  This will be independent of modelDate,
                    # and assumes that all fires are ignighted on the model initialization day.

                    # Account for any UTC offset in fire_date by taking the time difference
                    # between fire_time and modelStart in a UTC frame of reference.

                    ###padding = fireLoc.date_time - modelStart
                    padding = fireLoc["date_time"] - base_ignition_date[fireLoc["id"]]
                    utc_offset_hours = fireLoc["date_time"].astimezone(UTC()).hour - modelStart.hour
                    padding_hours = ((padding.days * 86400) + padding.seconds) / 3600
                    padding_hours += utc_offset_hours # additional offset for aquipt applications
                    num_hours = min(len(fireLoc.emissions.heat), len(fireLoc.plume_rise.hours))
                    h = hour - padding_hours

                    # If we don't have real data for the given timestep, we need to stick in 
                    # dummy records anyway (so we have the correct number of sources).
                    if h < 0 or h >= num_hours:
                        noEmis += 1
                        self.log.debug("Fire %s has no emissions for hour %s", fireLoc.id, hour)
                        dummy = True

                    area_meters = 0.0
                    smoldering_fraction = 0.0
                    pm25_injected = 0.0
                    if not dummy:
                        # Extract the fraction of area burned in this timestep, and
                        # convert it from acres to square meters.
                        area = fireLoc.area * fireLoc.time_profile.area_fract[h]
                        area_meters = area * SQUARE_METERS_PER_ACRE

                        smoldering_fraction = fireLoc.plume_rise.hours[h].smoldering_fraction
                        # Total PM2.5 emitted at this timestep (grams)
                        pm25_emitted = fireLoc.emissions.pm25[h].sum() * GRAMS_PER_TON
                        # Total PM2.5 smoldering (not lofted in the plume)
                        pm25_injected = pm25_emitted * smoldering_fraction

                    entrainment_fraction = 1.0 - smoldering_fraction

                    # We don't assign any heat, so the PM2.5 mass isn't lofted
                    # any higher.  This is because we are assigning explicit
                    # heights from the plume rise.
                    heat = 0.0

                    # Inject the smoldering fraction of the emissions at ground level
                    # (SMOLDER_HEIGHT represents a value slightly above ground level)
                    height_meters = SMOLDER_HEIGHT

                    # Write the smoldering record to the file
                    record_fmt = "%s 00 0100 %8.4f %9.4f %6.0f %7.2f %7.2f %15.2f\n"
                    emis.write(record_fmt % (dt_str, lat, lon, height_meters, pm25_injected, area_meters, heat))

                    for pct in xrange(0, 100, reductionFactor*5):
                        height_meters = 0.0
                        pm25_injected = 0.0

                        if not dummy:
                            # Loop through the heights (20 quantiles of smoke density).
                            # For the unreduced case, we loop through 20 quantiles, but we have 
                            # 21 quantile-edge measurements.  So for each quantile gap, we need 
                            # to find a point halfway  between the two edges and inject 1/20th 
                            # of the total emissions there.

                            # KJC optimization...
                            # Reduce the number of vertical emission levels by a reduction factor
                            # and place the appropriate fraction of emissions at each level.
                            # ReductionFactor MUST evenly divide into the number of quantiles

                            lower_height = fireLoc.plume_rise.hours[h]["percentile_%03d" % (pct)]
                            upper_height = fireLoc.plume_rise.hours[h]["percentile_%03d" % (pct + (reductionFactor*5))]
                            if reductionFactor == 1:
                                height_meters = (lower_height + upper_height) / 2.0  # original approach
                            else:
                                height_meters = upper_height # top-edge approach
                            # Total PM2.5 entrained (lofted in the plume)
                            pm25_entrained = pm25_emitted * entrainment_fraction
                            # Inject the proper fraction of the entrained PM2.5 in each quantile gap.
                            pm25_injected = pm25_entrained * (float(reductionFactor)/float(num_quantiles))

                        # Write the record to the file
                        emis.write(record_fmt % (dt_str, lat, lon, height_meters, pm25_injected, area_meters, heat))

                if noEmis > 0:
                    self.log.debug("%d of %d fires had no emissions for hour %d", noEmis, num_fires, hour)
    
    def writeControlFile(self, filteredFires, arl_files, modelStart, hoursToRun, controlFile, concFile, num_quantiles):
        num_fires = len(filteredFires)
        num_heights = num_quantiles + 1  # number of quantiles used, plus ground level
        num_sources = num_fires * num_heights

        # An arbitrary height value.  Used for the default source height 
        # in the CONTROL file.  This can be anything we want, because 
        # the actual source heights are overridden in the EMISS.CFG file.
        sourceHeight = 15.0

        verticalMethod = self.getVerticalMethod()

        # Height of the top of the model domain
        modelTop = self.config("TOP_OF_MODEL_DOMAIN", float)

        modelEnd = modelStart + timedelta(hours=hoursToRun)

        # Build the vertical Levels string
        verticalLevels = self.config("VERTICAL_LEVELS")
        levels = [int(x) for x in verticalLevels.split()]
        numLevels = len(levels)
        verticalLevels = " ".join(str(x) for x in levels)

        # Warn about multiple sampling grid levels and KML/PNG image generation
        if numLevels > 1:
            self.log.warn("KML and PNG images will be empty since more than 1 vertical level is selected")

        # Set the output concentration grid parameters
        centerLat = self.config("CENTER_LATITUDE", float)
        centerLon = self.config("CENTER_LONGITUDE", float)
        widthLon = self.config("WIDTH_LONGITUDE", float)
        heightLat = self.config("HEIGHT_LATITUDE", float)
        spacingLon = self.config("SPACING_LONGITUDE", float)
        spacingLat = self.config("SPACING_LATITUDE", float)

        with open(controlFile, "w") as f:
            # Starting time (year, month, day hour)
            f.write(modelStart.strftime("%y %m %d %H") + "\n")

            # Number of sources
            f.write("%d\n" % num_sources)

            # Source locations
            for fireLoc in filteredFires:
                for height in xrange(num_heights):
                    f.write("%9.3f %9.3f %9.3f\n" % (fireLoc.latitude, fireLoc.longitude, sourceHeight))

            # Total run time (hours)
            f.write("%04d\n" % hoursToRun)

            # Method to calculate vertical motion
            f.write("%d\n" % verticalMethod)

            # Top of model domain
            f.write("%9.1f\n" % modelTop)

            # Number of input data grids (met files)
            f.write("%d\n" % len(arl_files))

            # Directory for input data grid and met file name
            for metfile in arl_files:
                f.write("./\n")
                f.write("%s\n" % os.path.basename(metfile))

            # Number of pollutants = 1 (only modeling PM2.5 for now)
            f.write("1\n")
            # Pollutant ID (4 characters)
            f.write("PM25\n")
            # Emissions rate (per hour) (Ken's code says "Emissions source strength (mass per second)" -- which is right?)
            f.write("0.001\n")
            # Duration of emissions (hours)
            f.write(" %9.3f\n" % hoursToRun)
            # Source release start time (year, month, day, hour, minute)
            f.write("%s\n" % modelStart.strftime("%y %m %d %H %M"))

            # Number of simultaneous concentration grids
            f.write("1\n")

            # NOTE: The size of the output concentration grid is specified 
            # here, but it appears that the ICHEM=4 option in the SETUP.CFG 
            # file may override these settings and make the sampling grid 
            # correspond to the input met grid instead...
            # But Ken's testing seems to indicate that this is not the case...          

            # Sampling grid center location (latitude, longitude)
            f.write("%9.3f %9.3f\n" % (centerLat, centerLon))
            # Sampling grid spacing (degrees latitude and longitude)
            f.write("%9.3f %9.3f\n" % (spacingLat, spacingLon))
            # Sampling grid span (degrees latitude and longitude)
            f.write("%9.3f %9.3f\n" % (heightLat, widthLon))

            # Directory of concentration output file
            f.write("./\n")
            # Filename of concentration output file
            f.write("%s\n" % os.path.basename(concFile))

            # Number of vertical concentration levels in output sampling grid
            f.write("%d\n" % numLevels)
            # Height of each sampling level in meters AGL
            f.write("%s\n" % verticalLevels)

            # Sampling start time (year month day hour minute)
            f.write("%s\n" % modelStart.strftime("%y %m %d %H %M"))
            # Sampling stop time (year month day hour minute)
            f.write("%s\n" % modelEnd.strftime("%y %m %d %H %M"))
            # Sampling interval (type hour minute)
            f.write("0 1 00\n") # Sampling interval:  type hour minute.  A type of 0 gives an average over the interval.

            # Number of pollutants undergoing deposition
            f.write("1\n") # only modeling PM2.5 for now

            # Particle diameter (um), density (g/cc), shape
            f.write("1.0 1.0 1.0\n")

            # Dry deposition: 
            #    deposition velocity (m/s), 
            #    molecular weight (g/mol),
            #    surface reactivity ratio, 
            #    diffusivity ratio,
            #    effective Henry's constant
            f.write("0.0 0.0 0.0 0.0 0.0\n")

            # Wet deposition (gases):
            #     actual Henry's constant (M/atm),
            #     in-cloud scavenging ratio (L/L),
            #     below-cloud scavenging coefficient (1/s)
            f.write("0.0 0.0 0.0\n")

            # Radioactive decay half-life (days)
            f.write("0.0\n")

            # Pollutant deposition resuspension constant (1/m)
            f.write("0.0\n")

    def writeSetupFile(self, filteredFires, modelStart, emissionsFile, setupFile, num_quantiles, ninit_val):
        # Advanced setup options
        # adapted from Robert's HysplitGFS Perl script        

        khmax_val = int(self.config("KHMAX"))
        ndump_val = int(self.config("NDUMP"))
        ncycl_val = int(self.config("NCYCL"))
        dump_datetime = modelStart + timedelta(hours=ndump_val)

        num_fires = len(filteredFires)
        num_heights = num_quantiles + 1
        num_sources = num_fires * num_heights

        max_particles = num_sources * 1000

        with open(setupFile, "w") as f:
            f.write("&SETUP\n")

            # ichem: i'm only really interested in ichem = 4 in which case it causes
            #        the hysplit concgrid to be roughly the same as the met grid
            # -- But Ken says it may not work as advertised...
            #f.write("  ICHEM = 4,\n")

            # qcycle: the number of hours between emission start cycles
            f.write("  QCYCLE = 1.0,\n")

            # mgmin: a run once complained and said i need to reaise this variable to
            #        some value around what i have here...it has something to do with
            #        the minimum size (in grid units) of the met sub-grib.
            f.write("  MGMIN = 750,\n")

            # maxpar: max number of particles that are allowed to be active at one time
            f.write("  MAXPAR = %d,\n" % max_particles)

            # numpar: number of particles (or puffs) permited than can be released
            #         during one time step
            f.write("  NUMPAR = %d,\n" % num_sources)

            # khmax: maximum particle duration in terms of hours after relase
            f.write("  KHMAX = %d,\n" % khmax_val)

            # initd: # 0 - Horizontal and Vertical Particle
            #          1 - Horizontal Gaussian Puff, Vertical Top Hat Puff
            #          2 - Horizontal and Vertical Top Hat Puff
            #          3 - Horizontal Gaussian Puff, Vertical Particle
            #          4 - Horizontal Top-Hat Puff, Vertical Particle (default)
            f.write("  INITD = 1,\n")

            # make the 'smoke initizilaztion' files?
            # pinfp: particle initialization file (see also ninit)
            #if self.config("READ_INIT_FILE", bool):
            #   f.write("  PINPF = \"PARINIT\",\n")

            # ninit: (used along side pinpf) sets the type of initialization...
            #          0 - no initialzation (even if files are present)
            #          1 = read pinpf file only once at initialization time
            #          2 = check each hour, if there is a match then read those values in
            #          3 = like '2' but replace emissions instead of adding to existing
            #              particles
            f.write("  NINIT = %s,\n" % ninit_val)

            # poutf: particle output/dump file
            if self.config("MAKE_INIT_FILE", bool):
                f.write("  POUTF = \"PARDUMP\",\n") 
                self.log.info("Dumping particles to PARDUMP starting at %s every %s hours" % (dump_datetime, ncycl_val))

            # ndump: when/how often to dump a poutf file negative values indicate to
            #        just one  create just one 'restart' file at abs(hours) after the
            #        model start
            if self.config("MAKE_INIT_FILE", bool):
                f.write("  NDUMP = %d,\n" % ndump_val)

            # ncycl: set the interval at which time a pardump file is written after the
            #        1st file (which is first created at T = ndump hours after the
            #        start of the model simulation 
            if self.config("MAKE_INIT_FILE", bool):
                f.write("  NCYCL = %d,\n" % ncycl_val)

            # efile: the name of the emissions info (used to vary emission rate etc (and
            #        can also be used to change emissions time
            f.write("  EFILE = \"%s\",\n" % os.path.basename(emissionsFile))

            f.write("&END\n")
