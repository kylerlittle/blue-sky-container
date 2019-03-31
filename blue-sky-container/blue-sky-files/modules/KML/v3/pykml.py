"""
The authoritative KML Reference:
See https://developers.google.com/kml/documentation/kmlreference for more details.
"""

"""
 TODO: These tasks would make this library complete, but were out of the scope for the BSF KML project - AMC
     - Validation for allowed/required elements.
     - Comments/documentation on how to use (show the API).
     - Add support for a variety of input types (such as varous ways to define a "color")
     - Refactor KML class to give it more of a "driving" role.
     - Add missing tags and abstract elements (various geometries, gx tags, etc)
     - See what sneaky (yet easy-to-follow) tricks there are to reduce the mass redundancy. (Such as possibly better
           class structure, utilizing __getattr__ and __call__ class methods, and/or use of decorators)
"""
__author__ = "Anthony Cavallaro"
__copyright__ = "Copyright 2013, Sonoma Technology"
__credits__ = ["Anthony Cavallaro", "Ken Craig", "John Stilley"]
__license__ = "GPLv3"
__maintainer__ = "Anthony Cavallaro"
__version__ = "1.0"

from abstractkml import *
from primitivekml import *
from kml_utilities import pretty_xml


class KML(Object):
    KML_VERSION = "2.2"
    def __init__(self):
        super(KML, self).__init__('kml')
        self.attributes = {'xmln': "http://www.opengis.net/kml/%s" % self.KML_VERSION}

    def __str__(self):
        self.content = "".join([str(element) for element in self.elements])
        out = super(KML, self).__str__()
        return "<?xml version='1.0' encoding='utf-8'?>%s" % out

    def to_pretty_kml(self):
        return pretty_xml(str(self))


class BalloonStyle(ColorStyle):
    def __init__(self, id=None):
        super(BalloonStyle, self).__init__('BalloonStyle', id)

    def set_set_bg_color(self, value):
        """kml:color"""
        return self.create_element(ColorElement, 'bgColor', value)

    def set_text_color(self, value):
        """kml:color"""
        return self.create_element(ColorElement, 'textColor', value)

    def set_text(self, value):
        """string"""
        return self.create_element(StringElement, 'text', value)

    def set_display_mode(self, value):
        """'default', 'hide'"""
        return self.create_element(StringElement, 'displayMode', value)


class Camara(AbstractView):
    def __init__(self, id=None):
        super(Camara, self).__init__('Camara', id)

    def set_longitude(self, value):
        """kml:angle180"""
        return self.create_element(FloatElement, 'longitude', value)

    def set_latitude(self, value):
        """kml:angle90"""
        return self.create_element(FloatElement, 'latitude', value)

    def set_altitude(self, value):
        """double"""
        return self.create_element(DoubleElement, 'altitude', value)

    def set_heading(self, value):
        """kml:angle360"""
        return self.create_element(FloatElement, 'heading', value)

    def set_tilt(self, value):
        """kml:angle180"""
        return self.create_element(FloatElement, 'tilt', value)

    def set_roll(self, value):
        """kml:angle180"""
        return self.create_element(FloatElement, 'roll', value)

    def set_altitude_mode(self, value):
        """altitude_mode_enum"""
        return self.create_element(StringElement, 'altitudeMode', value)


class Document(Container):
    def __init__(self, id=None):
        super(Document, self).__init__('Document', id)

        # TODO: Support 0 or more Schema elements


class Folder(Container):
    def __init__(self, id=None):
        super(Folder, self).__init__('Folder', id)


class GroundOverlay(Overlay):
    def __init__(self, id=None):
        super(GroundOverlay, self).__init__('GroundOverlay', id)

    def set_altitude(self, value):
        """double"""
        return self.create_element(DoubleElement, 'altitude', value)

    def set_altitude_mode(self, value):
        """altitude_mode_enum"""
        return self.create_element(StringElement, 'altitudeMode', value)

    def with_lat_lon_box(self, element):
        """<LatLonBox>"""
        return self.add_element(element)


# TODO: Figure out what the deal is with the KML documentation...
class Icon(Object):
    def __init__(self, id=None):
        super(Icon, self).__init__('Icon', id)

    def set_href(self, value):
        """string:url or local file path"""
        return self.create_element(StringElement, 'href', value)

    def set_refresh_interval(self, value):
        """float"""
        return self.create_element(FloatElement, 'refreshInterval', value)

    def set_view_refresh_time(self, value):
        """float"""
        return self.create_element(FloatElement, 'viewRefreshTime', value)

    def set_view_bound_scale(self, value):
        """float"""
        return self.create_element(FloatElement, 'viewBoundScale', value)


class IconStyle(ColorStyle):
    def __init__(self, id=None):
        super(IconStyle, self).__init__('IconStyle', id)

    def set_scale(self, value):
        """float"""
        return self.create_element(FloatElement, 'scale', value)

    def set_heading(self, value):
        """float"""
        return self.create_element(FloatElement, 'heading', value)

    def with_icon(self, element):
        """<Icon>"""
        return self.add_element(element)

    def set_hot_spot(self, x, y, xunits, yunits):
        """attributes"""
        return self.create_element(Element, 'heading', attributes={'x':x, 'y':y, 'xunits':xunits, 'yunits':yunits})


class ItemIcon(Object):
    def __init__(self, id=None):
        super(ItemIcon, self).__init__('ItemIcon', id)

    def set_state(self, value):
        """item_icon_mode_enum"""
        return self.create_element(StringElement, 'state', value)

    def set_href(self, value):
        """string:anyURI"""
        return self.create_element(StringElement, 'href', value)


class LabelStyle(ColorStyle):
    def __init__(self, id=None):
        super(LabelStyle, self).__init__('LabelStyle', id)

    def set_scale(self, value):
        """float"""
        return self.create_element(FloatElement, 'scale', value)


class LatLonAltBox(Object):
    def __init__(self, id=None):
        super(LatLonAltBox, self).__init__('LatLonAltBox', id)

    def set_north(self, value):
        """kml:angle90"""
        return self.create_element(FloatElement, 'north', value)

    def set_south(self, value):
        """kml:angle90"""
        return self.create_element(FloatElement, 'south', value)

    def set_east(self, value):
        """kml:angle180"""
        return self.create_element(FloatElement, 'east', value)

    def set_west(self, value):
        """kml:angle180"""
        return self.create_element(FloatElement, 'west', value)

    def set_min_altitude(self, value):
        """float"""
        return self.create_element(FloatElement, 'minAltitude', value)

    def set_max_altitude(self, value):
        """float"""
        return self.create_element(FloatElement, 'maxAltitude', value)

#    def _validate(self):
#        # Required:
#        #   north
#        #   south
#        #   east
#        #   west
#        super(LatLonAltBox, self)._validate()
#        self._validate_element_exists('north')
#        self._validate_element_exists('south')
#        self._validate_element_exists('east')
#        self._validate_element_exists('west')


class LatLonBox(Object):
    def __init__(self, id=None):
        super(LatLonBox, self).__init__('LatLonBox', id)

    def set_north(self, value):
        """kml:angle90"""
        return self.create_element(FloatElement, 'north', value)

    def set_south(self, value):
        """kml:angle90"""
        return self.create_element(FloatElement, 'south', value)

    def set_east(self, value):
        """kml:angle180"""
        return self.create_element(FloatElement, 'east', value)

    def set_west(self, value):
        """kml:angle180"""
        return self.create_element(FloatElement, 'west', value)

    def set_rotation(self, value):
        """kml:angle180"""
        return self.create_element(FloatElement, 'rotation', value)


class LineStyle(ColorStyle):
    def __init__(self, id=None):
        super(LineStyle, self).__init__('LineStyle', id)

    def set_width(self, value):
        """float"""
        return self.create_element(FloatElement, 'width', value)


class Link(Object):
    def __init__(self, id=None):
        super(Link, self).__init__('Link', id)

    def set_href(self, value):
        """string:anyURI"""
        return self.create_element(StringElement, 'href', value)

    def set_refresh_mode(self, value):
        """refresh_mode_enum"""
        return self.create_element(StringElement, 'refreshMode', value)

    def set_refresh_interval(self, value):
        """float"""
        return self.create_element(FloatElement, 'refreshInterval', value)

    def set_view_refresh_mode(self, value):
        """view_refresh_enum"""
        return self.create_element(StringElement, 'viewRefreshMode', value)

    def set_view_refresh_time(self, value):
        """float"""
        return self.create_element(FloatElement, 'viewRefreshTime', value)

    def set_view_bound_scale(self, value):
        """float"""
        return self.create_element(FloatElement, 'viewBoundScale', value)

    def set_view_format(self, value):
        # TODO
        return self

    def set_http_query(self, value):
        """string"""
        return self.create_element(StringElement, 'httpQuery', value)


class ListStyle(ColorStyle):
    def __init__(self, id=None):
        super(ListStyle, self).__init__('ListStyle', id)

    def set_list_item_type(self, value):
        """list_item_type_enum"""
        return self.create_element(StringElement, 'listItemType', value)

    def set_bg_color(self, value):
        """kml:color"""
        return self.create_element(StringElement, 'bgColor', value)

    def with_item_icon(self, element):
        """ItemIcon"""
        return self.add_element(element, assert_unique=False)


class Lod(Object):
    def __init__(self, id=None):
        super(Lod, self).__init__('Lod', id)

    def set_min_lod_pixels(self, value):
        """integer"""
        return self.create_element(IntegerElement, 'minLodPixels', value)

    def set_max_lod_pixels(self, value):
        """integer"""
        return self.create_element(IntegerElement, 'maxLodPixels', value)

    def set_min_fade_extent(self, value):
        """integer"""
        return self.create_element(IntegerElement, 'minFadeExtent', value)

    def set_max_fade_extent(self, value):
        """integer"""
        return self.create_element(IntegerElement, 'maxFadeExtent', value)

#    def _validate(self):
#        # Required:
#        #   minLodPixels
#        super(Lod, self)._validate()
#        self._validate_element_exists('minLodPixels')


class LookAt(AbstractView):
    def __init__(self, id=None):
        super(LookAt, self).__init__('LookAt', id)

    def set_longitude(self, value):
        """kml:angle180"""
        return self.create_element(FloatElement, 'longitude', value)

    def set_latitude(self, value):
        """kml:angle90"""
        return self.create_element(FloatElement, 'latitude', value)

    def set_altitude(self, value):
        """double"""
        return self.create_element(FloatElement, 'altitude', value)

    def set_heading(self, value):
        """kml:angle360"""
        return self.create_element(FloatElement, 'heading', value)

    def set_tilt(self, value):
        """kml:angle180"""
        return self.create_element(FloatElement, 'tilt', value)

    def set_range(self, value):
        """double"""
        return self.create_element(FloatElement, 'range', value)

    def set_altitude_mode(self, value):
        """altitude_mode_enum"""
        return self.create_element(StringElement, 'altitudeMode', value)

#    def _validate(self):
#        # Required:
#        #   range
#        super(LookAt, self)._validate()
#    #        self._validate_tag_exists('range') # TBD: Confirm this is required


class NetworkLink(Feature):
    def __init__(self, id=None):
        super(NetworkLink, self).__init__('NetworkLink', id)

    def set_refresh_visibility(self, value):
        """boolean"""
        return self.create_element(BooleanElement, 'refreshVisibility', value)

    def set_fly_to_view(self, value):
        """boolean"""
        return self.create_element(BooleanElement, 'flyToView', value)

    def with_link(self, element):
        """<Link>"""
        return self.add_element(element)

#    def _validate(self):
#        # REQUIRED:
#        #   Link
#        super(NetworkLink, self)._validate()
#        self._validate_element_exists('Link')


class Pair(Object):
    def __init__(self, id=None):
        super(Pair, self).__init__('Pair', id)

    def set_key(self, value):
        """string"""
        return self.create_element(StringElement, 'key', value)

    def set_style_url(self, value):
        """string: full url"""
        return self.create_element(StringElement, 'styleUrl', value)


class Placemark(Feature):
    def __init__(self, id=None):
        super(Placemark, self).__init__('Placemark', id)

    def with_geometry(self, element):
        """<Point>, <LineString>, <LinearRing>, <Polygon>, <MultiGeometry>, or <Model>"""
        return self.add_element(element)


class Point(Geometry):
    def __init__(self, id=None):
        super(Point, self).__init__('Point', id)

    def set_extrude(self, value):
        """boolean"""
        return self.create_element(BooleanElement, 'extrude', value)

    def set_altitude_mode(self, value):
        """altitude_mode_enum"""
        return self.create_element(StringElement, 'altitudeMode', value)

    def set_coordinates(self, value_tupple):
        """1 tuple(lon,lat[,alt])"""
        return self.create_element(CoordinateElement, 'coordinates', value_tupple)

#    def validate(self):
#        # REQUIRED:
#        #   coordinates
#        super(Point, self)._validate()
#        self._validate_element_exists('coordinates')


class PolyStyle(ColorStyle):
    def __init__(self, id=None):
        super(PolyStyle, self).__init__('PolyStyle', id)

    def set_fill(self, value):
        """boolean"""
        return self.create_element(BooleanElement, 'fill', value)

    def set_outline(self, value):
        """boolean"""
        return self.create_element(BooleanElement, 'outline', value)


class Region(Object):
    def __init__(self, id=None):
        super(Region, self).__init__('Region', id)

    def with_lat_lon_alt_box(self, element):
        """<LatLonAltBox>"""
        return self.add_element(element)

    def with_lod(self, element):
        """<Lod>"""
        return self.add_element(element)

#    def _validate(self):
#        # Required:
#        #   LatLonAltBox
#        super(Region, self)._validate()
#        self._validate_element_exists('LatLonAltBox')


class ScreenOverlay(Overlay):
    def __init__(self, id=None):
        super(ScreenOverlay, self).__init__('ScreenOverlay', id)

    def set_overlay_xy(self, x, y, xunits, yunits):
        """attributes"""
        return self.create_element(Element, 'overlayXY', attributes={'x':x, 'y':y, 'xunits':xunits, 'yunits':yunits})

    def set_screen_xy(self, x, y, xunits, yunits):
        """attributes"""
        return self.create_element(Element, 'screenXY', attributes={'x':x, 'y':y, 'xunits':xunits, 'yunits':yunits})

    def set_rotation_xy(self, x, y, xunits, yunits):
        """attributes"""
        return self.create_element(Element, 'rotationXY', attributes={'x':x, 'y':y, 'xunits':xunits, 'yunits':yunits})

    def set_size(self, x, y, xunits, yunits):
        """attributes"""
        return self.create_element(Element, 'size', attributes={'x':x, 'y':y, 'xunits':xunits, 'yunits':yunits})

    def set_roation(self, value):
        """float"""
        return self.create_element(FloatElement, 'rotation', value)


class Style(StyleSelector):
    def __init__(self, id=None):
        super(Style, self).__init__('Style', id)

    def with_icon_style(self, element):
        """<IconStyle>"""
        return self.add_element(element)

    def with_label_style(self, element):
        """<LabelStyle>"""
        return self.add_element(element)

    def with_line_style(self, element):
        """<LineStyle>"""
        return self.add_element(element)

    def with_poly_style(self, element):
        """<PolyStyle>"""
        return self.add_element(element)

    def with_balloon_style(self, element):
        """<BalloonStyle>"""
        return self.add_element(element)

    def with_list_style(self, element):
        """<ListStyle>"""
        return self.add_element(element)


class StyleMap(StyleSelector):
    def __init__(self, id):
        super(StyleMap, self).__init__('StyleMap', id)

    def with_pair(self, element):
        """<Pair>"""
        return self.add_element(element, assert_unique=False)

#    def _validate(self):
#        # Required:
#        #   Pair
#        super(StyleMap, self)._validate()
#        self._validate_element_exists('Pair') # TODO: Validate exactly 2 exist


class TimeSpan(TimePrimitive):
    def __init__(self, id=None):
        super(TimeSpan, self).__init__('TimeSpan', id)

    def set_begin(self, value):
        """kml:dateTime"""
        # TODO: Create DateTimeTag
        return self.create_element(StringElement, 'begin', value)

    def set_end(self, value):
        """kml:dateTime"""
        # TODO: Create DateTimeTag
        return self.create_element(StringElement, 'end', value)


class TimeStamp(TimePrimitive):
    def __init__(self, id=None):
        super(TimeStamp, self).__init__('TimeStamp', id)

    def set_when(self, value):
        """kml:dateTime"""
        # TODO: Create DateTimeTag
        return self.create_element(StringElement, 'when', value)