
def deepCopy(func):
    """Decorator - Performs a deep copy on all args and kwargs."""
    from functools import wraps
    from copy import deepcopy

    @wraps(func)
    def wrapped_func(*args, **kwargs):
        """If 1st arg holds the wrapped function "func" as an attribute, then
        the arg is an instance "self" of the containing class and should not be copied."""
        kwargs = deepcopy(kwargs)
        if hasattr(args[0], func.__name__):
            self = args[0]
            args = deepcopy(args[1:])  # Ignore first arg
            return func(self, *args, **kwargs)
        args = deepcopy(args)
        return func(*args, **kwargs)
    return wrapped_func


def pretty_xml(xml_str, indent='    ', newl='\n', encoding='utf-8'):
    import xml.dom.minidom
    xml = xml.dom.minidom.parseString(xml_str)
    return xml.toprettyxml(indent=indent, newl=newl, encoding=encoding)


def zip_files(output_name, file_path_list):
    import zipfile, os
    with zipfile.ZipFile(output_name, 'w', zipfile.ZIP_DEFLATED) as f_out:
        for file_path in file_path_list:
            file_name = os.path.basename(file_path)
            f_out.write(file_path, file_name)
