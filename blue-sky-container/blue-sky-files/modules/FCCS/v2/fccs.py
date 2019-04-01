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

from fuel_loading import FuelLoading
from kernel.types import construct_type
from kernel.grid import open_grid


class FCCS(FuelLoading):
    """ FCCS Fuel Loading Module """

    def run(self, context):
        
        #
        # Get fires from input plug
        #
        fireInfo = self.get_input("fires")

        #
        # Get NetCDF and CSV 'library' filenames (rarely changed)
        #
        FUEL_LOAD_DATA = None
        FUEL_LOOKUP_CSV = None
        FUEL_LOAD_VARIABLE = None
        FUEL_LOAD_DATA_AK = None
        FUEL_LOOKUP_CSV_AK = None
        FUEL_LOAD_VARIABLE_AK = None
        if self.config("FCCS_VERSION") == "1":
        	FUEL_LOAD_DATA = self.config("FUEL_LOAD_DATA")
        	FUEL_LOOKUP_CSV = self.config("FUEL_LOOKUP_CSV")
        	FUEL_LOAD_VARIABLE = self.config("FUEL_LOAD_VARIABLE")
        elif self.config("FCCS_VERSION") == "2":
        	FUEL_LOAD_DATA = self.config("FUEL_LOAD_DATA2")
        	FUEL_LOOKUP_CSV = self.config("FUEL_LOOKUP_CSV2")
        	FUEL_LOAD_VARIABLE = self.config("FUEL_LOAD_VARIABLE2")
        # Alaska dataset    
        FUEL_LOAD_DATA_AK = self.config("FUEL_LOAD_DATA_AK")
        FUEL_LOOKUP_CSV_AK = self.config("FUEL_LOOKUP_CSV2")
        FUEL_LOAD_VARIABLE_AK = self.config("FUEL_LOAD_VARIABLE_AK")

        #
        # Open the NetCDF file and extract the fuel loading
        #
        grid = open_grid(FUEL_LOAD_DATA, param=FUEL_LOAD_VARIABLE)
        # Alaska dataset
        grid_AK = open_grid(FUEL_LOAD_DATA_AK, param=FUEL_LOAD_VARIABLE_AK)

        #
        # Read in the CSV Fuel Lookup data into a dictionary for easy lookup
        #
        fccsLoading = {}
        for row in csv.DictReader(file(FUEL_LOOKUP_CSV,'r')):
            fccsLoading[int(row["mapID"])] = row
        # Alaska dataset
        fccsLoadingAK = {}
        for rowAK in csv.DictReader(file(FUEL_LOOKUP_CSV_AK,'r')):
            fccsLoadingAK[int(rowAK["mapID"])] = rowAK
        
        nFires = len(fireInfo.locations())
        nSuccess = 0
        for fireLoc in fireInfo.locations():
        
            fuelInfo = fireLoc["fuels"]
            fccsNumber = None
            fuelLoadingLookup = {}

            if fuelInfo is not None:
                fccsNumber = fuelInfo["metadata"].get("fccs_number", None)

            if fuelInfo is not None and fccsNumber is not None:
                self.log.info("Skipping %s, fuels already set" % fireLoc)
                continue
            elif fuelInfo is None:
                if fireLoc["latitude"] is None or fireLoc["longitude"] is None:
                    self.log.debug("Invalid location for %s, fuels is None", fireLoc)
                    continue

                try:
                    fccsNumber = grid.getValueAt(fireLoc["latitude"], fireLoc["longitude"])
                    fuelLoadingLookup = fccsLoading
                except ValueError, e:
                    self.log.debug("Error: %s for %s", str(e), fireLoc)
                    pass

            if fccsNumber is None or fccsNumber < 0: # or fccsNumber > 291:
                self.log.debug("No data for %s in contiguous U.S., fccs_number = %s",
                               fireLoc, fccsNumber)
                
                self.log.debug("Checking Alaska...")

                try:
                    fccsNumber = grid_AK.getValueAt(fireLoc["latitude"], fireLoc["longitude"])
                    fuelLoadingLookup = fccsLoadingAK
                except ValueError, e:
                    self.log.debug("Error: %s for %s", str(e), fireLoc)
                    continue
                
                if fccsNumber is None or fccsNumber < 0:
                    self.log.debug("No data for %s, fccs_number = %s",
                               fireLoc, fccsNumber)
                    continue
                    

            fuelInfo = construct_type("FuelsData")
            fireLoc["fuels"] = fuelInfo
            self.log.debug("%s: FCCS Fuel Loading: %d %s", fireLoc, fccsNumber, fuelLoadingLookup[fccsNumber]["VEG"])
            nSuccess += 1
            
            fuelInfo["metadata"]["fccs_number"] = fccsNumber

            fuelInfo["fuel_1hr"] = float(fuelLoadingLookup[fccsNumber]["1HR"])
            fuelInfo["fuel_10hr"] = float(fuelLoadingLookup[fccsNumber]["10HR"])
            fuelInfo["fuel_100hr"] = float(fuelLoadingLookup[fccsNumber]["100HR"])
            fuelInfo["fuel_1khr"] = float(fuelLoadingLookup[fccsNumber]["1kHR"])
            fuelInfo["fuel_10khr"] = float(fuelLoadingLookup[fccsNumber]["10kHR"])
            fuelInfo["fuel_gt10khr"] = float(fuelLoadingLookup[fccsNumber]["10k+HR"])
            fuelInfo["shrub"] = float(fuelLoadingLookup[fccsNumber]["SHRUB"])
            fuelInfo["grass"] = float(fuelLoadingLookup[fccsNumber]["GRASS"])
            fuelInfo["canopy"] = float(fuelLoadingLookup[fccsNumber]["CANOPY"])
            fuelInfo["rot"] = float(fuelLoadingLookup[fccsNumber]["ROT"])
            fuelInfo["duff"] = float(fuelLoadingLookup[fccsNumber]["DUFF"])
            fuelInfo["litter"] = float(fuelLoadingLookup[fccsNumber]["LITTER"])
            fuelInfo["metadata"]["VEG"] = fuelLoadingLookup[fccsNumber]["VEG"]
        
        self.log.info("Successfully added fuel loadings "
                      "for %d of %d input fires", nSuccess, nFires)
        
        #
        # Set output plug to updated fireInfo
        #
        self.set_output("fires", fireInfo)
