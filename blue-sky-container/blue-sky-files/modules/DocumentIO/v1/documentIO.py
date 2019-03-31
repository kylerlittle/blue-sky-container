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

from kernel.core import Process
from kernel.types import construct_type, get_type_constructor
import csv

class DocumentIO(Process):
    def init(self):
        self.declare_input("fires", "FireInformation")
        self.declare_output("fires", "FireInformation")
        
    def run(self,context):
        """Document how to work with the BlueSky FireInformation data structure"""

        # Retrieve the fireInformation structure passed from a previous module
        fireInfo = self.get_input("fires")
         
        # A FireInformation data structure (such as FireInfo here) contains a list of 
        #    FireLocationData structures, which hold basic information about each fire.  
        #    Each FireLocationData structure may also contain additional
        #    data objects, including: FuelsData, ConsumptionData, EmissionsData,
        #    TimeProfileData, and PlumeRiseData
        
        # Retrieve the total number of fires in the FireInformation structure
        nFires = len(fireInfo.locations())
        
        # Output this result as an INFO statement to the screen and to the run.log file
        self.log.info("found %s fires in input FireInformation structure" % nFires)
        
        # Documentation and example usage of each data object that can exist in a FireInformation
        #    data structure can be found in the functions below:
        
        self.firelocation_demo(fireInfo)   # FireLocationData
        self.fuels_demo(fireInfo)          # FuelsData
        self.consumption_demo(fireInfo)    # ConsumptionData
        self.emissions_demo(fireInfo)      # EmissionsData
        self.timeprofile_demo(fireInfo)    # TimeProfileData and temporalizing EmissionsData
        self.plumerise_demo(fireInfo)      # PlumeRiseData
        
        # Demonstration of how to prepare FireInformation data for use by an external progarm,
        #   how to run an external program, and how to retrieve data from an external program
        #   to populate the appropirate FireInformation attributes
        
        self.external_program_demo(fireInfo,context)
        
        # declare output to be passed on to other modules
        self.set_output("fires", fireInfo)
        
    def firelocation_demo(self,fireInfo):
        """FIRE_LOCATION data example"""
        
        # A FireInformation data stucture contains a list of fireLocationData structures
        
        # Loop over all fires contained in a fireInformation data structure
        #    using the fireInfo.locations() method
        
        for fireLoc in fireInfo.locations():
        
            # Each fire is uniquely identified
            self.log.info("found fire ID %s" % fireLoc["id"])
            
            # Access or modify basic (and mandatory) information about the fire
            fireLoc["latitude"] = 35.0              # degrees north is positive
            fireLoc["longitude"] = -120.0           # degrees west is negative
            fireLoc["area"] = 500                   # size in acres
            fireLoc["date_time"] = '200905040700L'  # BlueSky date/time convention
            
        # Delete a fire (and all it's data) from a fireInfromation structure
        for fireLoc in fireInfo.locations():
            if fireLoc["latitude"] == 35.0:
                fireInfo.removeLocation(fireLoc)

        # Adding a new fireLocation to the fireInformation structure is as 
        #   easy as 1,2,3!
        #
        #   1)  Build a new fireLocation data structure
        #   2)  Add information elelments about the fire
        #   3)  Add the new fireLocation object to the fireInformation structure
        
        # First, build a new fireLocation data structure
        id = 'D00001'  # create an ID
        fireLoc = construct_type("FireLocationData", id)
        
        # Second, add a full complement of information about fire D0000.
        #   Note that some attributes are mandatory.
        fireLoc["latitude"] = 37.0              # Latitude (MANDATORY)
        fireLoc["longitude"] = -121.0           # Longitude (MANDATORY)
        fireLoc["area"] = 1000.0                # Fire size (acres) (MANDATORY)
        fireLoc["date_time"] = '200905050700L'  # Add date/time (BSDateTime) (MANDATORY)
        fireLoc["elevation"] = 243.0            # Elevation (meters)
        fireLoc["type"] = "WF"                  # Fire type (WF,WFU,AG,RX)
        fireLoc["scc"] = ""                     # SCC code (defined in fill_data.py)
        fireLoc["owner"] = "KJC"                # Owner string
        fireLoc["fips"] = ""                    # FIPS code
        fireLoc["slope"] = ""                   # Terrain slope
        fireLoc["state"] = "California"         # State/Province
        fireLoc["county"] = "Merced"            # County name
        fireLoc["country"] = "USA"              # Country name
        
        # DAP: Commented out 2010-04-07 because we now have the fireLoc["local_weather"]
        #      and fireLoc["fuel_moisture"] structures, which include these fields and more.
        
        # TO DO: Document these new structures here...
        
        #fireLoc["snow_month"] = 5               # Snow months per year (months)
        #fireLoc["rain_days"] = 8                # Days since last rain (days)
        #fireLoc["wind"] = 5.0                   # Surface wind speed (mph)
        #fireLoc["fuel_moisture_10hr"] = 1.0     # 10 hour fuel moisture (percent)
        #fireLoc["fuel_moisture_1khr"] = 0.0     # 10,000 hour fuel moisture (percent)
        
        # Add metadata to fire D0000
        fireLoc["metadata"]["contained"] = "No"
        
        # Finally, add new fire D0000 and its information to the 
        #   FireInformation object
        fireInfo.addLocation(fireLoc) # Add the new fire location to the FireInformation data structure

        # Associate fire D00001 with fire event D10000 and add this new event to the 
        #   fireInformation data structure 
        event_id = "D10000"
        fireEvent = construct_type("FireEventData")
        fireEvent["event_id"] = event_id
        fireEvent["event_name"] = "documentIO dummy event"
        fireEvent["metadata"]["owner"] = "KJC"
        fireInfo.addEvent(fireEvent)
        fireEvent.addLocation(fireLoc)
        
        # Loop through all fire events
        for event in fireInfo.events():
            continue
        
        return
        
    def fuels_demo(self,fireInfo):
        """FUELS data example"""
        
        # FuelsData objects contain information about the vegetation 
        #   and fuels that can be consumed in a fire
        
        # Loop over all fires
        for fireLoc in fireInfo.locations():
        
            # Build a FuelsData structure
            fuelInfo = construct_type("FuelsData")
            
            # Associate the FuelsData structure with fireLoc["fuels"] for this fire
            fireLoc["fuels"] = fuelInfo
            
            # Add fuels data for this fire
            fuelInfo["metadata"]["fccs_number"] = 0  # FCCS fuel load number (applicable to FCCS only)
            fuelInfo["fuel_1hr"] = 0.0           # 1 hour fuel (tons per acre)
            fuelInfo["fuel_10hr"] = 0.0          # 10 hour fuel (tons per acre)
            fuelInfo["fuel_100hr"] = 0.0         # 100 hour fuel (tons per acre)
            fuelInfo["fuel_1khr"] = 0.0          # 1,000 hour fuel (tons per acre)
            fuelInfo["fuel_10khr"] = 0.0         # 10,000 hour fuel (tons per acre)
            fuelInfo["fuel_gt10khr"] = 0.0       # > 10,000 hour fuel (tons per acre)
            fuelInfo["shrub"] = 0.0              # shrub fuel load (tons per acre)
            fuelInfo["grass"] = 0.0              # grass fuel load (tons per acre)
            fuelInfo["canopy"] = 0.0             # canopy fuel load (tons per acre)
            fuelInfo["rot"] = 1                  # rot fuel load (tons per acre)
            fuelInfo["duff"] = 0                 # duff fuel depth (inches)
            fuelInfo["litter"] = 14              # litter fuel load (tons per acre)
            
            # Any metadata can be added into fuelInfo["metadata"]
            fuelInfo["metadata"]["VEG"] = "Vegetation type" # metedata entry for vegetation type
        
        # Retrieve fuels information
        for fireLoc in fireInfo.locations():
        
            # Do this fire have fuels data?  Note that log.debug() logs a 
            #    DEBUG statement to run.log
            if fireLoc["fuels"] is None:
                self.log.debug("Fire %s has no fuel loading" % fireLoc["id"])
                continue
            
            # Is this fuel a non-FCCS fuel?
            fccsNumber = fireLoc["fuels"]["metadata"]["fccs_number"]
            if fccsNumber is None or fccsNumber < 0:
                self.log.debug("Fire %s is a non-FCCS fuel loading" % fireLoc["id"])
                continue
                
            # Modify fuels data elements
            fireLoc["fuels"]["fuel_1hr"]
            fireLoc["fuels"]["duff"]

        return
        
    def consumption_demo(self,fireInfo):
        """CONSUMPTION data example"""
        
        # ConsumptionData objects contain the amount of vegetation
        #    consumed in a fire
        
        # Loop over all fires
        for fireLoc in fireInfo.locations():
        
            # Build a ConsumptionData structure
            consumptionData = construct_type("ConsumptionData")
            
            # Associate the ConsumptionData structure with fireLoc["consumption"] for this fire
            fireLoc["consumption"] = consumptionData
            
            # Add consumption data values for this fire
            consumptionData["flaming"] = 10.0        # Flaming component of consumption (tons)
            consumptionData["smoldering"] = 99.0     # Smoldering component of consumption (tons)
            consumptionData["residual"] = 99.0       # Residual consumption (tons)
            consumptionData["duff"] = 99.0           # Duff consumption (tons)
        
        # Retrieve Consumption data
        for fireLoc in fireInfo.locations():
        
            # Does this fire have consumption data?
            if fireLoc["consumption"] is None:
                self.log.debug("Fire %s has no consumption data" % fireLoc["id"])
                continue
                
            # Modify consumption data elements
            fireLoc["consumption"]["flaming"] = 25.3
            fireLoc["consumption"]["smoldering"] = 50.1
            fireLoc["consumption"]["residual"] = 20.2
            fireLoc["consumption"]["duff"] = 1.5

        return
        
    def emissions_demo(self,fireInfo):
        """EMISSIONS data example"""
        
        # EmissionsData objects contain emissions rates due to 
        #    combustion by fire.  Each data element is a list that
        #    can be filled with one or more time periods of data.  
        #    EmissionsData objects also more complexe in that
        #    emissions can be split into flaming, smoldering, and 
        #    residual modes.
        
        # Loop over all fires
        for fireLoc in fireInfo.locations():
        
            # Build a EmissionsData structure
            if fireLoc["emissions"] is None:
                emissionsData = construct_type("EmissionsData")
                
            # Create an empty list for each element in EmissionsData.
            #   Note that the keys in EmissionsData are iterable
            
            for k in emissionsData.iterkeys():
                emissionsData[k] = []
        
            # Emissions for each species consists of a tuple of 
            #   three emissions modes.  Note that the time and heat
            #   elements are not represented as tuples.
            #
            #   EmissionsTuple(flaming_emis,smoldering_emis,residual_emis)
            
            # At this stage, we are only creating a total emissions value.
            #    (see timeprofile_demo to see how a temporal profile is applied)
            #    You could loop over hours to specify hourly emission rates.
            #
            
            emisRate = 5.00 # (units = tons)
            emissionsData["time"].append(0)        # time (hours)
            emissionsData["heat"].append(10000.0)  # heat release (BTU)
            emissionsData["pm25"].append(construct_type("EmissionsTuple", (emisRate, 0.0, 0.0))) # fine particulates 
            emissionsData["pm10"].append(construct_type("EmissionsTuple", (emisRate, 0.0, 0.0))) # coarse particulates
            emissionsData["pm"].append(construct_type("EmissionsTuple", (emisRate, 0.0, 0.0)))   # total particulates
            emissionsData["co"].append(construct_type("EmissionsTuple", (emisRate, 0.0, 0.0)))   # carbon monoxide
            emissionsData["co2"].append(construct_type("EmissionsTuple", (emisRate, 0.0, 0.0)))  # carbon dioxide
            emissionsData["ch4"].append(construct_type("EmissionsTuple", (emisRate, 0.0, 0.0)))  # methane
            emissionsData["nmhc"].append(construct_type("EmissionsTuple", (emisRate, 0.0, 0.0))) # non-methane hydrocarbons
            emissionsData["voc"].append(construct_type("EmissionsTuple", (emisRate, 0.0, 0.0)))  # volatile organic compounds
            emissionsData["nox"].append(construct_type("EmissionsTuple", (emisRate, 0.0, 0.0)))  # oxides of nitrogen
            emissionsData["nh3"].append(construct_type("EmissionsTuple", (emisRate, 0.0, 0.0)))  # ammonia
            emissionsData["so2"].append(construct_type("EmissionsTuple", (emisRate, 0.0, 0.0)))  # sulfur dioxide
            
            # Record the emissions data into the fireLocation structure
            fireLoc["emissions"] = emissionsData
            
            # Tuples are not mutable, i.e., they cannot be altered once they are created.
            #   To modify, for example, the CO smoldering emission rate, you need to re-construct the 
            #   entire tuple.
            fireLoc["emissions"]["co"][0] = construct_type("EmissionsTuple",(emisRate,emisRate,0.0))
            
            # Generate the total emissions for a given species and time
            totalCO = fireLoc["emissions"]["co"][0].sum()
            
            # Generate the total emissions over all modes and time periods
            totalCO = fireLoc["emissions"].sum("co")
            
        return
        
    def timeprofile_demo(self,fireInfo):
        """TIME_PROFILE data example"""
        
        # A TimeProfile object contains information about how to 
        #    temporally allocate total emissions into hourly emissions.
        
        # Loop over all fires
        for fireLoc in fireInfo.locations():
        
            # Build a TimeProfileData structure
            if fireLoc["time_profile"] is None:
                profileData = construct_type("TimeProfileData")
        
            # Create a profile (happens to be the WRAP profile)
            time_profile = [ 0.0057, 0.0057, 0.0057, 0.0057, 0.0057, 0.0057,
                             0.0057, 0.0057, 0.0057, 0.0057, 0.0200, 0.0400,
                             0.0700, 0.1000, 0.1300, 0.1600, 0.1700, 0.1200,
                             0.0700, 0.0400, 0.0057, 0.0057, 0.0057, 0.0057 ]
            
            # Assign profiles to the elements of TimeProfileData
            #    (Units = fraction for all elements)
            profileData["area_fract"] = time_profile[:]                 # area fraction time profile
            profileData["flame_profile"] = time_profile[:]              # flaming emissions profile
            profileData["smolder_profile"] = time_profile[:]            # smoldering emissions profile
            profileData["residual_profile"] = [0.0] * len(time_profile) # residual emissions profile
            
            # Add the new TimeProfileData structure to fireLoc["time_profile"]
            fireLoc["time_profile"] = profileData
            
        # Use the time profiles to temporally allocate emissions
        for fireLoc in fireInfo.locations():
        
            # Extract the time profile.  For simplicity, just use the flaming profile
            time_profile = fireLoc["time_profile"]["flame_profile"]
            
            # For clarity, pull out the emissions data from FireLoc
            emissionsData = fireLoc["emissions"]
            
            # Loop over all emissionsData elements
            for k in emissionsData.iterkeys():
            
                # Don't apply a profile to the time or metadata elements
                if k in ["time", "metadata"]:
                    continue
                
                # Avoid doing math on undefined data
                if emissionsData[k] is None:
                    continue
                    
                # Total emissions from all modes
                total = emissionsData.sum(k)
                
                # Apply the profile to the total emissions
                if k == "heat":
                    values = [(total * pct) for pct in time_profile]
                else:
                    values = [construct_type("EmissionsTuple", (total * pct, 0.0, 0.0))
                                      for pct in time_profile]
                
                # Set the EmissionsData structure, which now has hourly emission rates
                #   in units of tons per hour
                emissionsData[k] = values
                
            # Set the times from hour 0 to N based on the number of hours in the time profile
            emissionsData["time"] = range(len(time_profile))
            
            # Set the final hourly emissions into the fireLocation structure
            fireLoc["emissions"] = emissionsData

        return
        
    def plumerise_demo(self,fireInfo):
        """PLUME_RISE data example"""
        
        # A PlumeRise object contains information about 
        #    smoke plume characteristics.
        
        # Loop over all fires
        for fireLoc in fireInfo.locations():
        
            # Build a PlumeRise data structure
            if fireLoc["plume_rise"] is None:
                plumeriseData = construct_type("PlumeRise")
           
            # Create an empty list for all elements in PlumeRise
            plumeriseData["smoldering_fraction"] = []  # Smoldering fraction (fraction)
            plumeriseData["plume_bottom_meters"] = []  # Height of plume bottom (meters)
            plumeriseData["plume_top_meters"] = []     # Height of plume top (meters)
            
            # Set some dummy constant values
            smolderFraction = 0.75
            plumeBottom = 250.0
            plumeTop =    1000.0
            
            # Add houlry plume rise data
            for hour in range(len(fireLoc["time_profile"]["flame_profile"])):
                plumeriseData["smoldering_fraction"].append(smolderFraction)
                plumeriseData["plume_bottom_meters"].append(plumeBottom)
                plumeriseData["plume_top_meters"].append(plumeTop)
            
            # Set PlumeRiseData structure for this fire location
            fireLoc["plume_rise"] = plumeriseData
        
        return
        
    def external_program_demo(self,fireInfo,context):
        """"External program demonstration"""
        
        # External program demonstration
        #   -- Create a new fire location and add some dummy consumption data
        #   -- prepare data for use by an external program
        #   -- run an external program
        #   -- read data from the output of an external program
        #      and fill appropriate fireInformation data attributes
        
        # Note that we passed in a "context" object.  This contins the "context"
        #    (or current operating environment) in which BlueSky is operating.
        #    It provides the ability to, among other things, execute
        #    external programs.
        
        # 1) CREATE NEW FIRE LOCATION AND ADD SOME DUMMY DATA
        #    (see other demos for more detailed description of what's going on here)
        
        id = 'D00002'  # create an ID
        fireLoc = construct_type("FireLocationData", id)
        fireLoc["latitude"] = 38.0 
        fireLoc["longitude"] = -120.0
        fireLoc["area"] = 5000.0
        fireLoc["date_time"] = '200905050700L'
        fireInfo.addLocation(fireLoc)
        
        consumptionData = construct_type("ConsumptionData")
        fireLoc["consumption"] = consumptionData
        fireLoc["consumption"]["flaming"] = 25.3
        fireLoc["consumption"]["smoldering"] = 50.1
        fireLoc["consumption"]["residual"] = 20.2
        fireLoc["consumption"]["duff"] = 1.5
        
        # 2) PREPARE INPUT DATA (in this example, consumption data)
            
        # Create the input file name with full BlueSky working path
        infilename = context.full_path('documentIO_input.txt')
        
        # Write information to the input file
        infile = file(infilename,"w")
        infile.write("Flaming Consumption     | %-10.2f\n"  % fireLoc["consumption"]["flaming"])
        infile.write("Smoldering Consumption  | %-10.2f\n"  % fireLoc["consumption"]["smoldering"])
        infile.write("Residual Consumption    | %-10.2f\n"  % fireLoc["consumption"]["residual"])
        infile.write("Duff Consumption        | %-10.2f\n"  % fireLoc["consumption"]["duff"])
        infile.close()
            
        # Archive the input file
        context.archive_file(infilename)
            
        # 3) RUN EXTERNAL PROGRAM
            
        # Create the output file name with full BlueSky working path
        outfilename = context.full_path('documentIO_output.txt')
        
        # Get the program executable specified in documentIO.ini 
        DOCUMENTIO_BINARY = self.config("DOCUMENTIO_BINARY")
        
        # Execute the external program with arguments
        context.execute(DOCUMENTIO_BINARY,infilename,outfilename)
        
        # Archive the resulting output file
        context.archive_file(outfilename)
        
        # 4) READ OUTPUT FILE AND FILL FIREINFORMATION ATTRIBUTES
        
        # Create a new EmissionsData structure
        emissions = construct_type("EmissionsData")
        
        # The emissions data output file contains a header, and 
        #   three lines of data (flaming,smoldering, and residual)
        
        for row in csv.DictReader(open(outfilename,'r')):
            if row["emistype"] == "FLAMING   ":
                f_row = row.copy()
            if row["emistype"] == "SMOLDERING":
                s_row = row.copy()
            if row["emistype"] == "RESIDUAL  ":
                r_row = row.copy()
        
        # Create the EmissionsData structure and fill in the data
        
        emissionsData = construct_type("EmissionsData")
        for k in emissionsData.iterkeys():
            emissionsData[k] = []
        
        emissionsData["time"].append(0)
        emissionsData["pm25"].append(construct_type("EmissionsTuple", (f_row["pm25"],s_row["pm25"],r_row["pm25"])))
        emissionsData["pm10"].append(construct_type("EmissionsTuple", (f_row["pm10"],s_row["pm10"],r_row["pm10"])))
        emissionsData["pm"].append(construct_type("EmissionsTuple",   (f_row["pm"]  ,s_row["pm"]  ,r_row["pm"])))
        emissionsData["co"].append(construct_type("EmissionsTuple",   (f_row["co"]  ,s_row["co"]  ,r_row["co"])))
        emissionsData["co2"].append(construct_type("EmissionsTuple",  (f_row["co2"] ,s_row["co2"] ,r_row["co2"])))
        emissionsData["ch4"].append(construct_type("EmissionsTuple",  (f_row["ch4"] ,s_row["ch4"] ,r_row["ch4"])))
        emissionsData["nmhc"].append(construct_type("EmissionsTuple", (f_row["nmhc"],s_row["nmhc"],r_row["nmhc"])))
        emissionsData["voc"].append(construct_type("EmissionsTuple",  (f_row["voc"] ,s_row["voc"] ,r_row["voc"])))
        emissionsData["nox"].append(construct_type("EmissionsTuple",  (f_row["nox"] ,s_row["nox"] ,r_row["nox"])))
        emissionsData["nh3"].append(construct_type("EmissionsTuple",  (f_row["nh3"] ,s_row["nh3"] ,r_row["nh3"])))
        emissionsData["so2"].append(construct_type("EmissionsTuple",  (f_row["so2"] ,s_row["so2"] ,r_row["so2"])))
        fireLoc["emissions"] = emissionsData
        
        return
        
