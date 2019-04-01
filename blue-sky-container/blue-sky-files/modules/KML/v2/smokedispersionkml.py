
import csv
import datetime
import re
import os

import firedescriptions
try:
    from pykml import pykml
    from pykml.kml_utilities import zip_files
except ImportError:
    import pykml
    from kml_utilities import zip_files

# Constants
HOURLY_IMAGE_PREFIX = "hourly_"
DAILY_MAX_IMAGE_PREFIX = "daily_maximum_"
DAILY_AVG_IMAGE_PREFIX = "daily_average_"
KML_TIMESPAN_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
KML_TIMESPAN_DATE_FORMAT = "%Y-%m-%d"

# AQUIPT Constants
MAXIMPACT_IMAGE_PREFIX = "MAXIMPACT"
AVGIMPACT_IMAGE_PREFIX = "AVGIMPACT"
PCNTSIMS_IMAGE_PREFIX = "PCNTSIMS"
PERCENT_IMAGE_PREFIX = "PERCENT"
TIMPACT_IMAGE_PREFIX = "TIMPACT"

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
        fccs_number = raw_data.get('fccs_number')
        veg = raw_data.get('VEG')
        if fccs_number and veg: # else don't set the fire location fccs number
            self.fccs_number = "%s %s" % (fccs_number, veg)

    def placemark_description(self):
        return firedescriptions.build_fire_location_description(self)


class FireEventInfo(FireData):
    def __init__(self):
        super(FireEventInfo, self).__init__()
        self.name = ''
        self.daily_area = dict()
        self.daily_emissions = dict()
        self.fire_locations = list()
        self.daily_num_locations = dict()
        self.num_locations = 0
        # TODO: Add Fuel Loading

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
        self.lat = lat_sum / self.num_locations  # Set centroid lat
        self.lon = lon_sum / self.num_locations  # Set centroid lon
        return self

    def placemark_description(self):
        return firedescriptions.build_fire_event_description(self)


def build_smoke_dispersion_kml(config, start_datetime, grid_bbox, legend_name="colorbar.png", pretty_kml=False,
                               verbose=False):
    global _verbose
    _verbose = verbose

    modes = config.get('DEFAULT', 'MODES')

    # [DispersionGridInput] configurations
    section = 'DispersionGridInput'
    concentration_param = config.get(section, "PARAMETER")

    # [DispersionGridOutput] configurations
    section = 'DispersionGridOutput'
    dispersion_image_dir = config.get(section, "OUTPUT_DIR")

    # [SmokeDispersionKMLInput] configurations
    section = 'SmokeDispersionKMLInput'
    met_type = config.get(section, "MET_TYPE")
    fire_locations_csv = config.get(section, "FIRE_LOCATION_CSV")
    disclaimer_image = config.get(section, "DISCLAIMER_IMAGE")
    fire_event_icon = config.get(section, "FIRE_EVENT_ICON")
    fire_location_icon = config.get(section, "FIRE_LOCATION_ICON")

    # [SmokeDispersionKMLOutput] configurations
    section = 'SmokeDispersionKMLOutput'
    kmz_file = config.get(section, "KMZ_FILE")

    # Collect fire data and concentration images
    fire_locations = _build_fire_locations(fire_locations_csv)
    fire_events = _build_fire_events(fire_locations)
    if 'dispersion' in modes:
        dispersion_images = _collect_dispersion_images(dispersion_image_dir)

    # Create primary KML object
    kml = pykml.KML()

    # Create root Document
    root_doc_name = "BSF_%s" % (start_datetime.strftime('%Y%m%d'))
    if met_type: root_doc_name += "_%s" % (met_type)
    root_doc = pykml.Document().set_name(root_doc_name).set_open(True)

    # Set default KML screen time/position
    screen_lookat = _create_screen_lookat(start=start_datetime, end=start_datetime)
    root_doc.with_time(screen_lookat)

    # Create and add style KML to root Document
    location_style_group = _create_style_group('location', os.path.basename(fire_location_icon))
    event_style_group = _create_style_group('event', os.path.basename(fire_event_icon))
    combined_style_group = location_style_group + event_style_group
    for style in combined_style_group:
        root_doc.with_style(style)

    # Create and add disclaimer screen overlay KML to root Document
    disclaimer = _create_screen_overlay('Disclaimer', os.path.basename(disclaimer_image),
                                        overlay_x=1.0, overlay_y=1.0, screen_x=1.0, screen_y=1.0)
    root_doc.with_feature(disclaimer)

    # Create and add fire information related KML to root Document
    fire_information = _create_fire_info_folder(fire_events)
    root_doc.with_feature(fire_information)

    # Create and add concentratiom image related KML to root Document
    if 'dispersion' in modes:
        concentration_information = _create_concentration_information(dispersion_images, legend_name,
                                                                     concentration_param, grid_bbox)
        root_doc.with_feature(concentration_information)

    # Stick KML root document into primary KML object
    kml.add_element(root_doc)

    # FIXME: If possible, skip saving KML file to disk
    # Save temp KML file to disk
    kml_name = 'doc.kml'
    _create_kml_file(kml, kml_name, pretty_kml)

    # Create KMZ containing KML file and its various assets
    kmz_assets = [kml_name, disclaimer_image, fire_event_icon, fire_location_icon]
    if 'dispersion' in modes:
        for image in os.listdir(dispersion_image_dir):
            image_path = os.path.join(dispersion_image_dir, image)
            kmz_assets.append(image_path)

    _create_kmz(kmz_file, kmz_assets)

    # Remove temp KML file from disk
    os.remove(kml_name)

def build_aquipt_kml(config, grid_bbox, pretty_kml=False, verbose=False):
    global _verbose
    _verbose = verbose

    modes = config.get('DEFAULT', 'MODES')

    # [DispersionGridInput] configurations
    section = 'DispersionGridInput'
    parameters = config.get(section, "PARAMETER").split()

    # [DispersionGridOutput] configurations
    section = 'DispersionGridOutput'
    dispersion_image_dir = config.get(section, "OUTPUT_DIR")

    # [SmokeDispersionKMLInput] configurations
    section = 'SmokeDispersionKMLInput'
    met_type = config.get(section, "MET_TYPE")
    fire_locations_csv = config.get(section, "FIRE_LOCATION_CSV")
    disclaimer_image = config.get(section, "DISCLAIMER_IMAGE")
    fire_event_icon = config.get(section, "FIRE_EVENT_ICON")
    fire_location_icon = config.get(section, "FIRE_LOCATION_ICON")

    # [SmokeDispersionKMLOutput] configurations
    section = 'SmokeDispersionKMLOutput'
    kmz_file = config.get(section, "KMZ_FILE")

    # Collect fire data and concentration images
    fire_locations = _build_fire_locations(fire_locations_csv)
    fire_events = _build_fire_events(fire_locations)
    if 'dispersion' in modes:
        dispersion_images = _collect_aquipt_images(dispersion_image_dir)

    # Create primary KML object
    kml = pykml.KML()
    
    ###### Create root Document
    root_doc_name = "BSF_Aquipt"
    if met_type: root_doc_name += "_%s" % met_type
    root_doc = pykml.Document().set_name(root_doc_name).set_open(True)
    
    # Create and add style KML to root Document
    location_style_group = _create_style_group('location', os.path.basename(fire_location_icon))
    event_style_group = _create_style_group('event', os.path.basename(fire_event_icon))
    combined_style_group = location_style_group + event_style_group
    for style in combined_style_group:
        root_doc.with_style(style)
    
    # Create and add disclaimer screen overlay KML to root Document
    disclaimer = _create_screen_overlay('Disclaimer', os.path.basename(disclaimer_image),
                                        overlay_x=1.0, overlay_y=1.0, screen_x=1.0, screen_y=1.0)
    root_doc.with_feature(disclaimer)
    
    # Create and add fire information related KML to root Document
    fire_information = _create_fire_info_folder(fire_events)
    root_doc.with_feature(fire_information)
    
    ###### Create and add concentratiom image related KML to root Document
    if 'dispersion' in modes:
        concentration_information = _create_aquipt_concentration_information(dispersion_images, grid_bbox)
        root_doc.with_feature(concentration_information)
        
    # Stick KML root document into primary KML object
    kml.add_element(root_doc)
    
    # FIXME: If possible, skip saving KML file to disk
    # Save temp KML file to disk
    kml_name = 'doc.kml'
    _create_kml_file(kml, kml_name, pretty_kml)
    
    # Create KMZ containing KML file and its various assets
    kmz_assets = [kml_name, disclaimer_image, fire_event_icon, fire_location_icon]
    if 'dispersion' in modes:
        for image in os.listdir(dispersion_image_dir):
            image_path = os.path.join(dispersion_image_dir, image)
            kmz_assets.append(image_path)
    
    _create_kmz(kmz_file, kmz_assets)
    
    # Remove temp KML file from disk
    os.remove(kml_name)

###
# Data Gathering Methods
###

def _build_fire_locations(fire_locations_csv):
    fire_locations = list()
    for row in csv.DictReader(open(fire_locations_csv, 'rb')):
        fire_location = FireLocationInfo()
        fire_location.build_from_raw_data(row)
        fire_locations.append(fire_location)
    return fire_locations

def _build_fire_events(fire_locations):
    fire_events_dict = dict()
    for fire_location in fire_locations:
        if fire_location.event_id not in fire_events_dict:
            fire_events_dict[fire_location.event_id] = FireEventInfo()
        fire_events_dict[fire_location.event_id].fire_locations.append(fire_location)
    for event_id in fire_events_dict:
        fire_events_dict[event_id].build_data_from_locations()
    fire_events = fire_events_dict.values()
    return fire_events

def _collect_dispersion_images(dispersion_image_dir):
    images = {
        HOURLY_IMAGE_PREFIX: [],
        DAILY_MAX_IMAGE_PREFIX: [],
        DAILY_AVG_IMAGE_PREFIX: []
    }
    for image in os.listdir(dispersion_image_dir):
        if image.startswith(HOURLY_IMAGE_PREFIX):
            images[HOURLY_IMAGE_PREFIX].append(image)
        elif image.startswith(DAILY_MAX_IMAGE_PREFIX):
            images[DAILY_MAX_IMAGE_PREFIX].append(image)
        elif image.startswith(DAILY_AVG_IMAGE_PREFIX):
            images[DAILY_AVG_IMAGE_PREFIX].append(image)
    return images

def _collect_aquipt_images(image_dir):
    images = {
        MAXIMPACT_IMAGE_PREFIX: {
            'images': [],
            'legends': []
        },
        AVGIMPACT_IMAGE_PREFIX: {
            'images': [],
            'legends': []
        },
        PCNTSIMS_IMAGE_PREFIX: {
            'images': [],
            'legends': []
        },
        PERCENT_IMAGE_PREFIX: {
            'images': [],
            'legends': []
        },
        TIMPACT_IMAGE_PREFIX: {
            'images': [],
            'legends': []
        }
    }

    for image in os.listdir(image_dir):
        image_prefix = None
        if image.startswith(MAXIMPACT_IMAGE_PREFIX):
            image_prefix = MAXIMPACT_IMAGE_PREFIX
        if image.startswith(AVGIMPACT_IMAGE_PREFIX):
            image_prefix = AVGIMPACT_IMAGE_PREFIX
        if image.startswith(PCNTSIMS_IMAGE_PREFIX):
            image_prefix = PCNTSIMS_IMAGE_PREFIX
        if image.startswith(PERCENT_IMAGE_PREFIX):
            image_prefix = PERCENT_IMAGE_PREFIX
        if image.startswith(TIMPACT_IMAGE_PREFIX):
            image_prefix = TIMPACT_IMAGE_PREFIX

        if image_prefix is not None:
            images[image_prefix]['images'].append(image)
            legend = "colorbar_%s.png" % image.split('.')[0]
            images[image_prefix]['legends'].append(legend)

    return images

###
# KML Creation Methods
###

def _create_screen_lookat(start=None, end=None, latitude=40, longitude=-100,
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


def _create_style_group(id, icon_url):
    normal_style_id = id + '_normal'
    highlight_style_id = id + '_highlight'
    style_map = _create_style_map(id, normal_style_id, highlight_style_id)
    normal_style = _create_style(normal_style_id, icon_url, label_scale=0.0)
    highlight_style = _create_style(highlight_style_id, icon_url)
    return style_map, normal_style, highlight_style


def _create_style_map(style_map_id, normal_style_id, highlight_style_id):
    pair_normal = pykml.Pair().set_key('normal').set_style_url(normal_style_id)
    pair_highlight = pykml.Pair().set_key('highlight').set_style_url(highlight_style_id)
    return pykml.StyleMap(style_map_id).with_pair(pair_normal).with_pair(pair_highlight)


def _create_style(id, icon_url, label_scale=1.0, icon_scale=1.0):
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


def _create_screen_overlay(name, image_path,
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


def _create_fire_info_folder(fire_events):
    info_folder = pykml.Folder().set_name('Fire Information')
    for fire_event in fire_events:
        event_folder = _create_fire_event_folder(fire_event)
        info_folder.with_feature(event_folder)
    return info_folder


def _create_fire_event_folder(fire_event):
    event_description = fire_event.placemark_description()
    event_placemark = _create_placemark(fire_event.name, event_description, '#event', fire_event.lat,
                                        fire_event.lon, start_date_time=fire_event.start_date_time,
                                        end_date_time=fire_event.end_date_time)
    location_folder = _create_fire_location_folder(fire_event.fire_locations)
    return (pykml.Folder()
            .set_name(fire_event.name)
            .with_feature(event_placemark)
            .with_feature(location_folder))


def _create_fire_location_folder(fire_locations):
    location_folder = pykml.Folder().set_name('Modeled Fire Locations').set_visibility(False)
    for fire_location in fire_locations:
        location_name = "Modeled Fire Location - %s" % fire_location.start_date_time.strftime("%Y-%m-%d")
        location_description = fire_location.placemark_description()
# Is this the problem, or is it the time stamp?
        location_placemark = _create_placemark(location_name, location_description, '#location', fire_location.lat,
                                               fire_location.lon, start_date_time=fire_location.start_date_time,
                                               end_date_time=fire_location.end_date_time, visible=False)
        location_folder.with_feature(location_placemark)
    return location_folder


def _create_placemark(name, description, style_id, lat, lon, alt=0.0, start_date_time=None,
                      end_date_time=None, altitude_mode="relativeToGround", visible=True):
    time_span = (pykml.TimeSpan()
                 .set_begin(start_date_time.strftime(KML_TIMESPAN_DATETIME_FORMAT))
                 .set_end(end_date_time.strftime(KML_TIMESPAN_DATETIME_FORMAT)))
    point = pykml.Point().set_coordinates((lon, lat, alt)).set_altitude_mode(altitude_mode)
    return (pykml.Placemark()
            .set_name(name)
            .set_visibility(visible)
            .with_time(time_span)
            .set_description(description)
            .set_style_url(style_id)
            .with_geometry(point))


def _create_concentration_information(dispersion_images, legend_name, concentration_param, grid_bbox):
    legend_overlay = _create_screen_overlay('Key', legend_name)
    # Hourly Data
    hourly_name = 'Hourly %s' % concentration_param.upper()
    hourly_images = dispersion_images[HOURLY_IMAGE_PREFIX]
    hourly_data = _create_concentration_folder(hourly_name, hourly_images, grid_bbox, visible=True)
    # Daily Max Data
    daily_max_name = 'Daily Maximum %s' % concentration_param.upper()
    daily_max_images = dispersion_images[DAILY_MAX_IMAGE_PREFIX]
    daily_max_data = _create_concentration_folder(daily_max_name, daily_max_images, grid_bbox)
    # Daily Avg Data
    daily_avg_name = 'Daily Average %s' % concentration_param.upper()
    daily_avg_images = dispersion_images[DAILY_AVG_IMAGE_PREFIX]
    daily_avg_data = _create_concentration_folder(daily_avg_name, daily_avg_images, grid_bbox)
    return (pykml.Folder()
            .set_name('%s from Wildland Fire' % concentration_param.upper())
            .set_open(True)
            .with_feature(legend_overlay)
            .with_feature(hourly_data)
            .with_feature(daily_max_data)
            .with_feature(daily_avg_data))


def _create_aquipt_concentration_information(param_images, grid_bbox):
    
    # Average Impacts
    name = 'Average Impact'
    images = param_images[AVGIMPACT_IMAGE_PREFIX]['images']
    legends = param_images[AVGIMPACT_IMAGE_PREFIX]['legends']
    images, legends = _sort_images_legends(images, legends)
    avgimpact_data = _create_aquipt_concentration_folder(name, images, legends, grid_bbox, visible=True, is_open=True)

    # Maximum Impacts
    name = 'Maximum Impact'
    images = param_images[MAXIMPACT_IMAGE_PREFIX]['images']
    legends = param_images[MAXIMPACT_IMAGE_PREFIX]['legends']
    images, legends = _sort_images_legends(images, legends)
    maximpact_data = _create_aquipt_concentration_folder(name, images, legends, grid_bbox)

    # Percent Simulations
    name = 'Percent Simulations'
    images = param_images[PCNTSIMS_IMAGE_PREFIX]['images']
    legends = param_images[PCNTSIMS_IMAGE_PREFIX]['legends']
    images, legends = _sort_images_legends(images, legends)
    pcntsims_data = _create_aquipt_concentration_folder(name, images, legends, grid_bbox)

    # Percent Time
    name = 'Percent Time'
    images = param_images[PERCENT_IMAGE_PREFIX]['images']
    legends = param_images[PERCENT_IMAGE_PREFIX]['legends']
    images, legends = _sort_images_legends(images, legends)
    percent_data = _create_aquipt_concentration_folder(name, images, legends, grid_bbox)

    # Time Impacts
    name = 'Time Impacts'
    images = param_images[TIMPACT_IMAGE_PREFIX]['images']
    legends = param_images[TIMPACT_IMAGE_PREFIX]['legends']
    images, legends = _sort_images_legends(images, legends)
    timpacts_data = _create_aquipt_concentration_folder(name, images, legends, grid_bbox)


    return (pykml.Folder()
            .set_name('AQUIPT Aggregate Statistics')
            .set_open(True)
            .with_feature(avgimpact_data)
            .with_feature(maximpact_data)
            .with_feature(pcntsims_data)
            .with_feature(percent_data)
            .with_feature(timpacts_data))


def _sort_images_legends(images, legends):
    combined = zip(images, legends)
    combined_natural = _natural_sort_tuple_list(combined)
    return tuple(list(item) for item in zip(*combined_natural)) # "unzip" the zipped images/legends back into different lists


def _natural_sort_tuple_list(tuple_list):
    """ Alpha-numerically sort the given tuple list, as opposed to the alpha-ascii sort normally performed
    """
    convert = lambda text: int(text) if text.isdigit() else text
    alphanum_key = lambda key: [convert(x) for x in re.split('([0-9]+)', key[0])] # uses 1st item in tuple list as key
    return sorted(tuple_list, key=alphanum_key)


def _create_concentration_folder(name, dispersion_images, grid_bbox, visible=False):
    concentration_folder = pykml.Folder().set_name(name)
    for image in dispersion_images:
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
        concentration_overlay = _create_ground_overlay(overlay_name, image, grid_bbox, start_date_time=overlay_start,
                                                       end_date_time=overlay_end, visible=visible)
        concentration_folder.with_feature(concentration_overlay)
    return concentration_folder


def _create_aquipt_concentration_folder(name, dispersion_images, legend_images, grid_bbox, visible=False, is_open=False):
    concentration_folder = pykml.Folder().set_name(name).set_open(is_open)
    for image, legend in zip(dispersion_images, legend_images):
        image_overlay = _create_ground_overlay('Layer', image, grid_bbox, visible=visible)
        legend_overlay = _create_screen_overlay('Key', legend, visible=visible)

        # Create a nested "parameter" folder to hold the corresponding layer and key images
        parameter_name = image[:image.find('.')]
        parameter_folder = pykml.Folder().set_name(parameter_name).with_feature(image_overlay).with_feature(legend_overlay)
        
        concentration_folder.with_feature(parameter_folder)
                            
    return concentration_folder


def _create_ground_overlay(name, image_path, grid_bbox, start_date_time=None, end_date_time=None, visible=False):
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


def _create_kml_file(kml, kml_name, pretty_kml=False):
    with open(kml_name, 'w') as out:
        if pretty_kml:
            out.write(kml.to_pretty_kml())
        else:
            out.write(str(kml))


def _create_kmz(kmz_file, kmz_assets):
    zip_files(kmz_file, kmz_assets)
