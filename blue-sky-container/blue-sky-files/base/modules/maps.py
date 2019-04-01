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
import mapscript
try:
    from osgeo import gdal
    from osgeo import ogr
    from osgeo import osr
except ImportError:
    import gdal
    import ogr
    import osr
from datetime import timedelta

from kernel.core import Process
from kernel.config import config, baseDir
from kernel.grid import open_grid, makeCompatibleDataset

def aggregateDispersionData(context, dispersionData, startTime=None):
    aggregationUtil = os.path.join(baseDir, "base", "aggregationUtil")
    aggregationFile = context.full_path("aggregation.nc")
    context.trash_file(aggregationFile)
    if startTime is None:
        startTime = dispersionData["start_time"]
        
    context.link_file(dispersionData["grid_filename"])
    inputFileName = os.path.basename(dispersionData["grid_filename"])
    aggregationFileName = os.path.basename(aggregationFile)
        
    context.execute(aggregationUtil, 
        "-I" + inputFileName,
        "-O" + aggregationFileName,
        "-D1",
        "-T" + startTime.strftime("%H%m"))
    
    return aggregationFile

def getMapObjects(context, dispersionData, aggregate=None, startTime=None):
    shapePath = config.get("OutputMapImages", "SHAPE_PATH")
    mapFile = config.get("OutputMapImages", "MAP_TEMPLATE")
    dataLayer = config.get("OutputMapImages", "DATA_LAYER")
    if config.has_option("OutputMapImages", "USE_DATA_PROJECTION"):
        useDataProjection = config.get("OutputMapImages", "USE_DATA_PROJECTION", asType=bool)
    else:
        useDataProjection = True
    
    grid_filename = dispersionData["grid_filename"]
    nc_variable = dispersionData["parameters"]["pm25"]
    
    if aggregate is not None:
        grid_filename = aggregateDispersionData(context, dispersionData, startTime)
        nc_variable += str(aggregate)
    
    if dispersionData["grid_filetype"] == "NETCDF":
        inputFile = makeCompatibleDataset(context, grid_filename, nc_variable)
    else:
        inputFile = grid_filename
    
    grid = open_grid(inputFile)
    minx, miny, maxx, maxy = grid.getRect()
    proj = grid.getProj4()
    
    mp = mapscript.mapObj(mapFile)
    
    if useDataProjection:
        mp.setProjection(proj)
        mp.extent = mapscript.rectObj(minx, miny, maxx, maxy)
    else:
        latlon = osr.SpatialReference()
        latlon.SetWellKnownGeogCS("WGS84")
        mapCoordSys = osr.SpatialReference()
        mapCoordSys.ImportFromProj4(mp.getProjection())
        xform = osr.CoordinateTransformation(latlon, mapCoordSys)
        # Transform all four corners to make sure we cover at least the full 
        # grid in the projected coordinate system
        corners = [(minx, miny), (minx, maxy), (maxx, miny), (maxx, maxy)]
        coords = [xform.TransformPoint(x, y) for (x, y) in corners]
        xs = [coord[0] for coord in coords]
        ys = [coord[1] for coord in coords]
        minx = min(xs)
        miny = min(ys)
        maxx = max(xs)
        maxy = max(ys)        
        mp.extent = mapscript.rectObj(minx, miny, maxx, maxy)
    mp.shapepath = shapePath
    
    layer = mp.getLayerByName(dataLayer)
    layer.data = inputFile
    layer.setProjection(proj)
    
    return grid, mp, layer
    
def createMapImage(context, dispersionData, hour):
    grid, mp, layer = getMapObjects(context, dispersionData)
    band = hour + 1
    layer.setProcessingKey("BANDS", str(band))
    img = mp.draw()
    return img

def createMapImages(self, context, dispersionData):
    outputDir = self.config("OUTPUT_DIR")
    imageFilePattern = self.config("IMAGE_FILE_PATTERN")

    count = 0
    for t in range(dispersionData["hours"]):
        dt = dispersionData["start_time"] + timedelta(hours=t)
        imgFile = dt.strftime(os.path.join(outputDir, imageFilePattern))
        
        grid, mp, layer = getMapObjects(context, dispersionData)
        
        count += 1
        band = t + 1
        self.log.debug("Rendering band %d to: %s", band, imgFile)
        layer.setProcessingKey("BANDS", str(band))
        img = mp.draw()
        img.save(imgFile)
    
    self.log.info("Wrote %d image files", count)

class OutputMapImages(Process):
    def init(self):
        self.declare_input("fires", "FireInformation")

    def run(self, context):
        fireInfo = self.get_input("fires")
        if fireInfo.dispersion is None:
            self.log.debug("Skip OutputMapImages because there is no DispersionData")
            return
        
        self.log.info("Creating map images from dispersion data")
        createMapImages(self, context, fireInfo.dispersion)