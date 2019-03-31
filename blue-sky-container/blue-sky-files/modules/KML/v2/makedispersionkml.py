#!/usr/bin/python

from datetime import datetime
import ConfigParser
from optparse import OptionParser
import os
import json

import dispersiongrid
import dispersion_file_utils as dfu
import dispersionimages
import smokedispersionkml


def main(options):
    print "Starting Make Dispersion KML."

    # Collect configuration settings
    config = _read_configfile(options.configfile)

    # Determine which mode to run OutputKML in
    if 'dispersion' in config.get('DEFAULT', 'MODES').split():
        # Create dispersion images directory within the specified bsf output directory
        dfu.create_dispersion_images_dir(config)

        # Generate smoke dispersion images
        print "Processing smoke dispersion NetCDF data into plot images..."
        start_datetime, grid_bbox = dispersiongrid.create_dispersion_images(config, verbose=options.verbose)

        # Output dispersion grid bounds
        _output_grid_bbox(grid_bbox, config)

        # Post process smoke dispersion images
        print "Formatting dispersion plot images..."
        dispersionimages.format_dispersion_images(config, verbose=options.verbose)
    else:
        start_datetime = config.get("DEFAULT", "DATE") if config.has_option("DEFAULT", "DATE") else datetime.now()
        grid_bbox = None

    # Generate KMZ
    smokedispersionkml.build_smoke_dispersion_kml(config, start_datetime, grid_bbox, pretty_kml=options.prettykml,
                                                  verbose=options.verbose)

    # If enabled, reproject concentration images to display in a different projection
    if config.getboolean('DispersionImages', 'REPROJECT_IMAGES'):
        dispersionimages.reproject_images(config, grid_bbox)

    print "Make Dispersion finished."


def _read_configfile(configfile):
    if not os.path.isfile(configfile):
        raise TypeError("[CRITICAL] Configuration file '%s' does not exist." % configfile)
    config = ConfigParser.ConfigParser()
    config.read(configfile)
    return config


def _output_grid_bbox(grid_bbox, config):
    grid_info_file = config.get('DispersionGridOutput', "GRID_INFO_JSON")
    if grid_info_file is not None:
        print "Outputting grid bounds to %s." % grid_info_file
        grid_info_dict = {'bbox': grid_bbox}
        grid_info_json = json.dumps(grid_info_dict)
        with open(grid_info_file, 'w') as fout:
            fout.write(grid_info_json)


if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option("-c", "--configfile", default="makedispersionkml.ini", help="Configuration file [default: %default]")
    parser.add_option("-p", "--prettykml", default=False, action="store_true", help="Outputs kml in a human readable format")
    parser.add_option("-v", "--verbose", default=False, action="store_true", help="Increases volume of output.")
    (options, args) = parser.parse_args()
    main(options)  # TODO: Catch exceptions and clean up any outputs created?  Should this be toggleable via command line option?
