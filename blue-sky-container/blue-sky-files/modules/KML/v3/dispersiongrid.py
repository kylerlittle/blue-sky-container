
from datetime import datetime, timedelta
import os
from osgeo import gdal
import numpy as np
import re
import subprocess

import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
from memoize import memoizeme

import dispersion_file_utils as dfu
from constants import TimeSeriesTypes, CONFIG_COLOR_LABELS

class BSDispersionGrid:

    GDAL_VERSION_MATCHER = re.compile('GDAL (\d+)\.(\d+)\.\d+, released \d+/\d+/\d+')
    def get_geotransform(self):
        flip_images = False

        try:
            gdal_info = subprocess.check_output(["gdalinfo","--version"])
            matches = self.GDAL_VERSION_MATCHER.match(gdal_info)
            major = int(matches.group(1))
            minor = int(matches.group(2))
            if (major > 1) or (major == 1 and minor >= 9):
                flip_images = True
        except OSError:
            # TODO: rather than just default to flip_images = False, read value from config
            pass

        x0 = float(self.metadata["NC_GLOBAL#XORIG"])
        y0 = float(self.metadata["NC_GLOBAL#YORIG"])
        dx = float(self.metadata["NC_GLOBAL#XCELL"])
        dy = float(self.metadata["NC_GLOBAL#YCELL"])
        #nx = int(self.metadata["NC_GLOBAL#NCOLS"])
        ny = int(self.metadata["NC_GLOBAL#NROWS"])

        if flip_images:
            return (x0, dx, 0.0, y0+float(ny-1)*dy, 0.0, -dy)
        else:
            return (x0, dx, 0.0, y0, 0.0, dy)

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
        self.geotransform = self.get_geotransform()

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
        self.datetimes = self.get_datetimes()

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

    def get_datetimes(self):
        """Get Models3 IO/API date-time"""

        sdate = str(self.metadata['NC_GLOBAL#SDATE'])
        # Note: stime should be multiple of 10000 (i.e. multiple of hours), so that
        # casting to int and dividing by 10000 shouldn't lose any information
        stime = int(self.metadata['NC_GLOBAL#STIME']) / 10000
        tstep = str(self.metadata['NC_GLOBAL#TSTEP'])

        start_datetime = datetime.strptime("%s%s" % (sdate, stime), "%Y%j%H")
        tstep_hrs = float(tstep) / 10000

        return [start_datetime + timedelta(hours = i*tstep_hrs) for i in xrange(self.num_times)]

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
        # NOTE: original code just referenced the first and last elemetns of
        #       the arrays but this is messed up when using the new
        #       geotransform for gdal >= 1.9
        self.lonmin = min(self.xvals)
        self.lonmax = max(self.xvals)
        self.latmin = min(self.yvals)
        self.latmax = max(self.yvals)

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
        # explicitly close plot otherwise pyplot keeps it open until end of
        # program
        plt.close()

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
        # explicitly close plot otherwise pyplot keeps it open until end of
        # program
        plt.close()

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
        # explicitly close plot otherwise pyplot keeps it open until end of
        # program
        plt.close()

def create_dispersion_images(config, verbose=False):
    global _verbose
    _verbose = verbose

    # [DispersionGridInput] configurations
    section = 'DispersionGridInput'
    infile = config.get(section, "FILENAME")
    parameter = config.get(section, "PARAMETER")
    layer = int(config.get(section, "LAYER"))
    grid = BSDispersionGrid(infile, param=parameter)  # dispersion grid instance

    plot = None

    for color_map_section in dfu.parse_color_map_names(config, CONFIG_COLOR_LABELS[TimeSeriesTypes.HOURLY]):
        plot = create_hourly_dispersion_images(config, grid, color_map_section, layer)

    for color_map_section in dfu.parse_color_map_names(config, CONFIG_COLOR_LABELS[TimeSeriesTypes.THREE_HOUR]):
        plot = create_three_hour_dispersion_images(config, grid, color_map_section, layer)

    for color_map_section in dfu.parse_color_map_names(config, CONFIG_COLOR_LABELS[TimeSeriesTypes.DAILY_MAXIMUM]):
        plot = create_daily_maximum_dispersion_images(config, grid, color_map_section, layer)

    for color_map_section in dfu.parse_color_map_names(config, CONFIG_COLOR_LABELS[TimeSeriesTypes.DAILY_AVERAGE]):
        plot = create_daily_average_dispersion_images(config, grid, color_map_section, layer)

    if not plot:
        raise Exception("Configuration ERROR... No color maps defined.")

    # Return the grid starting date, and a tuple lon/lat bounding box of the plot
    return grid.datetimes[0], (plot.lonmin, plot.latmin, plot.lonmax, plot.latmax)

@memoizeme
def create_color_plot(config, grid, section, parameter=None):
    # Create plots
    # Note that grid.data has dimensions of: [time,lay,row,col]

      # Create a dispersion plot instance
    plot = BSDispersionPlot(dpi=150)

    # Data levels for binning and contouring
    if parameter and ('PERCENT' in parameter or 'PCNTSIMS' in parameter):
        levels = [float(s.strip()) for s in config.get(section, "PERCENT_LEVELS").split()]
    else:
        levels = [float(s.strip()) for s in config.get(section, "DATA_LEVELS").split()]

    # Colormap
    if config.getboolean(section, "DEFINE_RGB"):
        r = [int(s.strip()) for s in config.get(section, "RED").split()]
        g = [int(s.strip()) for s in config.get(section, "GREEN").split()]
        b = [int(s.strip()) for s in config.get(section, "BLUE").split()]
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

    return plot

def create_hourly_dispersion_images(config, grid, section, layer):
    plot = create_color_plot(config, grid, section)

    outdir = dfu.create_image_set_dir(config, dfu.TimeSeriesTypes.HOURLY, section)

    for i in xrange(grid.num_times):
        # Shift filename date stamps
        fileroot = dfu.image_pathname(config, dfu.TimeSeriesTypes.HOURLY, section, grid.datetimes[i]-timedelta(hours=1))

        if _verbose: print "Creating hourly (%s) concentration plot %d of %d " % (section, i+1, grid.num_times)

        # Create a filled contour plot
        plot.make_contour_plot(grid.data[i,layer,:,:], fileroot)

    # Create a color bar to use in overlays
    fileroot = dfu.legend_pathname(config, dfu.TimeSeriesTypes.HOURLY, section)
    plot.make_colorbar(fileroot)

    # plot will be used for its already computed min/max lat/lon
    return plot

def create_three_hour_dispersion_images(config, grid, section, layer):

    # TODO: switch to iterating over time first and then over color scheme, to
    # avoid redundant average computations

    # TODO: write tests for this function

    plot = create_color_plot(config, grid, section)

    outdir = dfu.create_image_set_dir(config, dfu.TimeSeriesTypes.THREE_HOUR, section)

    for i in xrange(1, grid.num_times - 1):
        # Shift filename date stamps; shift an extra hour because we are on third
        # hour of three hour series and we want timestamp to reflect middle hour
        fileroot = dfu.image_pathname(config, dfu.TimeSeriesTypes.THREE_HOUR, section, grid.datetimes[i]-timedelta(hours=1))

        if _verbose: print "Creating three hour (%s) concentration plot %d of %d " % (section, i+1, grid.num_times)

        # Create a filled contour plot
        plot.make_contour_plot(np.average(grid.data[i-1:i+2,layer,:,:], 0), fileroot)


    # Create a color bar to use in overlays
    fileroot = dfu.legend_pathname(config, dfu.TimeSeriesTypes.THREE_HOUR, section)
    plot.make_colorbar(fileroot)

    # plot will be used for its already computed min/max lat/lon
    return plot

def create_daily_maximum_dispersion_images(config, grid, section, layer):
    plot = create_color_plot(config, grid, section)
    max_outdir = dfu.create_image_set_dir(config, dfu.TimeSeriesTypes.DAILY_MAXIMUM, section)

    hours_offset = 0
    grid.calc_aggregate_data(offset=hours_offset)
    for i in xrange(grid.num_days):
        if _verbose: print "Creating daily maximum concentration plot %d of %d " % (i + 1, grid.num_days)
        fileroot = dfu.image_pathname(config, dfu.TimeSeriesTypes.DAILY_MAXIMUM, section, grid.datetimes[i*24])
        plot.make_contour_plot(grid.max_data[i,layer,:,:], fileroot)

    plot.make_colorbar(dfu.legend_pathname(config, dfu.TimeSeriesTypes.DAILY_MAXIMUM, section))
    return plot

def create_daily_average_dispersion_images(config, grid, section, layer):
    plot = create_color_plot(config, grid, section)
    avg_outdir = dfu.create_image_set_dir(config, dfu.TimeSeriesTypes.DAILY_AVERAGE, section)

    hours_offset = 0
    grid.calc_aggregate_data(offset=hours_offset)
    for i in xrange(grid.num_days):
        if _verbose: print "Creating daily average concentration plot %d of %d " % (i + 1, grid.num_days)
        fileroot = dfu.image_pathname(config, dfu.TimeSeriesTypes.DAILY_AVERAGE, section, grid.datetimes[i*24])
        plot.make_contour_plot(grid.avg_data[i,layer,:,:], fileroot)

    # Create a color bars to use in overlays
    plot.make_colorbar(dfu.legend_pathname(config, dfu.TimeSeriesTypes.DAILY_AVERAGE, section))

    # plot will be used for its already computed min/max lat/lon
    return plot

def create_aquiptpost_images(config, verbose=False):
    global _verbose
    _verbose = verbose

    # [DispersionGridInput] configurations
    section = 'DispersionGridInput'
    infile = config.get(section, "FILENAME")
    parameters = config.get(section, "PARAMETER").split()
    layer = int(config.get(section, "LAYER"))

    # [DispersionGridOutput] configurations

    plot = None
    for section in dfu.parse_color_map_names(config, "AQUIPT_COLORS"):
        outdir = dfu.create_image_set_dir(config, dfu.TimeSeriesTypes.AQUIPT, section)
        for parameter in parameters:
            grid = BSDispersionGrid(infile, param=parameter)  # dispersion grid instance
            plot = create_color_plot(config, grid, section, parameter=parameter)

            if _verbose: print "Creating aggregate plot for %s " % (parameter)
            for i in xrange(grid.num_times):
                fileroot = os.path.join(outdir, parameter)
                plot.make_contour_plot(grid.data[i,layer,:,:], fileroot)

            # Create a color bar to use in overlays
            fileroot = os.path.join(outdir, 'colorbar_'+parameter)

            units = '%' if (parameter and ('PERCENT' in parameter or 'PCNTSIMS' in parameter)) else 'PM25'
            plot.make_colorbar(fileroot, label=units)


    if not plot:
        raise Exception("Configuration ERROR... No color maps defined.")

    # Return a tuple lon/lat bounding box of the plot
    return (plot.lonmin, plot.latmin, plot.lonmax, plot.latmax)
