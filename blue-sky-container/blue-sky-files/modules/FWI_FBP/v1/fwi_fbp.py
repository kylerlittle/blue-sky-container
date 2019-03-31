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
from kernel.core import Process
from kernel import location
from kernel.types import construct_type
from kernel.bs_datetime import BSDateTime, utc, timezone_from_str, FixedOffset
from kernel.structure import Structure, TemporalStructure
from datetime import timedelta


class FWI_FBP(Process):
   """ Use the Parks Canada FWI and FBP codes to calculate the Consumption
       and Fire Weather Index values.
   """

   def init(self):
      self.declare_input("canada_input","CanadianFireInformation")
      self.declare_output("fires","FireInformation")
      self.declare_output("canada_output","CanadianFireInformation")

   def run(self,context):
      inputData = self.get_input("canada_input")
      fireInfo = construct_type("FireInformation")
      
      location_number = 0                  #counter used to generate output days

      # grab variables from *.ini file
      FWI_executable = self.config("FWI_EXE")
      FBP_executable = self.config("FBP_EXE")
      FWI_input_file = self.config("FWI_DATA")
      FBP_input_file = self.config("FBP_DATA")

			#  MASTER LOOP over all Canadian fire objects
      for canadianFireLoc in inputData.fire_locations:

          # create output fire object
          fireLoc = construct_type("FireLocationData")

          # create FWI input file
          FWI_input = open(FWI_input_file,'w')
          FWI_input.write('WS %s\n' % canadianFireLoc['ws'])
          FWI_input.write('FFMC %s\n' % canadianFireLoc['ffmc'])
          FWI_input.write('DMC %s\n' % canadianFireLoc['dmc'])
          FWI_input.write('DC %s\n' % canadianFireLoc['dc'])
          FWI_input.write('ISI\n')
          FWI_input.write('BUI\n')
          FWI_input.write('FWI\n')
          FWI_input.write('DSR\n')
          FWI_input.write('DAY 1.0\n')
          FWI_input.close()

          # execute FWI model
          self.binary_output = ""
          context.execute(FWI_executable,FWI_input_file,output_handler=self.output_handler)
          
          # read selected FWI outputs
          FWI_output_lines = self.binary_output.split('\n')
          for line in FWI_output_lines:
             results = line.split(' ')
             if results[0] == "FFMC":
                FFMC_value = results[1]
             elif results[0] == "ISI":
                ISI_value = results[1]
             elif results[0] == "BUI":
                BUI_value = results[1]
             elif results[0] == "FWI":
                FWI_value = results[1]

          # create FBP input file
          FBP_input = open(FBP_input_file,'w')
          FBP_input.write('FuelType %s\n' % canadianFireLoc['fueltype'])
          FBP_input.write('Dj %s\n' % canadianFireLoc['date_time'].strftime('%j'))
          FBP_input.write('t %s\n' % canadianFireLoc['hoursignition'])
          FBP_input.write('FFMC %s\n' % FFMC_value)
          FBP_input.write('ISI %s\n' % ISI_value)
          FBP_input.write('BUI %s\n' % BUI_value)
          FBP_input.write('WS %s\n' % canadianFireLoc['ws'])
          FBP_input.write('WD %s\n' % canadianFireLoc['wd'])
          FBP_input.write('GS %s\n' % canadianFireLoc['slope'])
          FBP_input.write('Aspect %s\n' % canadianFireLoc['aspect'])
          FBP_input.write('C %s\n' % canadianFireLoc['c'])
          FBP_input.write('LAT %s\n' % canadianFireLoc['latitude'])
          FBP_input.write('LON %s' % canadianFireLoc['longitude'])
          FBP_input.close()

          # execute FBP model
          self.binary_output = ""
          context.execute(FBP_executable,FBP_input_file,output_handler=self.output_handler)

          # read selected outputs in Canadian units
          FBP_output_lines = self.binary_output.split('\n')
          for line in FBP_output_lines:
             results = line.split(' ')
             if results[0] == "TFC":
                TFC_value = results[1]     # kg/m2
             elif results[0] == "ROS":
                ROS_value = results[1]     # m/min
             elif results[0] == "SFC":
                SFC_value = results[1]     # kg/m2
             elif results[0] == "HFI":
                HFI_value = results[1]     # kW/m
                
          # convert TFC (kg/m^2) to tons/acre (1 kg/m^2 = 4.46089561 tons/acre)
          TFC_tons = float(TFC_value) * 4.46089561
          
          # calculate consumption values
          cons = construct_type("ConsumptionData")
          cons.flaming = float(TFC_tons) * 0.5
          cons.smoldering = float(TFC_tons) * 0.5
          cons.residual = 0.0
          cons.duff = float(TFC_tons) * 0.5

          # fill the output fire object
          fireLoc["id"] = canadianFireLoc['id']
          fireLoc["latitude"] = canadianFireLoc['latitude']
          fireLoc["longitude"] = canadianFireLoc['longitude']
          fireLoc["date_time"] = canadianFireLoc['date_time']
          fireLoc["slope"] = canadianFireLoc['slope']
          fireLoc["area"] = canadianFireLoc['area_ha'] * 2.47105381 # convert from hectares to acres
          fireLoc["consumption"] = cons
          
          # fill the output Canadian fire object
          canadianFireLoc["isi"] = ISI_value
          canadianFireLoc["bui"] = BUI_value
          canadianFireLoc["fwi"] = FWI_value
          canadianFireLoc["tfc"] = TFC_value
          canadianFireLoc["ros"] = ROS_value
          canadianFireLoc["sfc"] = SFC_value
          canadianFireLoc["hfi"] = HFI_value

          fireInfo.addLocation(fireLoc)
          location_number += 1

      # populate output files
      self.set_output("fires", fireInfo)
      self.set_output("canada_output", inputData)

   # handle standard output from FWI and FBP models
   def output_handler(self, logger, output, is_stderr):
      if is_stderr:
          logger.error(output)
      else:
          self.binary_output += output + "\n"


class InputCanadianFireFiles(Process):
   """ This is part of the new Canadian fire locations object, used to keep
       users from trying to mix American and Canadian fire science methods.
   """

   def init(self):
       self.declare_input("canada_input","CanadianFireInformation")
       self.declare_output("fires","CanadianFireInformation", cache=False)
      
   def run(self, context):
       fireInfo = self.get_input("canada_input")
       if fireInfo is None:
           fireInfo = construct_type("CanadianFireInformation")

       input_files = self.get_input_files(fireInfo)

       for fileInfo in input_files:
           locFile = fileInfo["locations_filename"]
           self.read_fire_locations(locFile, fireInfo)

       self.set_output("fires", fireInfo)


   def get_input_files(self, fireInfo):
       inputFiles = list()

       if self.config("USE_DAILY_FILE_PATTERNS", asType=bool):
           locationspattern = self.config("LOCATIONS_PATTERN")

           date = fireInfo["emissions_start"]
           while date < fireInfo["emissions_end"]:
               f = date.strftime(locationspattern)
               if os.path.exists(f):
                   info = construct_type("InputFileInfo")
                   info["locations_filename"] = f

                   inputFiles.append(info)
               date += timedelta(days=1)

       else:
           inputDir = self.config("INPUT_DIR")
           locationsfile = self.config("LOCATIONS_FILE")

           f = os.path.join(inputDir, locationsfile)
           if os.path.exists(f):
               info = construct_type("InputFileInfo")
               info.locations_filename = f
               inputFiles.append(info)

       return inputFiles

   def read_fire_locations(self, locations_filename, fireInfo):
       self.log.info("Reading Canadian fire locations from standard format file")
       num_fires = 0

       fireInfo.fire_locations = []
       
       f = open(locations_filename, "rb")
       for row in csv.DictReader(f):
           try:
               row = self.check_record(row, ["id", "latitude", "longitude", "date_time"])
               
               num_fires += 1
               fire = construct_type("CanadianFireLocation")
               
               # Populate the CanadianFireLocationData object
               for key, value in row.iteritems():
                   
                   fire[key] = value
                   
                   # Try to set the value into an object field; if we can't, it's metadata
                   found_it = fire.set_value(key, value, hour=None)
                   if not found_it:
                       self.log.debug('Unable to set value for "%s" field, assuming it is metadata', k)
                       fire.metadata[key] = value
                
               # Add our new location to the CanadianFireLocation object
               fireInfo.fire_locations.append(fire)
               
           except StandardError, err:
               self.log.warn("WARNING: %s %s", type(err), err)
               
       f.close()
       self.log.info("Successfully read %d Canadian fire locations", num_fires)
       
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

class OutputCanadianFireFiles(Process):
    """ Output Canadian fire information in BlueSky standard CSV format """

    def init(self):
        self.declare_input("fires", "CanadianFireInformation")

    def run(self, context):
        self.write_standard_files()
        
    def get_filenames(self):
        date = self.config("DATE", BSDateTime)

        locations_filename = os.path.join(
            self.config("OUTPUT_DIR"), 
            self.config("OUTPUT_LOCATIONS_FILE"))
        if "%" in locations_filename:
            locations_filename = date.strftime(locations_filename)
        
        return locations_filename

    def write_standard_files(self):
        locations_filename = self.get_filenames()
        fireInfo = self.get_input("fires")
        
        self.log.info("Writing Canadian fire locations to standard format file")
        number_fires = 0

        f = open(locations_filename, "w")
        f.write("id,event_id,latitude,longitude,date_time,ffmc,dmc,dc,hoursignition,ws,wd,slope,aspect,fueltype,\
        area_ha,isi,bui,fwi,tfc,ros,sfc,hfi\n")
        for loc in fireInfo.fire_locations:
            f.write("%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n" % (loc.id, loc.event_id, \
            loc.latitude, loc.longitude, loc.date_time, loc.ffmc, loc.dmc, loc.dc, loc.hoursignition, loc.ws, loc.wd, \
            loc.slope, loc.aspect, loc.fueltype, loc.area_ha, loc.isi, loc.bui, loc.fwi, loc.tfc, loc.ros, loc.sfc, loc.hfi))
            number_fires = int(number_fires) + 1
        f.close()
        
        self.log.info("Successfully wrote %d Canadian fire locations", number_fires)
        
