"""
The authoritative KML Reference:
See https://developers.google.com/kml/documentation/kmlreference for more details.
"""

from primitivekml import *
from kml_utilities import deepCopy


class Object(Element):
    def __init__(self, name, id=None):
        attributes = None
        if id:
            attributes = {'id': id}
        super(Object, self).__init__(name, attributes=attributes)
        self.elements = list()

    def __str__(self):
        self.content = "".join([str(element) for element in self.elements])
        return super(Object, self).__str__()

    @deepCopy
    def add_element(self, element, assert_unique=True):
        if assert_unique:
            self._assert_unique_element_name(element)
        self.elements.append(element)
        return self

    @deepCopy
    def insert_element_at_index(self, element, idx, assert_unique_name=True):
        if assert_unique_name:
            self._assert_unique_element_name(element)
        self.elements.insert(idx, element)
        return self

    @deepCopy
    def replace_element_at_index(self, new_element, idx, assert_unique_name=True):
        if assert_unique_name:
            self._assert_unique_element_name(new_element)
        self.elements[idx] = new_element
        return self

    def create_element(self, ElementType, name, value="", attributes=None):
        element = ElementType(name, value, attributes)
        return self.add_element(element)

    def element_name_list(self, show_indexes=False):
        if show_indexes:
            return ["%d: %s" % (i, element.name) for i, element in enumerate(self.elements)]
        return [element.name for element in self.elements]

    def get_element_at_index(self, idx):
        return self.elements[idx]

    def delete_element_at_index(self, idx):
        return self.elements.pop(idx)

    def move_element_at_index(self, from_idx, to_idx):
        element = self.delete_element_at_index(from_idx)
        self.insert_element_at_index(element, to_idx, assert_unique_name=False)
        return self

    def _element_exists(self, element_name):
        return element_name in self.element_name_list()

    def _assert_unique_element_name(self, element):
        assert not self._element_exists(element.name),\
            "'<%s>' element already exists within '<%s>'." % (element.name, self.name)


class Feature(Object):
    def __init__(self, name, id=None):
        super(Feature, self).__init__(name, id)

    def set_name(self, value):
        """string"""
        return self.create_element(StringElement, 'name', value)

    def set_visibility(self, value):
        """boolean"""
        return self.create_element(BooleanElement, 'visibility', value)

    def set_open(self, value):
        """boolean"""
        return self.create_element(BooleanElement, 'open', value)

    def set_address(self, value):
        """string"""
        return self.create_element(StringElement, 'address', value)

    def set_phone_number(self, value):
        """string"""
        return self.create_element(StringElement, 'phoneNumber', value)

    def set_description(self, value):
        """string"""
        return self.create_element(StringElement, 'description', value)

    def with_view(self, element):
        """<Camara> or <LookAt>"""
        return self.add_element(element)

    def with_time(self, element):
        """<TimeSpan> or <TimeStamp>"""
        return self.add_element(element)

    def set_style_url(self, value):
        """string:anyURI"""
        return self.create_element(StringElement, 'styleUrl', value)

    def with_style(self, element):
        """<Style> or <StyleMap>"""
        return self.add_element(element, assert_unique=False)

    def with_region(self, element):
        """<Region>"""
        return self.add_element(element)

    # TODO: Support <Metadata> (<KML2.2) & <ExtendedData> (>=KML2.2)


class Overlay(Feature):
    def __init__(self, name, id=None):
        super(Overlay, self).__init__(name, id)

    def set_color(self, value):
        """kml:color"""
        return self.create_element(ColorElement, 'color', value)

    def set_draw_order(self, value):
        """int"""
        return self.create_element(IntegerElement, 'drawOrder', value)

    def with_icon(self, element):
        """<Icon>"""
        return self.add_element(element)


class Container(Feature):
    def __init__(self, name, id=None):
        super(Container, self).__init__(name, id)

    def with_feature(self, element):
        """<NetworkLink>, <PlaceMark>, <PhotoOverlay>, <ScreenOverlay>, <GroundOverlay>, <Folder>, or <Document>"""
        return self.add_element(element, assert_unique=False)


class Geometry(Object):
    def __init__(self, name, id=None):
        super(Geometry, self).__init__(name, id)


class StyleSelector(Object):
    def __init__(self, name, id):
        super(StyleSelector, self).__init__(name, id)


class TimePrimitive(Object):
    def __init__(self, name, id=None):
        super(TimePrimitive, self).__init__(name, id)


class AbstractView(Object):
    def __init__(self, name, id=None):
        super(AbstractView, self).__init__(name, id)

    def with_time(self, element):
        """<TimeSpan> or <TimeStamp>"""
        return self.add_element(element)


class ColorStyle(Object):
    def __init__(self, tag_name, id=None):
        super(ColorStyle, self).__init__(tag_name, id)

    def set_color(self, value):
        """hex-string: 'aabbggrr'"""
        return self.create_element(ColorElement, 'color', value)

    def set_color_mode(self, value):
        """color_mode_enum"""
        return self.create_element(IntegerElement, 'colorMode', value)
