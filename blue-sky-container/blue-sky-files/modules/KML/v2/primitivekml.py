
class Element(object):
    def __init__(self, name, content="", attributes=None):
        if attributes is None:
            attributes = dict()
        self.name = name
        self.content = str(content)
        self.attributes = attributes

    def __str__(self):
        attributes_str = ""
        if self.attributes:
            attributes_str = "".join([" %s=\"%s\"" % (key, str(value)) for key, value in self.attributes.iteritems()])
        if self.content:
            return "<%s%s>%s</%s>" % (self.name, attributes_str, self.content, self.name)
        return "<%s%s/>" % (self.name, attributes_str)

    def _validate_value(self, value, valid_type_list):
        if not type(value) in valid_type_list:
            raise ValueError("Value of %s is required, not %s." % (valid_type_list[0], type(value))) # TODO: handle multiple possible types for error msg


class StringElement(Element):
    def __init__(self, name, content, attributes=None):
        self._validate_value(content, [str])
        super(StringElement, self).__init__(name, content, attributes)


class ColorElement(StringElement):
    """String element whose value is represented by 8 hex characters"""
    def __init__(self, name, content, attributes=None):
        super(ColorElement, self).__init__(name, content, attributes)
        self.content = self.content.lower()  # Force color code characters to lowercase.

    def _validate_value(self, value, valid_type_list):
        super(ColorElement, self)._validate_value(value, valid_type_list)
        try:
            int(self.content, 16)
        except ValueError:
            raise ValueError("'<%s>' assigned invalid color code: '%s'.  Must be a valid hexadecimal in the format of 'aabbggrr'" % (self.name,self.content))
        if len(self.content) != 8:
            raise ValueError("'<%s>' assigned invalid color code: '%s'.  Must be a valid hexadecimal in the format of 'aabbggrr'" % (self.name,self.content))


class BooleanElement(Element):
    def __init__(self, name, content, attributes=None):
        self._validate_value(content, [bool])
        content = int(content)  # KML recognizes boolean values as either 1 or 0
        super(BooleanElement, self).__init__(name, content, attributes)


class IntegerElement(Element):
    def __init__(self, name, content, attributes=None):
        self._validate_value(content, [int])
        super(IntegerElement, self).__init__(name, content, attributes)


class FloatElement(Element):
    def __init__(self, name, content, attributes=None):
        self._validate_value(content, [float, int])
        super(FloatElement, self).__init__(name, content, attributes)


class DoubleElement(FloatElement):
    """NOTE: Python has no type 'double', so 'doubles' are treated as 'float' types instead."""
    def __init__(self, name, content, attributes=None):
        super(DoubleElement, self).__init__(name, content, attributes)


class CoordinateElement(Element):
    def __init__(self, name, content, attributes=None):
        self._validate_value(content, [tuple])
        content = self._convert_to_str(content)
        super(CoordinateElement, self).__init__(name, content, attributes)

    def _convert_to_str(self, value):
        str_val = ""
        for val in value:
            str_val += "%s," % val
        str_val = str_val[:-1]  # Remove trailing comma
        return str_val

    def _validate_value(self, value, valid_type_list):
        super(CoordinateElement, self)._validate_value(value, valid_type_list)
        if len(value) < 2 or len(value) > 3:
            raise ValueError("Expected tuple of size 2 or 3, instead recieved %d" % len(value))
