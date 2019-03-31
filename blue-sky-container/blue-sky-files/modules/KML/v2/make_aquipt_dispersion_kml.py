#!/usr/bin/python

from datetime import datetime
import ConfigParser
from optparse import OptionParser
import os

import dispersiongrid
import dispersionimages
import smokedispersionkml


def main(options):
    print "Starting Make AQUIPT Dispersion KML."

    # Collect configuration settings
    config = _read_configfile(options.configfile)

    # Determine which mode to run OutputKML in
    if 'dispersion' in config.get('DEFAULT', 'MODES').split():
        # Create dispersion images directory within the specified bsf output directory
        _create_dispersion_images_dir(config)
    
        # Generate smoke dispersion images
        print "Processing smoke dispersion NetCDF data into plot images..."
        grid_bbox = dispersiongrid.create_aquiptpost_images(config, verbose=options.verbose)
    
        # Post process smoke dispersion images
        print "Formatting dispersion plot images..."
        dispersionimages.format_dispersion_images(config, verbose=options.verbose)
    else:
        grid_bbox = None
    
    # Generate KMZ
    smokedispersionkml.build_aquipt_kml(config, grid_bbox, pretty_kml=options.prettykml, verbose=options.verbose)
    
    print "Make AQUIPT Dispersion KML finished."


def _read_configfile(configfile):
    if not os.path.isfile(configfile):
        raise TypeError("[CRITICAL] Configuration file '%s' does not exist." % configfile)
    config = ConfigParser.ConfigParser()
    config.read(configfile)
    return config


def _create_dispersion_images_dir(config):
    # [DispersionGridOutput] configurations
    outdir = config.get('DispersionGridOutput', "OUTPUT_DIR")
    if not os.path.exists(outdir):
        os.makedirs(outdir)


if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option("-c", "--configfile", default="makedispersionkml.ini", help="Configuration file [default: %default]")
    parser.add_option("-p", "--prettykml", default=False, action="store_true", help="Outputs kml in a human readable format")
    parser.add_option("-v", "--verbose", default=False, action="store_true", help="Increases volume of output.")
    (options, args) = parser.parse_args()
    main(options)  # TODO: Catch exceptions and clean up any outputs created?  Should this be toggleable via command line option?
