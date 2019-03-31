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
from kernel.types import construct_type
from fuel_loading import FuelLoading
from consumption import Consumption
from time_profile import TimeProfile
from emissions import Emissions
from plume_rise import PlumeRise
from dispersion import Dispersion, DispersionMet
from trajectory import Trajectory, TrajectoryMet

class NoOp(Process):
    """ NoOp Module -- Just pass data through
        Also serves as a template for starting a new module.
    """

    def init(self):
        self.declare_input("in", "anything")
        self.declare_output("out", "anything")

    def run(self, context):
        self.log.debug("This module is currently unimplemented."
                       "  Passing data through unchanged.")
        my_input = self.get_input("in")
        self.set_output("out", my_input)

class InputNoFires(Process):
    def init(self):
        self.declare_input("fires", "FireInformation")
        self.declare_output("fires", "FireInformation")
        
    def run(self, context):
        fireInfo = self.get_input("fires")
        if fireInfo is None:
            fireInfo = construct_type("FireInformation")
        self.set_output("fires", fireInfo)
             
class NoOpFireInformation(Process):
    def init(self):
        self.declare_input("fires", "FireInformation")
        self.declare_output("fires", "FireInformation")
        
    def run(self, context):
        self.set_output("fires", self.get_input("fires"))
        
class NoFuelLoading(FuelLoading):
    def run(self, context):
        self.set_output("fires", self.get_input("fires"))

class NoConsumption(Consumption):
    def run(self, context):
        self.set_output("fires", self.get_input("fires"))
        
class NoTimeProfile(TimeProfile):
    def run(self, context):
        self.set_output("fires", self.get_input("fires"))

class NoEmissions(Emissions):
    def run(self, context):
        self.set_output("fires", self.get_input("fires"))
        
class NoPlumeRise(PlumeRise):
    def run(self, context):
        self.set_output("fires", self.get_input("fires"))

class NoDispersionMet(DispersionMet):
    def run(self, context):
        self.set_output("met_info", self.get_input("met_info"))

class NoDispersion(Dispersion):
    def run(self, context):
        self.set_output("fires", self.get_input("fires"))

class NoTrajectoryMet(TrajectoryMet):
    def run(self, context):
        self.set_output("met_info", self.get_input("met_info"))

class NoTrajectory(Trajectory):
    def run(self, context):
        self.set_output("fires", self.get_input("fires"))

