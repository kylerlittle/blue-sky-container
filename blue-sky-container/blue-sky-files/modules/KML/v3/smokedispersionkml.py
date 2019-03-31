
import csv
import datetime
import json
import os
import re
import subprocess

from constants import *
from dispersiongrid import BSDispersionGrid
from polygon_generator import PolygonGenerator
import dispersion_file_utils as dfu
import firedescriptions
try:
    from pykml import pykml
    from pykml.kml_utilities import zip_files
except ImportError:
    import pykml
    from kml_utilities import zip_files

# Constants
KML_TIMESPAN_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
KML_TIMESPAN_DATE_FORMAT = "%Y-%m-%d"

class FireData(object):
    area_units = "acres"
    date_time_format = "%Y%m%d"
    emission_fields = ['pm25', 'pm10', 'co', 'co2', 'ch4', 'nox', 'nh3', 'so2', 'voc']
    fire_types = {'RX': "Prescribed Fire", 'WF': "Wild Fire"}

    def __init__(self):
        self.id = ''
        self.fire_type = ''
        self.area = 0
        self.emissions = dict()
        self.lat = 0
        self.lon = 0
        self.start_date_time = None
        self.end_date_time = None

    def placemark_description(self):
        raise NotImplementedError("Abstract method not yet implemented")


class FireLocationInfo(FireData):
    def __init__(self):
        super(FireLocationInfo, self).__init__()
        self.event_name = None
        self.event_id = None
        self.fccs_number = None
        # TODO: Add Fuel Loading?

    def _build_event_name(self, state=None, county=None, country=None):
        # TODO: Mimic SFEI event naming?
        self.event_name = "Unknown Fire in %s, %s" % (state, country)
        return self

    def _set_date_time(self, date_time_str):
        date_time_str = date_time_str[:8]  # grab only yyyymmdd
        self.start_date_time = datetime.datetime.strptime(date_time_str, self.date_time_format)
        self.end_date_time = self.start_date_time + datetime.timedelta(days=1, seconds=-1)
        return self

    def build_from_raw_data(self, raw_data):
        self.id = raw_data['id']
        self.fire_type = raw_data['type']
        self._set_date_time(raw_data['date_time'])
        self.lat = float(raw_data['latitude'])
        self.lon = float(raw_data['longitude'])
        self.area = round(float(raw_data['area']), 2)
        # Set the event name based on optional raw data
        event_name = raw_data.get('event_name')
        if event_name:
            self.event_name = event_name
        else:
            self._build_event_name(raw_data.get('state'), raw_data.get('county'), raw_data.get('country'))
        # Set the event id based on optional raw data
        self.event_id = raw_data.get('event_guid', raw_data.get('event_id', self.id))
        # Set the emissions fields based on optional raw data
        for field in self.emission_fields:
            value = raw_data.get(field)
            if value: # else ignore the field
                self.emissions[field] = round(float(value), 2)
        # Set the fccs number based on optional raw data
        self.fccs_number = raw_data.get('fccs_number')
        self.veg = raw_data.get('VEG') or raw_data.get('veg')

    def placemark_description(self):
        return firedescriptions.build_fire_location_description(self)


class FireEventInfo(FireData):
    def __init__(self):
        super(FireEventInfo, self).__init__()
        self.name = ''
        self.daily_stats_by_fccs_num = dict()
        self.daily_area = dict()
        self.daily_emissions = dict()
        self.fire_locations = list()
        self.daily_num_locations = dict()
        self.num_locations = 0
        # TODO: Add Fuel Loading

    def _update_daily_stats_by_fccs_num(self, fire_location):
        dt = fire_location.start_date_time
        if dt not in self.daily_stats_by_fccs_num:
            self.daily_stats_by_fccs_num[dt] = {}
        fccs_number = fire_location.fccs_number or 'Unknown'
        if fccs_number not in self.daily_stats_by_fccs_num[dt]:
            self.daily_stats_by_fccs_num[dt][fccs_number] = {
                'total_area': 0, 'description': fire_location.veg
            }
        d = self.daily_stats_by_fccs_num[dt][fccs_number]
        d['total_area'] += fire_location.area
        d['description'] = d['description'] or fire_location.veg

    def _update_daily_area(self, date_time, location_area):
        if date_time not in self.daily_area:
            self.daily_area[date_time] = 0
        self.daily_area[date_time] += location_area
        self.area += location_area

    def _update_daily_emissions(self, date_time, location_emissions):
        if date_time not in self.daily_emissions:
            self.daily_emissions[date_time] = dict()
        for field in location_emissions:
            if field not in self.daily_emissions[date_time]:
                self.daily_emissions[date_time][field] = 0
            if field not in self.emissions:
                self.emissions[field] = 0
            self.daily_emissions[date_time][field] += location_emissions[field]
            self.emissions[field] += location_emissions[field]  # update total emissions as well

    def _update_date_time(self, start_date_time, end_date_time):
        if not self.start_date_time or self.start_date_time > start_date_time:
            self.start_date_time = start_date_time
        if not self.end_date_time or self.end_date_time < end_date_time:
            self.end_date_time = end_date_time

    def _update_daily_num_locations(self, date_time):
        if not date_time in self.daily_num_locations:
            self.daily_num_locations[date_time] = 0
        self.daily_num_locations[date_time] += 1
        self.num_locations += 1  # update total number of fire locations as well

    def build_data_from_locations(self):
        lat_sum = 0
        lon_sum = 0
        for fire_location in self.fire_locations:
            if not self.name:
                self.name = fire_location.event_name
            if not self.id:
                self.id = fire_location.event_id
            if not self.fire_type:
                self.fire_type = fire_location.fire_type
            lat_sum += fire_location.lat
            lon_sum += fire_location.lon
            self._update_daily_area(fire_location.start_date_time, fire_location.area)
            self._update_daily_emissions(fire_location.start_date_time, fire_location.emissions)
            self._update_date_time(fire_location.start_date_time, fire_location.end_date_time)
            self._update_daily_num_locations(fire_location.start_date_time)
            self._update_daily_stats_by_fccs_num(fire_location)
        self.lat = lat_sum / self.num_locations  # Set centroid lat
        self.lon = lon_sum / self.num_locations  # Set centroid lon
        return self

    def placemark_description(self):
        return firedescriptions.build_fire_event_description(self)

class KmzCreator(object):

    def __init__(self, config, grid_bbox, start_datetime=None,
            legend_name="colorbar.png", pretty_kml=False, verbose=False):
        self._config = config

        # Is this necessary?
        global _verbose
        _verbose = verbose

        self._start_datetime = start_datetime
        self._pretty_kml = pretty_kml

        self._modes = config.get('DEFAULT', 'MODES')
        self._concentration_param = config.get('DispersionGridInput', "PARAMETER")
        self._dispersion_image_dir = config.get('DispersionGridOutput', "OUTPUT_DIR")

        section = 'SmokeDispersionKMLInput'
        self._met_type = config.get(section, "MET_TYPE")
        self._disclaimer_image = config.get(section, "DISCLAIMER_IMAGE")
        self._fire_event_icon = config.get(section, "FIRE_EVENT_ICON")
        self._fire_location_icon = config.get(section, "FIRE_LOCATION_ICON")

        self._do_create_polygons = (self._config.has_section('PolygonsKML') and
            self._config.getboolean('PolygonsKML', 'MAKE_POLYGONS_KMZ') and
            'dispersion' in self._modes)

        # Collect fire data and concentration images
        fire_locations = self._build_fire_locations(config.get(section, "FIRE_LOCATION_CSV"))
        fire_events = self._build_fire_events(fire_locations, config.get(section, "FIRE_EVENT_CSV"))
        self._fire_information = self._create_fire_info_folder(fire_events)

        self._screen_lookat = None
        if start_datetime:
            self._screen_lookat = self._create_screen_lookat(start=start_datetime, end=start_datetime)
        location_style_group = self._create_style_group('location', os.path.basename(self._fire_location_icon))
        event_style_group = self._create_style_group('event', os.path.basename(self._fire_event_icon))
        self._combined_style_group = location_style_group + event_style_group
        self._disclaimer = self._create_screen_overlay('Disclaimer', os.path.basename(self._disclaimer_image),
                                            overlay_x=1.0, overlay_y=1.0, screen_x=1.0, screen_y=1.0)
        self._concentration_information = None
        if 'dispersion' in self._modes:
            self._dispersion_images = self._collect_images()
            self._concentration_information = self._create_concentration_information(grid_bbox)
            self._image_assets = self._collect_image_assets()
            if self._do_create_polygons:
                pgGen = PolygonGenerator(self._config)
                self._polygon_kmls = [(os.path.join(pgGen.output_dir, f), dt) for f,dt in pgGen.kml_files]
                self._polygon_legend = os.path.join(pgGen.output_dir, pgGen.legend_filename)
                self._polygon_information = self._create_polygon_information(self._polygon_kmls)
                # TODO: set color on _polygon_screen_overlay?
                self._polygon_screen_overlay = self._create_screen_overlay('Legend', pgGen.legend_filename)

    def create(self, kmz_name, kml_name, prefix, include_fire_inforamation,
            include_disclaimer, include_concentration_images, include_polygons):
        kml = pykml.KML()

        root_doc_name = ("%s_%s" % (prefix, self._start_datetime.strftime('%Y%m%d'))
            if self._start_datetime else prefix)
        if self._met_type:
            root_doc_name += "_%s" % (self._met_type)
        root_doc = pykml.Document().set_name(root_doc_name).set_open(True)

        # Set default KML screen time/position
        if self._screen_lookat:
            root_doc.with_time(self._screen_lookat)

        # Create and add style KML to root Document
        if include_fire_inforamation:
            for style in self._combined_style_group:
                root_doc.with_style(style)
            root_doc.with_feature(self._fire_information)

        if include_disclaimer:
            root_doc.with_feature(self._disclaimer)

        if 'dispersion' in self._modes:
            if include_concentration_images:
                root_doc.with_feature(self._concentration_information)
            if include_polygons:
                root_doc.with_feature(self._polygon_screen_overlay)
                root_doc.with_feature(self._polygon_information)

        kml.add_element(root_doc)

        self._create_kml_file(kml, kml_name)

        kmz_assets = [kml_name]
        if include_disclaimer:
            kmz_assets.append(self._disclaimer_image)
        if include_fire_inforamation:
            kmz_assets.extend([self._fire_event_icon, self._fire_location_icon])
        if 'dispersion' in self._modes:
            if include_concentration_images:
                kmz_assets.extend(self._image_assets)
            if include_polygons:
                kmz_assets.extend([e[0] for e in self._polygon_kmls])
                kmz_assets.append(self._polygon_legend)

        self._create_kmz(kmz_name, kmz_assets)
        os.remove(kml_name)

    def create_all(self):
        if (self._config.has_option('SmokeDispersionKMLOutput', "KMZ_FILE")
                and self._config.get('SmokeDispersionKMLOutput', "KMZ_FILE")):
            self.create(self._config.get('SmokeDispersionKMLOutput', "KMZ_FILE"),
                'doc.kml', 'BSF', True, True, True, False)

        if (self._config.has_option('SmokeDispersionKMLOutput', "KMZ_FIRE_FILE")
                and self._config.get('SmokeDispersionKMLOutput', "KMZ_FIRE_FILE")):
            self.create(self._config.get('SmokeDispersionKMLOutput', "KMZ_FIRE_FILE"),
                'doc_fires.kml', 'BSFFIRES_', True, False, False, False)

        if self._do_create_polygons:
            self.create(self._config.get('PolygonsKML', "KMZ_FILE"), 'doc_polygons.kml',
                'BSF_Polygons', True, False, False, True)


    ##
    ## Private Methods
    ##

    # Data Generating Methods

    def _collect_images(self):
        return dfu.collect_dispersion_images(self._config)

    # Data Gathering Methods

    def _build_fire_locations(self, fire_locations_csv):
        fire_location_dicts = list(csv.DictReader(open(fire_locations_csv, 'rb')))

        fire_locations = list()
        for fire_dict in fire_location_dicts:
            fire_location = FireLocationInfo()
            fire_location.build_from_raw_data(fire_dict)
            fire_locations.append(fire_location)

        self._dump_fire_locations_to_json(fire_locations_csv, fire_location_dicts)

        return fire_locations

    def _dump_fire_locations_to_json(self, fire_locations_csv, fire_location_dicts):
        """Dumps fire locations to file in json format.

        If fire_locations_csv is of the form
            /path/to/<filename>.csv'
        then dump json to
            /path/to/<filename>.json

        Otherwise, dump to
            '/path/to/fire_locations.json'
        (i.e. 'fire_locations.json' in the same dir as fire_locations_csv)
        """
        try:
            fire_locations_json = re.sub('\.csv$', '.json', fire_locations_csv)
            if fire_locations_json == fire_locations_csv:
                fire_locations_json = os.path.join(os.path.dirname(
                    fire_locations_csv), 'fire_locations.json')
            with open(fire_locations_json, 'w') as f:
                f.write(json.dumps(fire_location_dicts))
        except:
            # we can live without the json dump
            pass

    def _build_fire_events(self, fire_locations, fire_events_csv):
        fire_events_dict = dict()
        for fire_location in fire_locations:
            if fire_location.event_id not in fire_events_dict:
                fire_events_dict[fire_location.event_id] = FireEventInfo()
            fire_events_dict[fire_location.event_id].fire_locations.append(fire_location)
        for event_id in fire_events_dict:
            fire_events_dict[event_id].build_data_from_locations()

        # fill in fire even names if events csv file was specified
        if fire_events_csv:
            for row in csv.DictReader(open(fire_events_csv, 'rb')):
                # if the event name is defined in the events csv, assume it's
                # correct and thus don't worry about overriding the possibly
                # correct name pulled from the locations csv
                if fire_events_dict.has_key(row['id']) and row.get('event_name'):
                    fire_events_dict[row['id']].name = row['event_name']

        fire_events = fire_events_dict.values()
        return fire_events


    # KML Creation Methods

    def _create_screen_lookat(self, start=None, end=None, latitude=40, longitude=-100,
                              altitude=4000000, altitude_mode='relativeToGround'):
        time_span = pykml.TimeSpan()
        if start is not None:
            time_span.set_begin(start.strftime(KML_TIMESPAN_DATE_FORMAT))
        if end is not None:
            time_span.set_end(end.strftime(KML_TIMESPAN_DATE_FORMAT))
        return (pykml.LookAt()
                .with_time(time_span)
                .set_latitude(latitude)
                .set_longitude(longitude)
                .set_altitude(altitude)
                .set_tilt(0.0)
                .set_altitude_mode(altitude_mode))


    def _create_style_group(self, id, icon_url):
        normal_style_id = id + '_normal'
        highlight_style_id = id + '_highlight'
        style_map = self._create_style_map(id, normal_style_id, highlight_style_id)
        normal_style = self._create_style(normal_style_id, icon_url, label_scale=0.0)
        highlight_style = self._create_style(highlight_style_id, icon_url)
        return style_map, normal_style, highlight_style


    def _create_style_map(self, style_map_id, normal_style_id, highlight_style_id):
        pair_normal = pykml.Pair().set_key('normal').set_style_url(normal_style_id)
        pair_highlight = pykml.Pair().set_key('highlight').set_style_url(highlight_style_id)
        return pykml.StyleMap(style_map_id).with_pair(pair_normal).with_pair(pair_highlight)


    def _create_style(self, id, icon_url, label_scale=1.0, icon_scale=1.0):
        # Balloon Style
        balloon_style_text = '$[description]'
        balloon_style = pykml.BalloonStyle().set_text(balloon_style_text)
        # Label Style
        label_style = pykml.LabelStyle().set_scale(label_scale)
        # Icon Style
        icon = (pykml.Icon()
                .set_href(icon_url)
                .set_refresh_interval(0.0)
                .set_view_refresh_time(0.0)
                .set_view_bound_scale(0.0))
        icon_style = pykml.IconStyle().set_scale(icon_scale).set_heading(0.0).with_icon(icon)
        return (pykml.Style(id)
                .with_balloon_style(balloon_style)
                .with_label_style(label_style)
                .with_icon_style(icon_style))


    def _create_screen_overlay(self, name, image_path,
                               overlay_x=0.0, overlay_xunits='fraction', overlay_y=0.0, overlay_yunits='fraction',
                               screen_x=0.0, screen_xunits='fraction', screen_y=0.0, screen_yunits='fraction',
                               size_x=-1.0, size_xunits='fraction', size_y=-1.0, size_yunits='fraction',
                               visible=True):
        icon = pykml.Icon().set_href(image_path)
        return (pykml.ScreenOverlay()
                .set_name(name)
                .with_icon(icon)
                .set_visibility(visible)
                .set_overlay_xy(overlay_x, overlay_y, overlay_xunits, overlay_yunits)
                .set_screen_xy(screen_x, screen_y, screen_xunits, screen_yunits)
                .set_size(size_x, size_y, size_xunits, size_yunits))


    def _create_fire_info_folder(self, fire_events):
        info_folder = pykml.Folder().set_name('Fire Information')
        for fire_event in fire_events:
            event_folder = self._create_fire_event_folder(fire_event)
            info_folder.with_feature(event_folder)
        return info_folder


    def _create_fire_event_folder(self, fire_event):
        event_description = fire_event.placemark_description()
        event_placemark = self._create_placemark(fire_event.name, event_description, '#event', fire_event.lat,
                                            fire_event.lon)
        return (pykml.Folder()
                .set_name(fire_event.name)
                .with_feature(event_placemark))


    def _create_placemark(self, name, description, style_id, lat, lon, alt=0.0, start_date_time=None,
                          end_date_time=None, altitude_mode="relativeToGround", visible=True):
        point = pykml.Point().set_coordinates((lon, lat, alt)).set_altitude_mode(altitude_mode)
        placemark =  (pykml.Placemark()
                .set_name(name)
                .set_visibility(visible)
                .set_description(description)
                .set_style_url(style_id)
                .with_geometry(point))
        if start_date_time and end_date_time:
            time_span = (pykml.TimeSpan()
                .set_begin(start_date_time.strftime(KML_TIMESPAN_DATETIME_FORMAT))
                .set_end(end_date_time.strftime(KML_TIMESPAN_DATETIME_FORMAT)))
            placemark = placemark.with_time(time_span)

        return placemark



    def _create_concentration_information(self, grid_bbox):
        kml_root = pykml.Folder().set_name('%s from Wildland Fire' % self._concentration_param.upper()).set_open(True)

        for time_series_type in TimeSeriesTypes.ALL:
            images_dict = self._dispersion_images[time_series_type]
            if images_dict:
                visible = TimeSeriesTypes.DAILY_MAXIMUM == time_series_type
                pretty_name = TIME_SERIES_PRETTY_NAMES[time_series_type]

                if images_dict['legend']:
                    # TODO:  put legends in concentration folders?
                    overlay = self._create_screen_overlay(
                        '%s Key' % (pretty_name), images_dict['legend'],
                        visible=visible)
                    kml_root = kml_root.with_feature(overlay)

                if images_dict['smoke_images']:
                    name = '%s %s' % (pretty_name, self._concentration_param.upper())
                    data = self._create_concentration_folder(name,
                        images_dict['smoke_images'], grid_bbox,
                        visible=visible)
                    kml_root = kml_root.with_feature(data)

        return kml_root


    def _create_concentration_folder(self, name, images, grid_bbox, visible=False):
        concentration_folder = pykml.Folder().set_name(name)
        for image in images:
            overlay_datetime_str = image.replace('.', '_').split('_')[-2] # Ex: 'hourly_20130101.png' would yield '20130101'
            if len(overlay_datetime_str) == 8:
                image_datetime_format = '%Y%m%d'
                overlay_datetime_format = '%Y%m%d'
                end_offset = 24
            else:  # len == 12
                image_datetime_format = '%Y%m%d%H00'
                overlay_datetime_format = '%Y%m%d%H'
                end_offset = 1
            overlay_start = datetime.datetime.strptime(overlay_datetime_str, image_datetime_format)
            overlay_end = overlay_start + datetime.timedelta(hours=end_offset, seconds=-1)
            overlay_name = "%s %s" % (name, overlay_start.strftime(overlay_datetime_format))
            concentration_overlay = self._create_ground_overlay(overlay_name, image, grid_bbox, start_date_time=overlay_start,
                                                           end_date_time=overlay_end, visible=visible)
            concentration_folder.with_feature(concentration_overlay)
        return concentration_folder


    def _collect_image_assets(self):
        images = []
        for t_dict in self._dispersion_images.values():
            if t_dict['legend']:
                images.append(os.path.join(t_dict['root_dir'], t_dict['legend']))
            if t_dict['smoke_images']:
                images.extend([os.path.join(t_dict['root_dir'], i) for i in t_dict['smoke_images']])
        return images


    def _create_polygon_information(self, polygon_kmls):
        kml_root = pykml.Folder().set_name('%s from Wildland Fire' % self._concentration_param.upper()).set_open(True)
        for (poly_kml, dt) in polygon_kmls:
            link = pykml.Link().set_href(os.path.basename(poly_kml))
            list_style = pykml.ListStyle().set_list_item_type('checkHideChildren')
            style = pykml.Style().with_list_style(list_style)
            time_span = pykml.TimeSpan().set_begin(dt.isoformat()).set_end((dt + datetime.timedelta(hours=1)).isoformat())
            f = (pykml.NetworkLink()
                .set_name(dt.strftime("Hour %HZ"))
                .set_visibility(True)
                .with_link(link)
                .with_style(style)
                .with_time(time_span))

            kml_root.with_feature(f)

        return kml_root

    def _sort_images_legends(self, images, legends):
        combined = zip(images, legends)
        combined_natural = self._natural_sort_tuple_list(combined)
        return tuple(list(item) for item in zip(*combined_natural)) # "unzip" the zipped images/legends back into different lists


    def _natural_sort_tuple_list(self, tuple_list):
        """ Alpha-numerically sort the given tuple list, as opposed to the alpha-ascii sort normally performed
        """
        convert = lambda text: int(text) if text.isdigit() else text
        alphanum_key = lambda key: [convert(x) for x in re.split('([0-9]+)', key[0])] # uses 1st item in tuple list as key
        return sorted(tuple_list, key=alphanum_key)


    def _create_ground_overlay(self, name, image_path, grid_bbox, start_date_time=None, end_date_time=None, visible=False):
        if start_date_time:
            start_date_str = start_date_time.strftime(KML_TIMESPAN_DATETIME_FORMAT)
        else:
            start_date_str = ""
        if end_date_time:
            end_date_str = end_date_time.strftime(KML_TIMESPAN_DATETIME_FORMAT)
        else:
            end_date_str = ""
        time_span = (pykml.TimeSpan()
                     .set_begin(start_date_str)
                     .set_end(end_date_str))
        icon = pykml.Icon().set_href(image_path)
        west, south, east, north = (float(val) for val in grid_bbox)
        lat_lon_box = pykml.LatLonBox().set_west(west).set_south(south).set_east(east).set_north(north)
        return (pykml.GroundOverlay()
                .set_name(name)
                .set_visibility(visible)
                .with_time(time_span)
                .with_icon(icon)
                .with_lat_lon_box(lat_lon_box))


    def _create_kml_file(self, kml, kml_name):
        with open(kml_name, 'w') as out:
            if self._pretty_kml:
                out.write(kml.to_pretty_kml())
            else:
                out.write(str(kml))


    def _create_kmz(self, kmz_file, kmz_assets):
        zip_files(kmz_file, kmz_assets)



class AquiptKmzCreator(KmzCreator):

    def create_all(self):
        self.create(self._config.get('SmokeDispersionKMLOutput', "KMZ_FILE"),
            'doc.kml', 'BSF_Aquipt', True, True, True, False)

    #
    # Private Methods
    #

    def _collect_images(self):
        return dfu.collect_aquipt_images(self._config)

    def _create_concentration_information(self, grid_bbox):
        kml_root = pykml.Folder().set_name('AQUIPT Aggregate Statistics').set_open(True)
        for t in AquiptImageTypes.ALL:
            name = AQUIPT_IMAGE_TYPE_PRETTY_NAMES[t]
            images = self._dispersion_images[t]['images']
            legends = self._dispersion_images[t]['legends']
            images, legends = self._sort_images_legends(images, legends)
            data = self._create_concentration_folder(name, images, legends, grid_bbox, visible=True, is_open=True)
            kml_root = kml_root.with_feature(data)


    def _create_concentration_folder(self, name, images, legends, grid_bbox, visible=False, is_open=False):
        concentration_folder = pykml.Folder().set_name(name).set_open(is_open)
        for image, legend in zip(images, legends):
            image_overlay = self._create_ground_overlay('Layer', image, grid_bbox, visible=visible)
            legend_overlay = self._create_screen_overlay('Key', legend, visible=visible)

            # Create a nested "parameter" folder to hold the corresponding layer and key images
            parameter_name = image[:image.find('.')]
            parameter_folder = pykml.Folder().set_name(parameter_name).with_feature(image_overlay).with_feature(legend_overlay)

            concentration_folder.with_feature(parameter_folder)

        return concentration_folder


    def _collect_image_assets(self):
        images = []
        for t_dict in self._dispersion_images.values():
            images.extend([os.path.join(t_dict['root_dir'], i) for i in t_dict['legends']])
            images.extend([os.path.join(t_dict['root_dir'], i) for i in t_dict['smoke_images']])
        return images
