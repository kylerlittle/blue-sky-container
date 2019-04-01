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
#*****************************************************************************
_bluesky_version_ = "3.5.1"

try:
    from osgeo import ogr, osr
except ImportError:
    import ogr, osr

from kernel.grid import GridFile, InvGeoTransform
import arldata

class ARLGridFile(GridFile):
    
    def __init__(self, filename):
        try:
            self.ds = arldata.ARLFile( filename, fast=True )
        except:
            raise Exception("Unable to decode ARL file %s" % f)
            
        self.metadata = dict()
        self.metadata["filename"] = self.ds.file
        self.metadata["start_dt"] = self.ds.start
        self.metadata["end_dt"] = self.ds.end
        self.metadata["data_source"] = self.ds.mainHeader.data_source    
        self.metadata["tangent_long"] = self.ds.mainHeader.tangent_long     # Projection central longitude
        self.metadata["tangent_lat"] = self.ds.mainHeader.tangent_lat       # Projection central latitude
        self.metadata["cone_angle"] = self.ds.mainHeader.cone_angle         # Standard latitude
        self.metadata["num_x_pnts"] = self.ds.mainHeader.numb_x_pnts        # east-west grid dimensions
        self.metadata["num_y_pnts"] = self.ds.mainHeader.numb_y_pnts        # north-south grid dimensions
        self.metadata["grid_size"] =  self.ds.mainHeader.grid_size          # grid spacing in km
        self.metadata["x_synch_pnt"] = self.ds.mainHeader.x_synch_pnt       # X grid tie point
        self.metadata["y_synch_pnt"] = self.ds.mainHeader.y_synch_pnt       # Y grid tie point
        self.metadata["synch_pnt_lat"] = self.ds.mainHeader.synch_pnt_lat   # latitude of tie point
        self.metadata["synch_pnt_long"] = self.ds.mainHeader.synch_pnt_long # longitude of tie point

        # Get georeference info for the ARL grid

        cone_angle = self.metadata["cone_angle"]
        grid_spacing = self.metadata["grid_size"]*1000.0  # km --> m

        # For historical reasons, 'grid spacing' and 'cone angle' are used
        # to determine which type of projection is being used in an ARL file.
        if grid_spacing <= 0.001:
            self.metadata["projection"] = 'LatLon'
            proj = "+proj=latlong +datum=WGS84 +units=m"
            self.metadata["grid_size"] = self.metadata["tangent_lat"]  # degrees
            grid_spacing = self.metadata["grid_size"]

        elif cone_angle > -90.0 and cone_angle < 90.0:
            self.metadata["projection"] = 'Lambert'
            proj = ("+proj=lcc "
                    "+lat_0=%(tangent_lat)s "
                    "+lon_0=%(tangent_long)s "
                    "+lat_1=%(cone_angle)s "
                    "+x_0=0 +y_0=0 "
                    "+ellips=sphere +a=6371200 +b=6371200 "
                    "+towgs84=0,0,0,0,0,0,0 "
                    "+units=m" % self.metadata) 

        elif cone_angle == 90.0 or cone_angle == -90.0:
            self.metadata["projection"] = 'Polar Stereographic'
            proj = ("+proj=stere "
                    "+lat_0=%(cone_angle)s "
                    "+lat_ts=%(tangent_lat)s "
                    "+lon_0=%(tangent_long)s "
                    "+x_0=0 +y_0=0 "
                    "+ellips=sphere +a=6371200 +b=6371200 "
                    "+towgs84=0,0,0,0,0,0,0 "
                    "+units=m" % self.metadata)

        else:
            # Nota Bene: That we know of, no one is currently using Mercator.
            #            So some assumptions had to be made here.
            self.metadata["projection"] = 'Mercator'  # cone_angle is 0.0 degrees.
            proj = ("+proj=merc "
                    "+lon_0=%(tangent_long)s "
                    "+x_0=0 +y_0=0 "
                    "+ellips=sphere +a=6371200 +b=6371200 "
                    "+towgs84=0,0,0,0,0,0,0 "
                    "+units=m" % self.metadata)
            
        self.spatialref = osr.SpatialReference()
        self.spatialref.ImportFromProj4(proj)
        
        self.varname = None
        self.__currentband = None
        self.__currentgrid = None
        
        # Set up coordinate transforms
        latlon = osr.SpatialReference()
        latlon.SetWellKnownGeogCS("WGS84")
        self.LL2XY = osr.CoordinateTransformation(latlon, self.spatialref)
        self.XY2LL = osr.CoordinateTransformation(self.spatialref, latlon)
        
        # Use tie point to compute the projection coordinate of the SW corner of the grid
        synch_long = self.metadata["synch_pnt_long"]
        synch_lat = self.metadata["synch_pnt_lat"]
        synch_coord_x, synch_coord_y = self.getCoordsByLatLon(synch_lat, synch_long)
        xorig = synch_coord_x - (( self.metadata["x_synch_pnt"] - 1 ) * grid_spacing )
        yorig = synch_coord_y - (( self.metadata["y_synch_pnt"] - 1 ) * grid_spacing )
        xorig -= grid_spacing/2.0
        yorig -= grid_spacing/2.0
        self.metadata["xorig"] = xorig
        self.metadata["yorig"] = yorig
        
        # Set the geotransform for the coordinate system
        self.geotransform = (xorig, grid_spacing, 0.0, yorig, 0.0, grid_spacing)
        self.invtransform = InvGeoTransform(self.geotransform)
        self.minX, self.cellSizeX, self.skewX = self.geotransform[:3]
        self.minY, self.skewY, self.cellSizeY = self.geotransform[3:]
        self.sizeX = self.metadata["num_x_pnts"] 
        self.sizeY = self.metadata["num_y_pnts"]
            
    def getBand(self):
        raise NotImplementedError
    
    def getValueAt(self):
        raise NotImplementedError
    
    def __getitem__(self):
        raise NotImplementedError
        
    def __len__(self):
        """Return the number of time periods in the ARL data file"""
        delta = self.ds.end - self.ds.start
        return (((delta.days * 86400) + delta.seconds) / 3600) / (self.ds.interval.seconds / 3600)
        