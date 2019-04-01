
from datetime import datetime, timedelta
import os
import gdal
import numpy as np

import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt


class BSDispersionGrid:

    def __init__(self, filename, param=None, time=None):
        if param:
            gdal_filename = "NETCDF:%s:%s" % (filename, param)    
        else:
            raise ValueError ("No NetCDF parameter supplied.")
        self.ds = gdal.Open(gdal_filename)
        self.metadata = self.ds.GetMetadata()

        if not self.is_ioapi():
            raise Exception("[ERROR] Not dealing with a BlueSky Models3-style netCDF dispersion file.")

        # Get georeference info
        self.geotransform = (
                float(self.metadata["NC_GLOBAL#XORIG"]),
                float(self.metadata["NC_GLOBAL#XCELL"]),
                0.0,
                float(self.metadata["NC_GLOBAL#YORIG"]),
                0.0,
                float(self.metadata["NC_GLOBAL#YCELL"]))

        if not self.metadata["NC_GLOBAL#GDTYP"] == '1':  # lat/lon grid
            raise ValueError("Unrecognized grid type for BlueSky Dispersion netCDF data")

        # Extract grid information
        self.minX, self.cellSizeX, self.skewX = self.geotransform[:3]
        self.minY, self.skewY, self.cellSizeY = self.geotransform[3:]
        self.sizeX = self.ds.RasterXSize
        self.sizeY = self.ds.RasterYSize
        self.sizeZ = int(self.metadata["NC_GLOBAL#NLAYS"])

        # BlueSky dispersion outputs are dimensioned by [TSTEP, LAY, ROW, COL].
        # The number of GDAL raster bands (ds.RasterCount) will be TSTEP*LAY.
        self.num_times = self.ds.RasterCount / self.sizeZ

        # Extract date-time information
        self.datetimes = self.get_datetimes(filename)

        # Extract the data
        timeid = 0
        layerid = 0
        self.data = np.zeros((self.num_times, self.sizeZ, self.sizeY, self.sizeX), dtype=np.float)
        for i in xrange(self.ds.RasterCount):
            rb = self.ds.GetRasterBand(i+1)
            data = rb.ReadAsArray(0, 0, self.sizeX, self.sizeY)
            self.data[timeid,layerid,:,:] = rb.ReadAsArray(0, 0, self.sizeX, self.sizeY)

            # GDAL bands will increment by layer the fastest, then by time
            layerid += 1
            if layerid == self.sizeZ:
                timeid += 1
                layerid = 0

    def is_ioapi(self):
        if "NC_GLOBAL#IOAPI_VERSION" in self.metadata:
            return True
        else:
            return False

    def get_datetimes(self, filename):
        """Get Models3 IO/API date-time"""

        gdal_filename = "NETCDF:%s:%s" % (filename, 'TFLAG')    
        time_ds = gdal.Open(gdal_filename)

        assert self.num_times == time_ds.RasterCount

        dt = np.zeros((self.num_times, 2), dtype=np.int)
        dt_objects = list()
        for i in xrange(self.num_times):
            band = time_ds.GetRasterBand(i+1)
            dt[i,:] = band.ReadAsArray()[0]
            dt_objects.append(self.ioapi_datetime_to_object(dt[i,0], dt[i,1]))

        time_ds = None

        return dt_objects

    def ioapi_datetime_to_object(self, yyyyddd, hhmmss):
        """Convert a Models3 IO/API convention datetime to a python datetime object."""

        hour = hhmmss
        secs = hour % 100
        hour = hour / 100
        mins = hour % 100
        hour = hour / 100

        dt = datetime.strptime(str(yyyyddd), "%Y%j")
        dt = dt.replace(hour=hour, minute=mins, second=secs)

        return dt

    def num_days_spanned(self, hours_offset):
        """Calculate the number of full and partial days spanned by DispersionGrid dataset"""

        ntimes = self.num_times - hours_offset
        return ntimes / 24 + ((ntimes % 24) != 0)

    def calc_aggregate_data(self, offset=0):
        """Calculate various daily aggregates"""

        # Assumes hourly time interval.

        assert offset >= 0, "[ERROR] hour offset for aggregate calculations must be >= 0."

        self.num_days = self.num_days_spanned(offset)
        self.max_data = np.zeros((self.num_days, self.sizeZ, self.sizeY, self.sizeX), dtype=np.float)
        self.avg_data = np.zeros((self.num_days, self.sizeZ, self.sizeY, self.sizeX), dtype=np.float)

        shour = 0 + offset
        ehour = shour + 24  # Python slice indices point *between* elements.

        for day in xrange(self.num_days):
            for layer in xrange(self.sizeZ):
                self.max_data[day,layer,:,:] = np.max(self.data[shour:ehour,layer,:,:], axis=0)
                self.avg_data[day,layer,:,:] = np.average(self.data[shour:ehour,layer,:,:], axis=0)
            shour += 24
            ehour += 24
            if ehour > self.data.shape[0]: ehour = self.data.shape[0]


class BSDispersionPlot:

    def __init__(self, dpi=75):

        self.dpi = dpi
        self.export_format = 'png'

    def colormap_from_RGB(self, r, g, b):
        """ Create a colormap from lists of non-normalized RGB values (0-255)"""

        # Validate the RGB vectors
        assert len(r) == len(g) == len(b), "[ColorMap] RGB vectors must be the same size."
        assert max(r) <= 255 and min(r) >= 0, "ColorMap.RED vector element outside the range [0,255]"
        assert max(g) <= 255 and min(g) >= 0, "ColorMap.GREEN vector element outside the range [0,255]"
        assert max(b) <= 255 and min(b) >= 0, "ColorMap.BLUE vector element outside the range [0,255]"

        # matplotlib likes normalized [0,1] RGB values
        r = np.array(r)/255.
        g = np.array(g)/255.
        b = np.array(b)/255.

        # Create colormap
        self.colormap = mpl.colors.ListedColormap(zip(r, g, b))

        # Set out-of-range values get the lowest and highest colors in the colortable
        self.colormap.set_under( color=(r[0],g[0],b[0]) )
        self.colormap.set_over( color=(r[-1],g[-1],b[-1]) )

        # Create special colormap without the first color for colorbars
        self.cb_colormap = mpl.colors.ListedColormap(zip(r[1:],g[1:],b[1:]))

    def colormap_from_hex(self, hex_colors):
        """Create colormap from list of hex colors."""

        # Convert colors from hex to matplotlib-style normalized [0,1] values
        colors = list()
        for c in hex_colors:
            colors.append(mpl.colors.hex2color(c))

        # Create colormap 
        self.colormap = mpl.colors.ListedColormap(colors)

        # Set out-of-range values get the lowest and highest colors in the colortable
        self.colormap.set_under( color=mpl.colors.hex2color(hex_colors[0]) )
        self.colormap.set_over( color=mpl.colors.hex2color(hex_colors[-1]) )

        # Create special colormap without the first color for colorbars
        self.cb_colormap = mpl.colors.ListedColormap(colors[1:])

    def set_plot_bounds(self, grid):
        """Set X-axis and Y-axis coordinate values for the plot.
           Takes a BSDispersionGrid class as an input."""

        # TODO: Add bounds cropping capability.

        # X-axis and Y-axis values (longitudes and latitudes)
        self.xvals = np.linspace(grid.minX, grid.minX + ((grid.sizeX-1) * grid.cellSizeX), num=grid.sizeX)
        self.yvals = np.linspace(grid.minY, grid.minY + ((grid.sizeY-1) * grid.cellSizeY), num=grid.sizeY)

        # Set the plot extents for the KML
        self.lonmin = self.xvals[0]
        self.lonmax = self.xvals[-1]
        self.latmin = self.yvals[0]
        self.latmax = self.yvals[-1]

    def generate_colormap_index(self, levels):
        """Generate a colormap index based on discrete intervals"""

        self.levels = levels
        assert hasattr(self, "colormap"), "BSDispersionPlot object must have a colormap before you can generate a colormap index."
        self.norm = mpl.colors.BoundaryNorm(self.levels,
                                            ncolors=self.colormap.N)

        # for colorbar
        self.cb_levels = self.levels[1:]
        self.cb_norm = mpl.colors.BoundaryNorm(self.cb_levels,
                                               ncolors=self.cb_colormap.N)

    def make_quadmesh_plot(self, raster_data, fileroot):
        """Create a quadilateral mesh plot."""

        fig = plt.figure()
        #fig.set_size_inches(7,5)
        ax = plt.Axes(fig, [0., 0., 1., 1.], )
        ax.set_axis_off()
        fig.add_axes(ax)
        plt.pcolormesh(self.xvals,
                       self.yvals,
                       raster_data,
                       cmap=self.colormap,
                       norm=self.norm)
        plt.savefig(fileroot+'.'+self.export_format, bbox_inches='tight', pad_inches=0., dpi=self.dpi, transparent=True)

    def make_contour_plot(self, raster_data, fileroot, filled=True, lines=False):
        """Create a contour plot."""

        """ TODO: contour() and contourf() assume the data are defined on grid edges.
        i.e. They line up the bottom-left corner of each square with the coordinates given.
        If the data are defined at grid centers, a half-grid displacement is necessary.
        xv = plot.xvals[:-1] + grid.cellSizeX / 2.
        yv = plot.yvals[:-1] + grid.cellSizeY / 2.
        """

        fig = plt.figure()
        ax = plt.Axes(fig, [0., 0., 1., 1.], )
        ax.set_axis_off()
        fig.add_axes(ax)
        cnf = plt.contourf(self.xvals, 
                           self.yvals, 
                           raster_data, 
                           levels=self.levels,
                           cmap=self.colormap,
                           norm=self.norm,
                           extend='max')
        if lines:
            cn = plt.contour(self.xvals,
                             self.yvals,
                             raster_data,
                             levels=self.levels,
                             colors='black',
                             norm=self.norm)
            
        plt.savefig(fileroot+'.'+self.export_format, dpi=self.dpi, transparent=True)

    def make_colorbar(self, fileroot, label='PM25'):
        if label == 'PM25':
            cb_label = r'$PM_{2.5} \/[\mu g/m^{3}]$'
        else:
            cb_label = label
        mpl.rc('mathtext', default='regular')
        assert len(self.levels) == self.colormap.N + 1
        fig = plt.figure(figsize=(8,1))
        ax = fig.add_axes([0.05, 0.5, 0.9, 0.45])
        ax.tick_params(labelsize=12)
        cb = mpl.colorbar.ColorbarBase(ax, cmap=self.cb_colormap,
                                           norm=self.cb_norm,
                                           ticks=self.cb_levels[0:-1],
                                           orientation='horizontal')
        cb.set_label(cb_label, size=12)
        plt.savefig(fileroot+'.'+self.export_format, dpi=self.dpi/3)


def create_dispersion_images(config, verbose=False):
    global _verbose
    _verbose = verbose

    # [DispersionGridInput] configurations
    section = 'DispersionGridInput'
    infile = config.get(section, "FILENAME")
    parameter = config.get(section, "PARAMETER")
    grid = BSDispersionGrid(infile, param=parameter)  # dispersion grid instance

    # [DispersionGridOutput] configurations
    section = 'DispersionGridOutput'
    outdir = config.get(section, "OUTPUT_DIR")

    # [DispersionGridColorMap] definitions
    section = 'DispersionGridColorMap'
    plot = BSDispersionPlot(dpi=150)  # Create a dispersion plot instance

    # Data levels for binning and contouring
    levels = [float(s) for s in config.get(section, "DATA_LEVELS").split()]

    # Colormap
    if config.getboolean(section, "DEFINE_RGB"):
        r = [int(s) for s in config.get(section, "RED").split()]
        g = [int(s) for s in config.get(section, "GREEN").split()]
        b = [int(s) for s in config.get(section, "BLUE").split()]
        plot.colormap_from_RGB(r, g, b)

    elif config.getboolean(section, "DEFINE_HEX"):
        hex_colors = config.get(section, "HEX_COLORS").split()
        plot.colormap_from_hex(hex_colors)

    else:
        raise Exception("Configuration ERROR... ColorMap.DEFINE_RGB or ColorMap.HEX_COLORS must be true.")

    # Generate a colormap index based on discrete intervals
    plot.generate_colormap_index(levels)

    # X-axis and Y-axis values (longitudes and latitudes)
    plot.set_plot_bounds(grid)

    # Create plots
    # Note that grid.data has dimensions of: [time,lay,row,col]

    layer = 0  # first layer only
    for i in xrange(grid.num_times):
        # Shift filename date stamps
        fileroot = (grid.datetimes[i]-timedelta(hours=1)).strftime("hourly_%Y%m%d%H%M")
        fileroot = os.path.join(outdir, fileroot)

        if _verbose: print "Creating hourly concentration plot %d of %d " % (i+1, grid.num_times)

        # Create a filled contour plot
        plot.make_contour_plot(grid.data[i,layer,:,:], fileroot)

    # Create aggregate plots
    # Note that grid.xxx_data has dimensions of: [numdays,layers,row,columns]
    hours_offset = 0
    grid.calc_aggregate_data(offset=hours_offset)
    count = 0
    for i in xrange(grid.num_days): 
        count += 1
        if _verbose: print "Creating daily aggregate concentration plot %d of %d " % (count, grid.num_days*2)
        fileroot = grid.datetimes[i*24].strftime("daily_maximum_%Y%m%d")
        fileroot = os.path.join(outdir, fileroot)
        plot.make_contour_plot(grid.max_data[i,layer,:,:], fileroot)

        count += 1
        if _verbose: print "Creating daily aggregate concentration plot %d of %d " % (count, grid.num_days*2)
        fileroot = grid.datetimes[i*24].strftime("daily_average_%Y%m%d")
        fileroot = os.path.join(outdir, fileroot)
        plot.make_contour_plot(grid.avg_data[i,layer,:,:], fileroot) 

    # Create a color bar to use in overlays
    fileroot = os.path.join(outdir, 'colorbar')
    plot.make_colorbar(fileroot)

    # Return the grid starting date, and a tuple lon/lat bounding box of the plot
    return grid.datetimes[0], (plot.lonmin, plot.latmin, plot.lonmax, plot.latmax)

def create_aquiptpost_images(config, verbose=False):
    global _verbose
    _verbose = verbose

    # [DispersionGridInput] configurations
    section = 'DispersionGridInput'
    infile = config.get(section, "FILENAME")
    parameters = config.get(section, "PARAMETER").split()
    
    # [DispersionGridOutput] configurations
    section = 'DispersionGridOutput'
    outdir = config.get(section, "OUTPUT_DIR")
        
    for parameter in parameters:
      
        grid = BSDispersionGrid(infile, param=parameter)  # dispersion grid instance
        
        section = 'DispersionGridColorMap'
        plot = BSDispersionPlot(dpi=150)  # Create a dispersion plot instance
        
        # Data levels for binning and contouring
        data_levels = [float(s) for s in config.get(section, "DATA_LEVELS").split()]
        pcnt_levels = [float(s) for s in config.get(section, "PERCENT_LEVELS").split()]
        if 'PERCENT' in parameter:
            levels = pcnt_levels
            units = '%'
        elif 'PCNTSIMS' in parameter:
            levels = pcnt_levels
            units = '%'
        else:
            levels = data_levels
            units = 'PM25'
        
        # Colormap
        if config.getboolean(section, "DEFINE_RGB"):
            r = [int(s) for s in config.get(section, "RED").split()]
            g = [int(s) for s in config.get(section, "GREEN").split()]
            b = [int(s) for s in config.get(section, "BLUE").split()]
            plot.colormap_from_RGB(r, g, b)
        
        elif config.getboolean(section, "DEFINE_HEX"):
            hex_colors = config.get(section, "HEX_COLORS").split()
            plot.colormap_from_hex(hex_colors)
        
        else:
            raise Exception("Configuration ERROR... ColorMap.DEFINE_RGB or ColorMap.HEX_COLORS must be true.")
        
        # Generate a colormap index based on discrete intervals
        plot.generate_colormap_index(levels)
        
        # X-axis and Y-axis values (longitudes and latitudes)
        plot.set_plot_bounds(grid)
        
        # Create plots
        # Note that grid.data has dimensions of: [time,lay,row,col]
        
        layer = 0  # first layer only
        if _verbose: print "Creating aggregate plot for %s " % (parameter)
        for i in xrange(grid.num_times):
            fileroot = parameter
            fileroot = os.path.join(outdir, fileroot)
            plot.make_contour_plot(grid.data[i,layer,:,:], fileroot)
        
        # Create a color bar to use in overlays
        fileroot = os.path.join(outdir, 'colorbar_'+parameter)
        plot.make_colorbar(fileroot, label=units)
        
    # Return a tuple lon/lat bounding box of the plot
    return (plot.lonmin, plot.latmin, plot.lonmax, plot.latmax)