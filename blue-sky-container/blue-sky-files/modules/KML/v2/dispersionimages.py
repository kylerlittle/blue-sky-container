
from PIL import Image
# from PIL import ImageColor # TODO: Can this replace SimpleColor?
from copy import deepcopy
import os


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
    section = 'DispersionGridOutput'
    images_dir = config.get(section, "OUTPUT_DIR")

    i = 0
    for image_name in os.listdir(images_dir):
        if legend_name not in image_name:
            i += 1
            if _verbose: print "Applying transparency to plot %i " % (i)
            image_path = images_dir + '/' + image_name
            image = Image.open(image_path)
            image = _apply_transparency(image, deepcopy(background_color), image_opacity_factor)
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
