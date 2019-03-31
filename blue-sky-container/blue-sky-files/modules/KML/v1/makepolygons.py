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

import os
import tempfile
import zipfile
import numpy
from datetime import datetime, timedelta
from Scientific.IO.NetCDF import NetCDFFile

from kernel.core import Process
from kernel.types import construct_type
from kernel.bs_datetime import BSDateTime
from kernel.log import OUTPUT
from kml_from_csv_points import CSVPoints
from kml_from_csv_points import KMLFromCSVPoints

# --- using this DispersionData type from types.ini ---
#[DispersionData]
#grid_filetype = str
#grid_filename = filename
#parameter = str
#start_time = BSDateTime
#hours = int


class TEST_FEED_KML_ANIMATION(Process):
    """ Generates inputs for testing KML_ANIMATION"""

    def init(self):
        self.declare_output("grid_data", "DispersionData")

    def run(self, context):
        dispersionData = construct_type("DispersionData")
        dispersionData["grid_filetype"] = "NETCDF"
        filename = self.config("NETCDF_FILENAME")
        if filename is None:
            filename = raw_input("Filename: ")
        dispersionData["grid_filename"] = filename
        dispersionData["parameters"] = dict(pm25="PM2P5")

        self.log.info("Setting up DispersionData for KML_ANIMATION using " + dispersionData["grid_filename"])
        ncfile = NetCDFFile(dispersionData["grid_filename"], "r")
        if ncfile is None:
            self.log.info("Can't load NETCDF file using Scientific.IO.NetCDF.NetCDFFile")
            return
        YYYYDDD = str(ncfile.variables["TFLAG"][1, 0, 0, 0])
        HHMMSS = str(ncfile.variables["TFLAG"][1, 0, 0, 1])
        
        dispersionData["hours"] = numpy.shape(ncfile.variables["TFLAG"])[0]
        
        ncfile.close()

        if len(HHMMSS) == 1:
            HH = HHMMSS
        else:
            HH = HHMMSS[:-4]
        dt = datetime.strptime(YYYYDDD + HH, "%Y%j%H")

        dispersionData["start_time"] = BSDateTime(dt.year, dt.month, dt.day)

        self.set_output("grid_data", dispersionData)

def makeKmlAnimation(self, context, dispersionData):
    kmzFiles = []
    try:
        docKml = context.full_path("doc.kml")
        self.log.debug("Opened docKml %s", docKml)
        kmzFiles = [docKml]

        f = open(docKml, "w")
        f.write("""<?xml version="1.0" encoding="UTF-8"?>
        <kml xmlns="http://earth.google.com/kml/2.2">
            <Document>
                <name>%s</name>
                <open>0</open>
                <ScreenOverlay>
                    <name>Legend</name>
                    <overlayXY x="0" y="-16" xunits="pixel" yunits="pixel"/>
                    <screenXY x="0" y="0" xunits="fraction" yunits="fraction"/>
                    <size x="145" y="245" xunits="pixels" yunits="pixels"/>
                    <color>e0ffffff</color>
                    <Icon><href>http://www.getbluesky.org/images/%s</href></Icon>
                </ScreenOverlay>
        """ % (self.config("OVERLAY_TITLE"), self.config("LEGEND_IMAGE")))

        
        hourDelta = timedelta(hours=1)
        name, ext = os.path.splitext(os.path.basename(dispersionData["grid_filename"]))

        for t in range(dispersionData["hours"]):
            dt = dispersionData["start_time"] + hourDelta * t

            band = t + 1
            self.log.debug("Processing %s%s band %2d: %s...", name, ext, band, dt.strftime("%Y-%m-%d %HZ"))
            #kmlfile = dt.strftime(name + "_%Y%m%d%H.kml")
            kmlfile = name + str(band) + ".kml"
            polyFile = context.full_path(kmlfile)
            self.log.debug("Opened polyFile %s", polyFile)

            if dispersionData["grid_filetype"] == "NETCDF":
                makepolygonsInFile = "NETCDF:" + dispersionData["grid_filename"] + ":" + dispersionData["parameters"]["pm25"]
                cutpointsFilename = self.config("CUTPOINTS_FILENAME")
                xslFilename = self.config("XSL_FILENAME")
            else:
                makepolygonsInFile = dispersionData["grid_filename"]
                cutpointsFilename = ""
                xslFilename = ""

            def my_output_handler(logger, output, is_stderr):
                logger.log(OUTPUT, output)

            retCode = context.execute(
                self.config("MAKEPOLYGONS_BINARY"),
                "-in=" + makepolygonsInFile,
                "-band=" + str(band),
                "-cutpoints=" + str(cutpointsFilename),
                "-format=KML",
                "-kmlStyle=" + xslFilename,
                "-out=" + polyFile,
                output_handler = my_output_handler)

            if retCode != 0:
                self.log.error("Failure while trying to convert %s band %s", dispersionData["grid_filename"], band)
                break

            kmzFiles.append(polyFile)
            f.write("""
            <NetworkLink>
                <name>%s</name>
                <visibility>1</visibility>
                <TimeSpan><begin>%s</begin><end>%s</end></TimeSpan>
                <Link><href>%s</href></Link>
                <Style>
                    <ListStyle>
                        <listItemType>checkHideChildren</listItemType>
                    </ListStyle>
                </Style>
            </NetworkLink>
            """ %
            (dt.strftime("Hour %HZ"), dt.isoformat(), (dt + hourDelta).isoformat(), kmlfile))

        f.write("""
            </Document>
        </kml>
        """)
        f.close()

        date = self.config("DATE", BSDateTime)
        kmz_filename = os.path.join(
            self.config("OUTPUT_DIR"),
            self.config("KMZ_FILE"))
        kmz_filename = date.strftime(kmz_filename)

        self.log.info("Creating KMZ file " + os.path.basename(kmz_filename))
        z = zipfile.ZipFile(kmz_filename, "w", zipfile.ZIP_DEFLATED)
        for kml in kmzFiles:
            if os.path.exists(kml):
                z.write(kml, os.path.basename(kml))
            else:
                self.log.error("Failure while trying to write KMZ file -- KML file does not exist")
                self.log.debug('File "%s" does not exist', kml)
        z.close()

    finally:
        self.log.debug("Created kmz file")


class MakeKML(Process):
    """KML Animation task
    Creates polygonal KML animation (kmz file) from geospatial raster file."""
    _version_ = "1.0.0"

    def init(self):
        self.declare_input("grid_data", "DispersionData")

    def run(self, context):
        dispersionData = self.get_input("grid_data")
        makeKmlAnimation(self, context, dispersionData)


class OutputKML(Process):
    """KML output
    Creates polygonal KML animation (kmz file) from geospatial raster file."""
    _version_ = "1.0.0"

    def init(self):
        self.declare_input("fires", "FireInformation")
        
    def run(self, context):
        fireInfo = self.get_input("fires")
        dispersionData = fireInfo.dispersion
        if dispersionData is None:
            self.log.debug("Skip OutputKML because there is no DispersionData")
        else:
            self.log.info("Creating KML from dispersion data")
            makeKmlAnimation(self, context, dispersionData)


class OutputKMLPoints(Process):
    """Creates KML point file from the fire_locations.csv output."""

    def init(self):
        """All Processes must declare an input node.
        However, this input node is unused in this class."""
        self.declare_input("fires", "FireInformation")
    
    def run(self, context):
        fire_loc_file = self.config("FIRE_LOC_FILE")
        if not os.path.exists(fire_loc_file):
            self.log.info('ERROR: fire_locations.csv not found. It must ' +
                          'exist before OutputKMLPoints can be run.')
            return
        fire_icon = 'http://maps.google.com/mapfiles/kml/shapes/firedept.png'
        csv_points = CSVPoints(fire_loc_file)
        kml = KMLFromCSVPoints(csv_points, icon=fire_icon)
        kml.create_kml()
        kml.write_kml()

