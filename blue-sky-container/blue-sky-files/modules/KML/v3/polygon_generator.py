import os
import subprocess
from datetime import timedelta

import dispersion_file_utils as dfu
from dispersiongrid import BSDispersionGrid, BSDispersionPlot, create_color_plot

class PolygonGenerator(object):
    """Generates polygon kmls from a NETCDF file representing smoke dispersion
    time series.

    Public Instance Attributes:
      output_dir - output directory containing generated polygon kmls,
                    legend, xsl file, and cutpoints file
      legend_filename - legend's file name
      kml_files - list of tuples of the form (<kml file name>, <prediction
                    timestamp>)
    """

    # HACK: It would be more elegant to generate xml using an XML package, like minidom.
    # We're using raw strings for speed of implementation.

    XSL_FIRST_PART = r"""<?xml version="1.0"?>

<!-- This is an xsl stylesheet to add styles to an OGR generated KML file -->
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:kml="http://www.opengis.net/kml/2.2" version="1.0">
    <xsl:output method="xml" indent="yes" omit-xml-declaration="no" encoding="utf-8"/>

    <!-- In general, just pass through all elements and attributes -->
    <xsl:template match="*">
        <xsl:copy>
            <xsl:copy-of select="@*" />
            <xsl:apply-templates />
        </xsl:copy>
    </xsl:template>

    <!-- We want to eliminate any embedded style because we don't want to hide the external styles -->
    <xsl:template match="kml:Style" />

  <!-- Eliminate Schema and ExtendedData -->
    <xsl:template match="kml:Schema" />
    <xsl:template match="kml:ExtendedData" />

    <xsl:template match="kml:Document">
        <xsl:copy>
            <xsl:copy-of select="@*" />
    """

    XSL_STYLE_ELEMENT = """<Style id=\"%s\">
                <PolyStyle>
                    <color>%s</color>
                    <fill>%s</fill>
                    <outline>0</outline>
                </PolyStyle>
            </Style>
    """

    XSL_LAST_PART = r"""<xsl:apply-templates />
        </xsl:copy>
    </xsl:template>

    <xsl:template match="kml:Placemark">
        <xsl:copy>
            <xsl:copy-of select="@*" />
            <styleUrl><xsl:value-of select="./kml:ExtendedData/kml:SchemaData/kml:SimpleData[@name='Category']" /></styleUrl>
            <xsl:apply-templates />
        </xsl:copy>
    </xsl:template>

</xsl:stylesheet>
    """

    POLYGONS_CONFIG_SECTION = 'PolygonsKML'

    # TODO: pass in individual values from confif rather than config itself.
    def __init__(self, config):
        self._config = config

        # TODO: support multiple color schemes
        self._color_bar_section = self._config.get(self.POLYGONS_CONFIG_SECTION, 'POLYGON_COLORS').split(',')[0]

        self._create_output_dir()
        self._import_grid()
        self._generate_custom_cutpoints_file()
        self._generate_custom_xsl_files()
        self._generate_kmls()
        self._generate_legend()

    def _create_output_dir(self):
        self.output_dir = self._config.get(self.POLYGONS_CONFIG_SECTION, 'POLYGONS_OUTPUT_DIR')
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def _import_grid(self):
        netcdf_param = self._config.get('DispersionGridInput', "PARAMETER")
        if not netcdf_param:
            raise ValueError ("No NetCDF parameter supplied.")

        self._infile = self._config.get('DispersionGridInput', "FILENAME")
        self._makepolygons_infile = "NETCDF:%s:%s" % (self._infile, netcdf_param)
        self._grid = BSDispersionGrid(self._infile, param=netcdf_param)  # dispersion grid instance

    def _generate_custom_cutpoints_file(self):
        self._custom_cutpoints_filename = os.path.join(self.output_dir, 'CutpointsGateway.csv')
        newfile = open(self._custom_cutpoints_filename, 'w')
        newfile.write("Name,Threshold\n")

        levels =  [s for s in self._config.get(self._color_bar_section, "DATA_LEVELS").split()]
        for i in xrange(len(levels)):
            newfile.write("Cat%d,%s\n" % (i, levels[i]))
        newfile.close()

    def _generate_custom_xsl_files(self):
        self._custom_xsl_filename = os.path.join(self.output_dir, 'KMLPolygonStyleGateway.xsl')
        newfile = open(self._custom_xsl_filename, 'w')
        newfile.write(self.XSL_FIRST_PART)

        hex_colors = self._parse_colors()
        for i in xrange(len(hex_colors)):
            if hex_colors[i] == '000000':
                color_str = '00000000'
                fill_str = '0'
            else:
                color_str = '99%s' % (hex_colors[i])
                fill_str = '1'
            newfile.write(self.XSL_STYLE_ELEMENT % ("Cat%d" % (i), color_str, fill_str))

        newfile.write(self.XSL_LAST_PART)
        newfile.close()

    def _parse_colors(self):
        if self._config.getboolean(self._color_bar_section, "DEFINE_RGB"):
            r = [int(s) for s in self._config.get(self._color_bar_section, "RED").split()]
            g = [int(s) for s in self._config.get(self._color_bar_section, "GREEN").split()]
            b = [int(s) for s in self._config.get(self._color_bar_section, "BLUE").split()]
            if not len(r) == len(g) == len(b):
                raise Exception("Configuration ERROR... RED, GREEN, BLUE must specify same number of values.")
            # kml colors are specified as 'aabbggrr' (where 'aa' is the alpha value)
            return ['%02x%02x%02x' % (b[i], g[i], r[i]) for i in xrange(len(r))]
        elif self._config.getboolean(self._color_bar_section, "DEFINE_HEX"):
            return [s.strip('#') for s in self._config.get(self._color_bar_section, "HEX_COLORS").split()]
        else:
            raise Exception("Configuration ERROR... DEFINE_RGB or HEX_COLORS must be true.")

    def _generate_kmls(self):
        self._kml_file_basename, ext = os.path.splitext(os.path.basename(self._infile))

        dfu.create_polygon_kmls_dir(self._config)
        self.kml_files = []

        # def my_output_handler(logger, output, is_stderr):
        #     logger.log(OUTPUT, output)

        for i in xrange(self._grid.num_times):
            try:
                self._generate_kml(i)
            except:
                break

    def _generate_kml(self, i):
        dt = self._grid.datetimes[i] - timedelta(hours=1)
        band = i + 1

        #self.log.debug("Processing %s band %2d: %s...", name, band, dt.strftime("%Y-%m-%d %HZ"))
        #kmlfile = dt.strftime(name + "_%Y%m%d%H.kml")
        kmlfile = self._kml_file_basename + str(band) + ".kml"
        poly_file = os.path.join(self.output_dir, kmlfile)
        #self.log.debug("Opened poly_file %s", poly_file)

        args = [
            self._config.get(self.POLYGONS_CONFIG_SECTION, "MAKEPOLYGONS_BINARY"),
            "-in=" + self._makepolygons_infile,
            "-band=" + str(band),
            "-cutpoints=" + os.path.abspath(self._custom_cutpoints_filename),
            "-format=KML",
            "-kmlStyle=" + self._custom_xsl_filename,
            "-out=" + poly_file
        ]

        if subprocess.call(' '.join(args), shell=True) != 0:
            msg = "Failure while trying to create %s" % (poly_file)
            #self.log.error(msg)
            raise RuntimeError(msg)

        self.kml_files.append((kmlfile, dt))

    LEGEND_FILENAME_ROOT = 'colorbar_polygons'

    def _generate_legend(self):
        plot = create_color_plot(self._config, self._grid, self._color_bar_section)
        plot.make_colorbar(os.path.join(self.output_dir, self.LEGEND_FILENAME_ROOT))
        self.legend_filename = "%s.%s" % (self.LEGEND_FILENAME_ROOT,
            plot.export_format)

