# TODO: refactor this as a class (possibly singleton?) that takes config in contstructor

import os

from constants import *
from memoize import memoizeme

__all__ = [
    'create_dispersion_images_dir', 'image_dir', 'create_image_set_dir',
    'image_pathname', 'parse_color_map_names', 'collect_all_dispersion_images',
    'collect_dispersion_images', 'collect_aquipt_images'
    ]

def create_dir_if_does_not_exist(outdir):
    if not os.path.exists(outdir):
        os.makedirs(outdir)


def create_dispersion_images_dir(config):
    outdir = config.get('DispersionGridOutput', "OUTPUT_DIR")
    create_dir_if_does_not_exist(outdir)

def create_polygon_kmls_dir(config):
    outdir = config.get('PolygonsKML', "POLYGONS_OUTPUT_DIR")
    create_dir_if_does_not_exist(outdir)

# Note: this will memoize for a single instance of the config parse
# TODO: pass in images_output_dir instead of the config object ?
@memoizeme
def image_dir(config, time_series_type, color_map_type):
    """Returns the directory containing the specified image set"""
    images_output_dir = config.get('DispersionGridOutput', "OUTPUT_DIR")
    return os.path.join(images_output_dir, TIME_SET_DIR_NAMES[time_series_type], color_map_type)

def create_image_set_dir(config, time_series_type, color_map_type):
    """Creates the directory to contain the specified image set, if necessary"""
    outdir = image_dir(config, time_series_type, color_map_type)
    if not os.path.exists(outdir):
        os.makedirs(outdir)
    return outdir

def image_pathname(config, time_series_type, color_map_type, ts):
    filename = ts.strftime(IMAGE_PREFIXES[time_series_type] + FILE_NAME_TIME_STAMP_PATTERNS[time_series_type])
    outdir = image_dir(config, time_series_type, color_map_type)
    return os.path.join(outdir, filename)

def legend_pathname(config, time_series_type, color_map_type):
    filename = "colorbar_%s" % (TIME_SET_DIR_NAMES[time_series_type])
    outdir = image_dir(config, time_series_type, color_map_type)
    return os.path.join(outdir, filename)


# TODO: parse_color_map_names belongs somewhere else...or maybe this module,
# dispersion_file_utils, should be renamed more generically
# Note: this will memoize for a single instance of the config parse
# TODO: pass in color map names string instead of the config object ?
@memoizeme
def parse_color_map_names(config, set_name):
    if config.has_option("DispersionGridOutput", set_name):
        return [name.strip() for name in config.get("DispersionGridOutput", set_name).split(',')]
    return []

def is_smoke_image(file_name, time_series_type):
    if time_series_type == TimeSeriesTypes.AQUIPT:
        return len([p for p in AQUIPT_IMAGE_PREFIXES.values() if file_name.startswith(p)]) > 0
    else:
        return file_name.startswith(IMAGE_PREFIXES[time_series_type])


@memoizeme
def collect_all_dispersion_images(config):
    """Collect images from all sets of colormap images in each time series category"""
    images = dict((v, {}) for v in TimeSeriesTypes.ALL_PLUS_AQUIPT)

    for time_series_type in TimeSeriesTypes.ALL_PLUS_AQUIPT:
        for color_map_section in parse_color_map_names(config, CONFIG_COLOR_LABELS[time_series_type]):
            color_set = {
                'root_dir': create_image_set_dir(config, time_series_type, color_map_section),
                'smoke_images': [],
                'legend': None
            }
            for image in os.listdir(color_set['root_dir']):
                if is_smoke_image(image, time_series_type):  # <-- this is to exclude color bar
                    color_set['smoke_images'].append(image)
                else:  #  There should only be smoke images and a legend
                    color_set['legend'] = image

            images[time_series_type][color_map_section] = color_set

    return images


# Note: collect_dispersion_images was copied over from smokedispersionkml.py and
# refactored to remove redundancy
def collect_dispersion_images(config):
    """Collect images from first set of colormap images in each time series category"""
    images = dict((v, {'smoke_images':[], 'legend': None}) for v in TimeSeriesTypes.ALL)

    for time_series_type in TimeSeriesTypes.ALL:
        color_map_sections = parse_color_map_names(config, CONFIG_COLOR_LABELS[time_series_type])
        if color_map_sections and len(color_map_sections) > 0:
            outdir = create_image_set_dir(config, time_series_type, color_map_sections[0])
            images[time_series_type]['root_dir'] = outdir
            for image in os.listdir(outdir):
                if image.startswith(IMAGE_PREFIXES[time_series_type]):  # <-- this is to exclude color bar
                    images[time_series_type]['smoke_images'].append(image)
                else:  #  There should only be smoke images and a legend
                    images[time_series_type]['legend'] = image

    return images


# Note: collect_aquipt_images was copied over from smokedispersionkml.py and
# refactored to remove redundancy
def collect_aquipt_images(config):
    images = dict((t, {'images': [], 'legends': []}) for t in AquiptImageTypes.ALL)

    color_map_sections = parse_color_map_names(config, CONFIG_COLOR_LABELS[TimeSeriesTypes.AQUIPT])
    if color_map_sections and len(color_map_sections) > 0:
        outdir = create_image_set_dir(config, TimeSeriesTypes.AQUIPT, color_map_sections[0])
        images['root_dir'] = outdir
        for image in os.listdir(outdir):
            matching_types = [i[0] for i in AQUIPT_IMAGE_PREFIXES.items() if image.startswith(i[1])]
            image_type = matching_types[0] if len(matching_types) > 0 else None

            if image_type is not None:
                images[image_type]['images'].append(image)
                legend = "colorbar_%s.png" % image.split('.')[0]
                images[image_types]['legends'].append(legend)

    return images
