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
from shutil import copyfile
from kernel.config import TemplateConfigParser
from kernel.config import config as kernel_config
from kernel.core import Process
from kernel.log import OUTPUT


class OutputKML(Process):
    """KML output
    Creates KML using overlays of geospatial raster data.
    
    PLEASE NOTE: The config parameters set in this modules INI file are all mandatory.
    """
    _version_ = "1.0.0"

    def init(self):
        self.declare_input("fires", "FireInformation")

    def run(self, context):
        fireInfo = self.get_input("fires")
        dispersionData = fireInfo.dispersion

        self.log.info("Creating KMZ from output data.")
        if dispersionData is None:
            dispersionData = {}
            modes = 'fires'
            self.log.info('OutputKML will only produce fire emissions data.')
        else:
            modes = 'fires dispersion'
            self.log.info('OutputKML will produce dispersion and fire emissions data.')

        # Build Sections of external configuration file

        # Fire Locations section
        sect1 = 'DEFAULT'
        config = TemplateConfigParser()
        config.set(sect1, 'BSF_OUTPUT_DIR', self.config("OUTPUT_DIR"))
        config.set(sect1, 'MODES', modes)

        # Dispersion sections
        sect2 = 'DispersionGridInput'
        config.add_section(sect2)
        config.set(sect2, 'FILENAME', dispersionData.get('grid_filename', ''))
        config.set(sect2, 'PARAMETER', dispersionData.get('parameters', {}).get('pm25', ''))

        sect3 = 'DispersionGridOutput'
        config.add_section(sect3)
        config.set(sect3, 'OUTPUT_DIR', os.path.join(self.config('OUTPUT_DIR'), 'images'))

        sect4 = 'DispersionGridColorMap'
        if self.config('DEFINE_RGB', bool):
            opt1 = ['DEFINE_RGB','RED','GREEN','BLUE','DEFINE_HEX']
        elif self.config('DEFINE_HEX', bool):
            opt1 = ['DEFINE_HEX','HEX_COLORS','DEFINE_RGB']
        else:
            self.log.error('DEFINE_RGB or DEFINE_HEX must be set to true.')
        opt1.append('DATA_LEVELS')
        self._create_config_section(config, sect4, opt1)

        sect5 = 'DispersionImages'
        if self.config('DEFINE_RGB', bool):
            opt2 = ['DEFINE_RGB', 'BACKGROUND_COLOR_RED','BACKGROUND_COLOR_GREEN',
                    'BACKGROUND_COLOR_BLUE', 'DEFINE_HEX']
        elif self.config('DEFINE_HEX', bool):
            opt2 = ['DEFINE_HEX', 'BACKGROUND_COLOR_HEX', 'DEFINE_RGB']
        else:
            self.log.error('DEFINE_RGB or DEFINE_HEX must be set to true.')
        opt2.append('IMAGE_OPACITY_FACTOR')
        self._create_config_section(config, sect5, opt2)

        sect6 = 'SmokeDispersionKMLInput'
        opt3 = ['MET_TYPE','FIRE_LOCATION_CSV','LEGEND_IMAGE',
                'DISCLAIMER_IMAGE','FIRE_EVENT_ICON','FIRE_LOCATION_ICON']
        self._create_config_section(config, sect6, opt3)

        sect7 = 'SmokeDispersionKMLOutput'
        self._create_config_section(config, sect7, ['KMZ_FILE'])
        config.set(sect7, 'FIRE_LOCATION_CSV', os.path.join(self.config('OUTPUT_DIR')))

        # Write out config file needed by the external KMZ-producing executable
        config_file = context.full_path('makedispersionkml.ini')
        with open(config_file, 'w') as configfile:
            config.write(configfile)

        context.archive_file(config_file)

        # execute external kml-generating code
        def my_output_handler(logger, output, is_stderr):
            logger.log(OUTPUT, output)

        context.execute(self.config('MAKEKML_PROGRAM'),
                        output_handler = my_output_handler)

        kmz_final_file = os.path.join(self.config("OUTPUT_DIR"), self.config("KMZ_FILE"))
        kmz_temp_file = context.full_path(self.config('KMZ_FILE'))
        copyfile(kmz_temp_file, kmz_final_file)

    def _create_config_section(self, config, section, options):
        """Create a makedispersionkml INI section by copying over BlueSky INI settings."""

        config.add_section(section)
        for option in options:
            config.set(section, option, self.config(option))

class OutputAquiptKML(Process):
    """KML output for AQUIPT
    Creates KML using overlays of geospatial raster data generated by outputAQUIPT.
    
    PLEASE NOTE: The config parameters set in this modules INI file are all mandatory.
    """
    _version_ = "1.0.0"

    def init(self):
        self.declare_input("fires", "FireInformation")

    def run(self, context):
        fireInfo = self.get_input("fires")
        dispersionData = fireInfo.dispersion

        self.log.info("Creating KMZ from aquipt output data.")
        if dispersionData is None:
            dispersionData = {}
            modes = 'fires'
            self.log.info('OutputKML will only produce fire emissions data.')
        else:
            modes = 'fires dispersion'
            self.log.info('OutputKML will produce dispersion and fire emissions data.')

        # Build Sections of external configuration file

        # Fire Locations section
        sect1 = 'DEFAULT'
        config = TemplateConfigParser()
        config.set(sect1, 'BSF_OUTPUT_DIR', self.config("OUTPUT_DIR"))
        config.set(sect1, 'MODES', modes)

        # Dispersion sections
        sect2 = 'DispersionGridInput'
        config.add_section(sect2)
        config.set(sect2, 'FILENAME', os.path.join(self.config("OUTPUT_DIR"), 'smoke_aggregate.nc'))
        parameters = list()
        parameters.append('MAXIMPACT')
        parameters.append('AVGIMPACT')
        for level in [str(int(float(a))) for a in kernel_config.get("OutputAquipt","IMPACT_LEVELS",str).split(',')]:
            parameters.append('PERCENT'+level)
            parameters.append('PCNTSIMS'+level)
        for level in [str(int(float(a))) for a in kernel_config.get("OutputAquipt","TIME_IMPACT_PCNT_LEVELS",str).split(',')]:
            parameters.append('TIMPACT'+level)
        parameter_str = ''
        for p in parameters:
            parameter_str += p + ' '
        config.set(sect2, 'PARAMETER', parameter_str)

        sect3 = 'DispersionGridOutput'
        config.add_section(sect3)
        config.set(sect3, 'OUTPUT_DIR', os.path.join(self.config('OUTPUT_DIR'), 'images'))

        sect4 = 'DispersionGridColorMap'
        if self.config('DEFINE_RGB', bool):
            opt1 = ['DEFINE_RGB','RED','GREEN','BLUE','DEFINE_HEX']
        elif self.config('DEFINE_HEX', bool):
            opt1 = ['DEFINE_HEX','HEX_COLORS','DEFINE_RGB']
        else:
            self.log.error('DEFINE_RGB or DEFINE_HEX must be set to true.')
        opt1.append('DATA_LEVELS')
        opt1.append('PERCENT_LEVELS')
        self._create_config_section(config, sect4, opt1)

        sect5 = 'DispersionImages'
        if self.config('DEFINE_RGB', bool):
            opt2 = ['DEFINE_RGB', 'BACKGROUND_COLOR_RED','BACKGROUND_COLOR_GREEN',
                    'BACKGROUND_COLOR_BLUE', 'DEFINE_HEX']
        elif self.config('DEFINE_HEX', bool):
            opt2 = ['DEFINE_HEX', 'BACKGROUND_COLOR_HEX', 'DEFINE_RGB']
        else:
            self.log.error('DEFINE_RGB or DEFINE_HEX must be set to true.')
        opt2.append('IMAGE_OPACITY_FACTOR')
        self._create_config_section(config, sect5, opt2)

        sect6 = 'SmokeDispersionKMLInput'
        opt3 = ['MET_TYPE','FIRE_LOCATION_CSV','LEGEND_IMAGE',
                'DISCLAIMER_IMAGE','FIRE_EVENT_ICON','FIRE_LOCATION_ICON']
        self._create_config_section(config, sect6, opt3)

        sect7 = 'SmokeDispersionKMLOutput'
        self._create_config_section(config, sect7, ['KMZ_FILE'])
        config.set(sect7, 'FIRE_LOCATION_CSV', os.path.join(self.config('OUTPUT_DIR')))

        # Write out config file needed by the exernal KMZ-producing executable
        config_file = context.full_path('makedispersionkml.ini')
        with open(config_file, 'w') as configfile:
            config.write(configfile)

        context.archive_file(config_file)

        # execute external kml-generating code
        def my_output_handler(logger, output, is_stderr):
            logger.log(OUTPUT, output)

        context.execute(self.config('MAKEKML_PROGRAM'),
                        output_handler = my_output_handler)

        kmz_final_file = os.path.join(self.config("OUTPUT_DIR"), self.config("KMZ_FILE"))
        kmz_temp_file = context.full_path(self.config('KMZ_FILE'))
        copyfile(kmz_temp_file, kmz_final_file)

    def _create_config_section(self, config, section, options):
        """Create a makedispersionkml INI section by copying over BlueSky INI settings."""

        config.add_section(section)
        for option in options:
            config.set(section, option, self.config(option))
