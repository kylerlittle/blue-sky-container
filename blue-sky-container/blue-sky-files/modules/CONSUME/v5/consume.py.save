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

#***************Bluesky Framework Consume Module Version Notes*****************
#
#   Version 3 - A new Python-based Consume module is introduced. Also:
#               1) a template is used for input cases where FCCS was not used
#               2) prescribed burn functionality was included
#
#               John Stilley,  Sonoma Tech., Inc., March 2011
#
#   Version 4 - I am updating for the following issues:
#               1) FERA produced a new fuel_loadings.xml file
#               2) canopy consumption is exposed in the fire object metadata
#               3) the ecoregion will be exposed and searched based upon a map
#               4) prescribed burning depricated as Consume does't support them
#               5) some code re-factoring to make it easier to follow.
#
#               John Stilley,  Sonoma Tech., Inc., January 2012
#
#******************************************************************************

_bluesky_version_ = "3.5.1"

from consumption import Consumption
from kernel.types import construct_type
from kernel.grid import open_grid
from string import Template
import tempfile
import sys
import os
import csv
import mapscript
try:
  from osgeo import ogr, osr
except ImportError:
  import ogr, osr
import fuel_consumption as fc    # Contains python fuel consumption object
import input_variables as iv
import shutil
from live_fuel_moisture import process_lfm

def tonsPerAcrePerInch(param):
    if param == "litter":
        return 8.0
    else:
        self.log.warn("No tons-per-acre-per-inch for param " + param + ", using 1")
        return 1.0

def inchesFromTPA(loading, param):
    return str(float(loading[param]) / tonsPerAcrePerInch(param))

class CONSUME(Consumption):
    """ CONSUME Consumption Module """

    def run(self, context):
        fireInfo = self.get_input("fires")

        self.log.info("Running CONSUME Consumption model")
        num_fires = 0

        #If LFM data is used, create the path to where the lfm data will reside, and create a template header file
        if self.config("USE_LFM_DATA") == "YES":
            lfm_path = self.config("LFM_PATH")
            lfm_header = self.config("LFM_HEADER")
            lfm_header_name = self.config("LFM_HEADER_NAME")
            if not os.path.exists(r""+lfm_path+""): # This will likely always already exist, but may not contain a header file
                os.makedirs(r""+lfm_path+"")

            if (os.path.isfile(r""+lfm_path+lfm_header_name+"") == False):
                shutil.copy2(r""+lfm_header+"",r""+lfm_path+lfm_header_name+"")

        # Open fuel loadings XML file and create Consume object
        fccsFile = self.config("FCCS_XML")
        xml_obj = fc.FuelConsumption(fccs_file=fccsFile)  # object from master XML file

        #  MASTER LOOP over all fire objects
        for fireLoc in fireInfo.locations():

            # reset inputs and outputs in Consume object
            xml_obj.reset_inputs_and_outputs()

            if fireLoc["consumption"] is not None:
                self.log.debug("Skipping %s because it already has consumption data" % fireLoc["id"])
                continue

            if fireLoc["fuels"] is None:
                self.log.debug("Fire %s has no fuel loading; skip...", fireLoc["id"])
                continue

            # Set Canopy Consumption Variable
            canopyFraction = fireLoc["metadata"].get("canopy_fraction", None)
            canopyFraction = self.calc_canopyFraction(canopyFraction, fireLoc['type'], fireLoc['area'])
            # Check if inputs come from FCCS or NFDRS/Hardy
            fccsNumber = fireLoc["fuels"]["metadata"].get("fccs_number", None)

            # Define the Vegetation Type for each fuelbed.
            if self.config("USE_LFM_DATA") == "YES":
                veg_type = self.determine_veg_type(fccsNumber)

            # Derive the Live Fuel Consumption from LFM value in data file
            if self.config("USE_LFM_DATA") == "YES":
                lfm_value = process_lfm(fireLoc["latitude"],fireLoc["longitude"],str(fireLoc["date_time"]),lfm_path)
                if lfm_value >= 0:
                    canopyFraction = self.determine_CanopyConsumption_from_LFM(lfm_value, veg_type)
                else:
                    canopyFraction = self.calc_canopyFraction(canopyFraction, fireLoc['type'], fireLoc['area'])
            else:
                canopyFraction = self.calc_canopyFraction(canopyFraction, fireLoc['type'], fireLoc['area'])

            # IF there is no FCCS number, ELSE there is a FCCS number
            if fccsNumber is None or fccsNumber < 1:
                self.log.debug("Using FCCS template")

                # Coerce the fuel loading record into a new FCCS XML file for CONSUME
                templateFile = self.fcssXMLFileFromLoading(context, fireLoc["fuels"])
                temp_obj = fc.FuelConsumption(fccs_file=templateFile)

                # load extra fire parameters and then run the Consume Results method
                temp_obj = self.fill_extra_fire_params(temp_obj, fccsNumber, canopyFraction, fireLoc)
                cons = self.readConsumption(fireLoc, temp_obj)
            else:
                self.log.debug("Using FCCS number: %s", str(fccsNumber))

                # load extra fire parameters and then run the Consume Results method
                xml_obj = self.fill_extra_fire_params(xml_obj, fccsNumber, canopyFraction, fireLoc)
                cons = self.readConsumption(fireLoc, xml_obj)

            fireLoc["consumption"] = cons
            num_fires += 1

            veg_type = -1

        self.set_output("fires", fireInfo)

    def fcssXMLFileFromLoading(self, context, loading):
        """ creates FCCS XML fuel loading from a FuelsData record """

        # take care of any null values (KJC)
        fuel_keys = [ "fuel_1hr", "fuel_10hr", "fuel_100hr", "fuel_1khr",
                      "fuel_10khr", "fuel_gt10khr", "shrub", "grass", "rot",
                      "duff", "litter"]
        for k in fuel_keys:
            if loading[k] is None:
                loading[k] = 0.0

        # read the template file into a string
        fccsTemplateFile = open(self.config("FCCS_TEMPLATE"), "r")
        fccsTemplate = ""
        for line in fccsTemplateFile:
            fccsTemplate += line
        fccsTemplateFile.close()
        fccsTemplate = Template(fccsTemplate)

        # do the variable substitution on the template string
        thirdOfRot = str(float(loading["rot"]) / 3.0)
        fccsTemplate = fccsTemplate.substitute(CANOPY=loading["canopy"],
                                                 SHRUB=loading["shrub"],
                                                 GRASS=loading["grass"],
                                                 FUEL_1HR=loading["fuel_1hr"],
                                                 FUEL_10HR=loading["fuel_10hr"],
                                                 FUEL_100HR=loading["fuel_100hr"],
                                                 FUEL_1KHR=loading["fuel_1khr"],
                                                 FUEL_10KHR=loading["fuel_10khr"],
                                                 FUEL_GT10KHR=loading["fuel_gt10khr"],
                                                 ROT1=thirdOfRot,
                                                 ROT2=thirdOfRot,
                                                 ROT3=thirdOfRot,
                                                 LITTER_DEP=inchesFromTPA(loading, "litter"),
                                                 DUFF=loading["duff"],
                                                 ECOREGION=self.config("ECO_REGION"),
                                                 SNAGS=self.config("SNAGS"),
                                                 COVER_TYPE=self.config("COVER_TYPE"),
                                                 SHRUBS_LIVE=self.config("SHRUBS_LIVE"),
                                                 SHRUBS_2LIVE=self.config("SHRUBS_2LIVE"),
                                                 GRASS_LIVE=self.config("GRASS_LIVE"),
                                                 GRASS_2LIVE=self.config("GRASS_2LIVE"),
                                                 LITTER_PERC=self.config("LITTER_PERC"),
                                                 LICHEN=self.config("LICHEN"),
                                                 LICHEN_PERC=self.config("LICH_PERC"),
                                                 MOSS=self.config("MOSS"),
                                                 MOSS_PERC=self.config("MOSS_PERC"),
                                                 MOSS_TYPE=self.config("MOSS_TYPE"),
                                                 LITTER=self.config("LITTER"),
                                                 LITTER_EXTRA=self.config("LITTER_EXTRA"),
                                                 DUFF_TOTAL=self.config("DUFF_TOTAL"),
                                                 DUFF_PERC=self.config("DUFF_PERC"),
                                                 DUFF_DER_UP=self.config("DUFF_DER_UP"),
                                                 DUFF_LOWER=self.config("DUFF_LOWER"),
                                                 DUFF_LOW_PERC=self.config("DUFF_LOW_PERC"),
                                                 DUFF_DER_LOW=self.config("DUFF_DER_LOW"),
                                                 BAS=self.config("BAS"),
                                                 SM=self.config("SM"),
                                                 CAN_CONS=self.config("CAN_CONS"))

        # Write the template string to a new FCCS XML file and return the filename
        self.log.debug("Writing FCCS record info to XML file")
        xmlfile = context.full_path("fccs_record.xml")
        f = open(xmlfile, "w")
        f.write(fccsTemplate)
        f.close()
        return xmlfile

    def calc_canopyFraction(self, canopyFraction, fire_type, fire_area):
        if canopyFraction in (None, "", "auto"):
            # default method if canopy consumption fraction is not given
            if fire_type == 'Unknown':
                if fire_area > 150:
                    canopyFraction = 0.4
                else:
                    canopyFraction = 0.0
            elif (fire_type == 'WF'):
                canopyFraction = 0.6
            elif (fire_type == 'WFU'):
                canopyFraction = 0.4
            else:
                canopyFraction = 0.0
        else:
            # Some validation on the user-defined canopy consumption value
            if( float(canopyFraction) >= 0.0 and float(canopyFraction) <= 1.0 ):
                canopyFraction = float(canopyFraction)
            elif( float(canopyFraction) < 0 ):
                canopyFraction = 0.0
            elif( float(canopyFraction) > 1.0 ):
                canopyFraction = 1.0
            else:
                canopyFraction = 0.0

        return canopyFraction

    def determine_CanopyConsumption_from_LFM(self, lfmc_value, veg_type):
        """ Determine the 'fraction of canopy consumed' for Live fuel moisture.
        These relations were derived in-house by Dana Sullivan and Sean Raffuse
        after a thorough literature review. """
        if veg_type == 1:    # Aspen
            if lfmc_value <= 60:
                canopyFraction = 100.0
            elif (lfmc_value > 60) and (lfmc_value < 162):
                canopyFraction = 123.57 - (0.1786 * lfmc_value) - (0.0036 * lfmc_value * lfmc_value)
            else:
                canopyFraction = 0
        elif veg_type == 2:    # Boreal
            if lfmc_value <= 85:
                canopyFraction = 100.0
            elif (lfmc_value > 85) and (lfmc_value < 142):
                canopyFraction = -155 + (5.8333 * lfmc_value) - (0.0333 * lfmc_value * lfmc_value)
            else:
                canopyFraction = 0
        elif veg_type == 3:    # Closed Conifer Forest
            if lfmc_value <= 85:
                canopyFraction = 100.0
            elif (lfmc_value > 82) and (lfmc_value < 127):
                canopyFraction = -240 + (8.25 * lfmc_value) - (0.05 * lfmc_value * lfmc_value)
            else:
                canopyFraction = 0
        elif veg_type == 4:    # Eastern Deciduous Forest
            if lfmc_value <= 35:
                canopyFraction = 100.0
            elif (lfmc_value > 35) and (lfmc_value < 111):
                canopyFraction = 122.88 - (0.4519 * lfmc_value) - (0.0058 * lfmc_value * lfmc_value)
            else:
                canopyFraction = 0
        elif veg_type == 5:    # Grassland
            if lfmc_value <= 30:
                canopyFraction = 100.0
            elif (lfmc_value > 30) and (lfmc_value < 67):
                canopyFraction = 74 + (2.4667 * lfmc_value) - (0.0533 * lfmc_value * lfmc_value)
            else:
                canopyFraction = 0
        elif veg_type == 6:    # Open Conifer Forests
            if lfmc_value <= 50:
                canopyFraction = 100.0
            elif (lfmc_value > 50) and (lfmc_value < 153):
                canopyFraction = 125.71 - (0.3714 * lfmc_value) - (0.0029 * lfmc_value * lfmc_value)
            else:
                canopyFraction = 0
        elif veg_type == 7:    # Pacific Broadleaved Forest
            if lfmc_value <= 40:
                canopyFraction = 100.0
            elif (lfmc_value > 40) and (lfmc_value < 115):
                canopyFraction = 105 + (0.2917 * lfmc_value) - (0.0104 * lfmc_value * lfmc_value)
            else:
                canopyFraction = 0
        elif veg_type == 8:    # Riparian
            if lfmc_value <= 40:
                canopyFraction = 100.0
            elif (lfmc_value > 40) and (lfmc_value < 111):
                canopyFraction = 122.88 - (0.4519 * lfmc_value) - (0.0058 * lfmc_value * lfmc_value)
            else:
                canopyFraction = 0
        elif veg_type == 9:    # Savanna
            if lfmc_value <= 79:
                canopyFraction = 100.0
            elif (lfmc_value > 79) and (lfmc_value < 108):
                canopyFraction = 355 - (3.25 * lfmc_value)
            else:
                canopyFraction = 0
        elif veg_type == 10:   # Shrubland
            if lfmc_value <= 79:
                canopyFraction = 100.0
            elif (lfmc_value > 79) and (lfmc_value < 108):
                canopyFraction = 355 - (3.25 * lfmc_value)
            else:
                canopyFraction = 0
        elif veg_type == 0:
            canopyFraction = 0
        elif veg_type == -1:
            canopyFraction = 0

        if canopyFraction > 100.0:
            canopyFraction = 100.0

        canopyFraction = canopyFraction / 100.0
        canopyFraction = round(canopyFraction, 3)
        return canopyFraction

    def determine_veg_type(self, fccsNumber):
        """ Determine the Vegetation Type for each fuelbed (for LFM) """
        # Map fuelbed # to vegetation type #
        veg_type_1 = [42,142,143,224]
        veg_type_2 = [140,279]
        veg_type_3 = [2,5,7,8,10,12,17,22,34,37,38,39,47,52,59,70,138,155,208,238,273,287]
        veg_type_4 = [90,109,110,123,180,186,265,266,267,268,274,275,276]
        veg_type_5 = [41,57,63,65,66,131,133,175,203,236,280]
        veg_type_6 = [16,18,24,27,28,45,53,107,114,157,164,166,182,184,187,189,211,281,282]
        veg_type_7 = [6,14,36,48]
        veg_type_8 = [1,272,283,284,288]
        veg_type_9 = [43,55,154,173,174,232,264,289]
        veg_type_10 = [20,30,44,46,49,51,56,69,168,210,218,237,240]

        if fccsNumber == 0:
           veg_type = 0    # Exempt or Urban
        elif fccsNumber in veg_type_1:
           veg_type = 1    # Aspen
        elif fccsNumber in veg_type_2:
           veg_type = 2    # Boreal
        elif fccsNumber in veg_type_3:
           veg_type = 3    # Closed Conifer Forest
        elif fccsNumber in veg_type_4:
           veg_type = 4    # Eastern Deciduous Forest
        elif fccsNumber in veg_type_5:
           veg_type = 5    # Grassland
        elif fccsNumber in veg_type_6:
           veg_type = 6    # Open Conifer Forests
        elif fccsNumber in veg_type_7:
           veg_type = 7    # Pacific Broadleaved Forest
        elif fccsNumber in veg_type_8:
           veg_type = 8    # Riparian
        elif fccsNumber in veg_type_9:
           veg_type = 9    # Savanna
        elif fccsNumber in veg_type_10:
           veg_type = 10   # Shrubland
        else:
           veg_type = -1

        return veg_type


    # fill non-XML fire parameters from fire_locations.csv
    def fill_extra_fire_params(self, fc_obj, fccsNumber, canopyFraction, fireLoc):
        # manually set the fccs number list that was built by Consume from the XML file
        # This has to be done because the fuel consumption object in Consume is a singleton
        # except for this variable, but we need a full object functionality.
        iv.NaturalInputVarParameters[0][3] = fc_obj.FCCS.valids

        # We are currently assuming that all fires are 'natural' fires, because the
        # 'activity' fire logic in the Consume model is not fully implemented.
        fc_obj.burn_type = 'natural'

        # In the case where we don't assign a fuelbed ID, the template is being called
        # and the template has a default fuelbed value of 1.
        if fccsNumber is not None and fccsNumber > 0:
           fc_obj.fuelbed_fccs_ids = fccsNumber
        fc_obj.fuelbed_area_acres = fireLoc['area']
        fc_obj.fuel_moisture_1000hr_pct = fireLoc["fuel_moisture"]["moisture_1khr"]
        fc_obj.fuel_moisture_10hr_pct = fireLoc["fuel_moisture"]["moisture_10hr"]
        fc_obj.fuel_moisture_duff_pct = fireLoc["fuel_moisture"]["moisture_duff"]
        fc_obj.canopy_consumption_pct = canopyFraction * 100

        if self.config("USE_LFM_DATA") == "YES":
           fc_obj.shrub_blackened_pct = canopyFraction * 100
        else:
           fc_obj.shrub_blackened_pct = float(self.config("SHRUB_PERCENT_BLACKENED"))
        fc_obj.output_units = 'tons_ac'

        # A separate algorithm is needed to fill the ecoregion variable.
        ecoregion_shapefile = self.config("ECOREGION_SHAPEFILE")
        region = self.locate_ecoregion(fireLoc["latitude"], fireLoc["longitude"],ecoregion_shapefile)
        excepted_values = ["western","southern","boreal"]
        if region not in excepted_values:
           region = "western"
        fc_obj.fuelbed_ecoregion = region

        return fc_obj

    # runs Consume and collects the outputs
    def readConsumption(self, fireLoc, fc_obj):
        cons = construct_type("ConsumptionData")
        cons.flaming = 0.0
        cons.smoldering = 0.0
        cons.residual = 0.0
        cons.duff = 0.0

        # Call the CONSUME results package one time by creating a results object.
        consResults = fc_obj.results()

        flaming = consResults['consumption']['summary']['total']['flaming']
        smoldering = consResults['consumption']['summary']['total']['smoldering']
        residual = consResults['consumption']['summary']['total']['residual']
        duff = consResults['consumption']['summary']['ground fuels']['total']

        # Fill our ConsumptionData structure
        cons.flaming = float(flaming)
        cons.smoldering = float(smoldering)
        cons.residual = float(residual)
        cons.duff = float(duff)

        return cons

    #Return the ecoregion for this location (as an int)
    #Returns the string "Unknown" if the time zone could not be determined.
    #Raises an exception if the time zone data file could not be opened.
    def locate_ecoregion(self, latitude, longitude, inData):

        # Instantiate mapscript shapefileObj
        # will later be used to read features in the shapefile
        shpfile = mapscript.shapefileObj(inData, -1)     # -1 indicates file already exists
        numShapes = shpfile.numshapes                    # stores the number of shapes from the shapefileObj

        # store fire location longitude, latitude in mapscript pointOb
        # used to determine if pointObj is within global region features
        point = mapscript.pointObj(longitude, latitude)

        # determine if feature in shpfile contains fire location point
        ecoregion_number = 0
        while (ecoregion_number < numShapes):
            shape = shpfile.getShape(ecoregion_number)
            if shape.contains(point):
                break
            else:
                ecoregion_number += 1

        # get the shapefile driver
        driver = ogr.GetDriverByName('ESRI Shapefile')

        # open the data source
        datasource = ogr.Open(inData)
        if datasource is None:
            self.log.info("Could not open time zone shapefile")

        # get the data layer
        layer = datasource.GetLayerByIndex(0)
        layer.ResetReading()

        feature = layer.GetFeature(ecoregion_number)

        # test if the lat/lon was found inside one of the ecoregions
        if feature is None:
            val = 0
        else:
            val = feature.GetFieldAsString('DOMAIN')

        # close the data source
        datasource.Destroy()

        # if the value is empty, assign it to zero
        if val in ("", None):
            val = 0

        return val
