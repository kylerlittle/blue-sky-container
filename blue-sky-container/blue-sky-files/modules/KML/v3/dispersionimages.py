
from PIL import Image
# from PIL import ImageColor # TODO: Can this replace SimpleColor?
from copy import deepcopy
import os

import dispersion_file_utils as dfu
from constants import TIME_SERIES_PRETTY_NAMES

class SimpleColor(object):
    """Represents a pixel color in the form of RGBA."""

    def __init__(self, r=255, g=255, b=255, a=255):
        """
        Keyword arguments:
            r -- Red color level (int between 0 and 255, default 255)
            g -- Green color level (int between 0 and 255, default 255)
            b -- Blue color level (int between 0 and 255, default 255)
            a -- Alpha level (int between 0 and 255, default 255)
        """
        self.set_color(r,g,b,a)

    def set_color(self, r=None, g=None, b=None, a=None):
        """Sets individual color levels.
        Arguments:
            r -- Red color level (int between 0 and 255, default None)
            g -- Green color level (int between 0 and 255, default None)
            b -- Blue color level (int between 0 and 255, default None)
            a -- Alpha level (int between 0 and 255, default None)
        Returns:
            The SimpleColor object instance
        """
        if r is not None:
            self.r = r
        if g is not None:
            self.g = g
        if b is not None:
            self.b = b
        if a is not None:
            self.a = a
        return self

    def get_color_tuple(self):
        """Provides tuple representation of the SimpleColor object.
        Returns:
            tuple(Red, Green, Blue, Alpha)
        """
        return self.r, self.g, self.b, self.a


def format_dispersion_images(config, legend_name="colorbar", verbose=False):
    global _verbose
    _verbose = verbose

    # [DispersionImages] configurations
    section = 'DispersionImages'
    image_opacity_factor = config.getfloat(section, "IMAGE_OPACITY_FACTOR")
    if config.getboolean(section, "DEFINE_RGB"):
        red = config.getint(section, "BACKGROUND_COLOR_RED")
        green = config.getint(section, "BACKGROUND_COLOR_GREEN")
        blue = config.getint(section, "BACKGROUND_COLOR_BLUE")
    elif config.getboolean(section, "DEFINE_HEX"): # Convert hex to RGB integers
        background_color_hex = config.get(section, "BACKGROUND_COLOR_HEX")
        rgb_hex = background_color_hex[1:3], background_color_hex[3:5], background_color_hex[5:7]
        red, green, blue = ((int(hex_val, 16) for hex_val in rgb_hex))
    else:
        raise Exception("Configuration ERROR...DispersionImages.DEFINE_RGB or DispersionImages.DEFINE_HEX must be true.")
    background_color = SimpleColor(red, green, blue, 255)

    # [DispersionGridOutput] configurations
    images = dfu.collect_all_dispersion_images(config)

    for (time_series_type, time_series_dict) in images.items():
        for (color_map_section, color_set_dict) in time_series_dict.items():
            # iof is the color map section's custom image opacity factor, if specified
            iof = (config.getfloat(color_map_section, "IMAGE_OPACITY_FACTOR") if
                config.has_option(color_map_section, "IMAGE_OPACITY_FACTOR") else
                image_opacity_factor)
            i = 0
            for image_name in color_set_dict['smoke_images']:
                i += 1
                if _verbose:
                    print "Applying transparency %s to plot %i of %s %s" % (
                        iof, i, TIME_SERIES_PRETTY_NAMES[time_series_type], color_map_section)
                image_path = os.path.join(color_set_dict['root_dir'], image_name)
                image = Image.open(image_path)
                image = _apply_transparency(image, deepcopy(background_color), iof)
                image.save(image_path, "PNG")

def _apply_transparency(image, background_color, opacity_factor):
    """Sets the background color of the image to be fully transparent, and modifies the overall image opacity based on a
    specified factor.
    Arguments:
        image            -- Image to apply transparency to (PIL.Image object)
        background_color -- Color that will be made transparent (SimpleColor object)
        opacity_factor   -- Determines visibility of image. A value of 0 would make the image fully transparent
                            (float 0.0 to 1.0)
    Returns:
        Modified img object
    """
    background_color_tuple = background_color.get_color_tuple() # Get color tuple to search for
    transparent_color_tuple = background_color.set_color(a=0).get_color_tuple() # Get transparent color tuple
    pixdata = image.load()

    for y in xrange(image.size[1]):
        for x in xrange(image.size[0]):
            if pixdata[x, y] == background_color_tuple:
                pixdata[x, y] = transparent_color_tuple
            else:
                pixel = pixdata[x, y]
                new_alpha = int(pixel[3]*opacity_factor)
                if new_alpha > 255:
                    new_alpha = 255
                elif new_alpha < 0:
                    new_alpha = 0
                pixel_color = SimpleColor(r=pixel[0], g=pixel[1], b=pixel[2], a=new_alpha)
                pixdata[x, y] = pixel_color.get_color_tuple()
    return image

def reproject_images(config, grid_bbox):
    """Reproject images for display on map software (i.e. OpenLayers).
    PNG images will first be translated to TIF files via the 'gdal_translate' command.  The new TIF file will then be
    reprojected using the 'gdalwarp' command.  Finally, the reprojected TIF file will be warped back into PNG image form.

    Currently hardcoded to reproject to  EPSG:3857 - http://spatialreference.org/ref/sr-org/epsg3857/
    """

    # Note: This code utilizes gdal CLI commands.  Idealy it should instead take advantage of the python gdal library.
    # However, there is no official documentation available for the python gdal API, making it rather tricky to
    # use correctly.  The below link points to a unit test suite for python gdal's transformation logic.  Perhaps there
    # are enough examples there to determain how to replace the translation/warp operations used from the command line.
    #
    # http://svn.osgeo.org/gdal/trunk/autotest/gcore/transformer.py
    #
    # Below are links to the command line documentation for gdal's "translate" and "warp" commands.
    #
    # gdal_translate - http://www.gdal.org/gdal_translate.html
    # gdalwarp -      http://www.gdal.org/gdalwarp.html

    images = dfu.collect_all_dispersion_images(config)
    for (time_series_type, time_series_dict) in images.items():
        for (color_map_section, color_set_dict) in time_series_dict.items():
            for image in color_set_dict['smoke_images']:
                image_path = os.path.join(color_set_dict['root_dir'], image)
                tiff_path1 = os.path.join(color_set_dict['root_dir'], 'temp1.tif')
                tiff_path2 = os.path.join(color_set_dict['root_dir'], 'temp2.tif')

                # Collect inputs for gdal translate and warp commands
                a_srs = 'WGS84'
                a_ullr = '%s %s %s %s' % (str(grid_bbox[0]), str(grid_bbox[3]), str(grid_bbox[2]), str(grid_bbox[1]))
                t_srs = '+proj=merc +lon_0=0 +k=1 +x_0=0 +y_0=0 +a=6378137 +b=6378137 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs'

                # Build gdal translate and warp command line strings
                gdal_translate_cmd1 = 'gdal_translate -a_srs %s -a_ullr %s %s %s' % (a_srs, a_ullr, image_path, tiff_path1)
                gdal_warp_cmd = 'gdalwarp -t_srs \'%s\' %s %s' % (t_srs, tiff_path1, tiff_path2)
                gdal_translate_cmd2 = 'gdal_translate -of PNG %s %s' % (tiff_path2, image_path)

                # Gdal translate PNG image to TIF
                print "Executing: %s" % gdal_translate_cmd1
                os.system(gdal_translate_cmd1)

                # Gdal warp TIF to new projection
                print "Executing: %s" % gdal_warp_cmd
                os.system(gdal_warp_cmd)

                # Gdal translate new TIF back to PNG
                print "Executing: %s" % gdal_translate_cmd2
                os.system(gdal_translate_cmd2)

                # Clean up intermediate files
                os.remove(tiff_path1)
                os.remove(tiff_path2)
                os.remove(image_path + '.aux.xml')
