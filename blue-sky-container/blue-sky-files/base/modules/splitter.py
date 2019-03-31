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

#############################################
class ConsolidateFires(Process):
    def init(self):
        self.declare_input("fires", "FireInformation", multiInput=True)
        self.declare_input("precedence", "int", multiInput=True)
        self.declare_output("fires", "FireInformation")
        
    def run(self, context):
        inputFires = self.get_input("fires")
        precedences = self.get_input("precedence")
        if len(precedences) == 1:
            precedences = [int(precedences[0])] * len(inputFires)
        inputs = sorted(zip(precedences, inputFires))
        
        fires = construct_type("FireInformation")
        
        for precedence, fireInfo in inputs:
            for fireEvent, fireLoc in fireInfo.iterLocations():
                fires.addEventLocation(fireEvent, fireLoc)

        if len(fires.locations()) == 0:
            if self.config("STOP_IF_NO_BURNS", bool):
                raise Exception("There are currently zero fire locations to burn; stop.")
        self.set_output("fires", fires)


#############################################
class FireTypeSplitter(Process):
    def init(self):
        self.declare_input("fires", "FireInformation")
        self.declare_output("wildfires", "FireInformation")
        self.declare_output("prescribed_fires", "FireInformation")
        self.declare_output("other_fires", "FireInformation")
        
    def run(self, context):
        fireInfo = self.get_input("fires")
        wf = construct_type("FireInformation")
        rx = construct_type("FireInformation")
        other = construct_type("FireInformation")
        
        for fireEvent, fireLoc in fireInfo.iterLocations():
            if fireLoc["type"] in ("WF", "WFU"):
                wf.addEventLocation(fireEvent, fireLoc)
            elif fireLoc["type"] in ("AG", "RX"):
                rx.addEventLocation(fireEvent, fireLoc)
            else: # Unknown or other
                other.addEventLocation(fireEvent, fireLoc)

        self.set_output("wildfires", wf)
        self.set_output("prescribed_fires", rx)
        self.set_output("other_fires", other)
