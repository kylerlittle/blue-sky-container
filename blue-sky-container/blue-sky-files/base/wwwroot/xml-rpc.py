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

from __future__ import with_statement

import sys
import os
import SimpleXMLRPCServer
import DocXMLRPCServer
import repr
_repr = repr.Repr()
_repr.maxstring = 200
repr = _repr.repr

from kernel.log import corelog
from kernel.config import config
from kernel.context import get_server_context
from kernel.modules import get_process, get_procinfo, get_procinfos
from kernel.bs_datetime import BSDateTime
from kernel.types import get_type
from kernel.utility import unique_path, bs_traceback
from kernel.structure import Structure
from kernel.core import CORE_LOCK

class BlueSkyXMLRPCRequestHandler(DocXMLRPCServer.DocCGIXMLRPCRequestHandler):
    def __init__(self):
        SimpleXMLRPCServer.SimpleXMLRPCDispatcher.__init__(self, allow_none=True, encoding=None)
        DocXMLRPCServer.XMLRPCDocGenerator.__init__(self)
        
    def system_methodSignature(self, method_name):
        if hasattr(self.instance, '_methodSignature'):
            return self.instance._methodSignature(method_name)
        return DocXMLRPCServer.DocCGIXMLRPCRequestHandler.system_methodSignature(self, method_name)
        
    def handle_request(self, request_text = None):
        """Handle a single XML-RPC request passed through a CGI post method.

        If no XML data is given then it is read from stdin. The resulting
        XML-RPC response is printed to stdout along with the correct HTTP
        headers.
        """
        
        authorized = True
        if config.get("WebServer", "REQUIRE_AUTH_TOKEN", asType=bool):
            authorized = False
            queryString = os.environ.get("QUERY_STRING", None)
            if queryString and config.has_option("WebServerAuthTokens", queryString):
                corelog.debug('Auth token successfully validated for user "%s"',
                    config.get("WebServerAuthTokens", queryString))
                authorized = True

        if not authorized:
            corelog.info("Rejecting web request due to invalid auth token")
            html = """<html>
<head>
<title>Invalid Authorization Token</title>
<head>
<body>
    <h1>Invalid Authorization Token</h1>
    <p>
        This server is restricted.  Please use a valid authorization token
        as defined in web.ini.
    </p>
</body>
</html>"""
            print "Content-Type: text/html"
            print "Content-Length: %d" % len(html)
            print
            sys.stdout.write(html)
            return
                
        if request_text is None and \
            os.environ.get('REQUEST_METHOD', None) == 'GET':
            self.handle_get()
        else:
            # POST data is normally available through stdin
            if request_text is None:
                request_text = sys.stdin.read()

            self.handle_xmlrpc(request_text)

class Dispatch(object):
    def __init__(self):
        self.context = get_server_context()

    def _listMethods(self):
        return [p.name for p in get_procinfos() if not p.is_io]
    
    def _dispatch(self, method, params):
        with CORE_LOCK:
            try:
                corelog.debug('Dispatching call for "%s" web service', method)
                procType = get_process(method)
                proc = procType(method)
                for i, paramName in enumerate(sorted(proc.inputs().keys())):
                    plug = proc.inputs()[paramName]
                    dataType = get_type(plug.type)
                    value = params[i]
                    corelog.debug('Converting value "%s" into %s for "%s" input', repr(value), dataType, paramName)
                    try:
                        value = dataType.convertValue(value)
                    except ValueError:
                        corelog.error(bs_traceback(sys.exc_info(), True))
                        raise ValueError('Invalid data or type for "%s": %s %s' % (paramName, repr(value), type(value)))
                    if isinstance(value, Structure):
                        corelog.debug('Converted value is: %s', repr(value.simplify()))
                    else:
                        corelog.debug('Converted value is: %s', repr(value))
                    plug.set_value(value)
                corelog.debug('Evaluating "%s" process', proc.name)
                proc._evaluate(self.context)
                result = dict()
                for paramName in sorted(proc.outputs().keys()):
                    value = proc.outputs()[paramName].get_value(self.context)
                    if isinstance(value, Structure):
                        value = value.simplify()
                    corelog.debug('Using value "%s" as result for "%s" output', repr(value), paramName)
                    result[paramName] = value
                return result
            except:
                corelog.error(bs_traceback(sys.exc_info(), True))
                raise
        
    def _methodHelp(self, method):
        procInfo = get_procinfo(method)
        return procInfo.documentation or procInfo.desc

    def _get_method_argstring(self, method):
        try:
            procType = get_process(method)
            proc = procType(method)
            args = sorted(proc.inputs().keys())
            return '(%s)' % ', '.join(args)
        except:
            corelog.error(bs_traceback(sys.exc_info(), True))
            raise
       
if __name__ == '__main__':
    handler = BlueSkyXMLRPCRequestHandler()
    handler.register_instance(Dispatch())
    handler.register_introspection_functions()
    corelog.debug("Handling web request with BlueSkyXMLRPCRequestHandler")
    handler.handle_request()
