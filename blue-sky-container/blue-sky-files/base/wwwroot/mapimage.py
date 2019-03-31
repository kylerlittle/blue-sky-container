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

import sys
import os
import cgi
import mapscript

from kernel.config import config, baseDir
from kernel.log import corelog
from kernel.types import construct_type
from kernel.context import get_server_context
from base.modules import maps

def main():
    form = cgi.FieldStorage()
    
    authorized = True
    if config.get("WebServer", "REQUIRE_AUTH_TOKEN", asType=bool):
        authorized = False
        authString = form.getfirst("auth")
        if authString and config.has_option("WebServerAuthTokens", authString):
            corelog.debug('Auth token successfully validated for user "%s"',
                config.get("WebServerAuthTokens", authString))
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
    
    dispersionData = construct_type("DispersionData")
    
    # Hardcode some defaults
    dispersionData.grid_filetype = "NETCDF"
    dispersionData.hours = 24
    dispersionData.parameters = dict()
    dispersionData.parameters["pm25"] = "PM2P5"
    hour = None
    bbox = None
    aggregate = None
    day = None
    debug = False
    
    # Parse variables from query string and/or POST data
    for k in form.keys():
        if k == "hour":
            hour = int(form.getfirst(k))
            continue
        elif k == "bbox":
            bbox = form.getfirst(k)
            continue
        elif k == "debug":
            debug = bool(form.getfirst(k))
            continue
        elif k == "aggregate":
            aggregate = form.getfirst(k)
            continue
        elif k == "day":
            day = int(form.getfirst(k))
            continue
            
        if k == "grid_filename":
            if not form.getfirst(k).startswith(baseDir):
                corelog.info("Ignoring invalid grid_filename path: %s", form.getfirst(k))
        if not dispersionData.set_value(k, form.getfirst(k)):
            dispersionData.parameters[k] = form.getfirst(k)
    
    # Debug mode: dump the dispersionData structure
    if debug:
        print "Content-type: text/plain\n"
        print repr(dispersionData.simplify())
        return
        
    # Get a new context object
    context = get_server_context()
    
    # Show test page if we don't have data to render
    if hour is None and day is None:
        test()
        return
    
    if not aggregate:
        aggregate = None
    
    grid, mp, layer = maps.getMapObjects(context, dispersionData, aggregate)
    
    if hour is not None:
        band = hour + 1
    elif day is not None:
        band = day + 1
    
    layer.setProcessingKey("BANDS", str(band))
    
    # Clip to bounding box (if requested)
    if bbox:
        minx, miny, maxx, maxy = [float(v) for v in bbox.split(',')] 
        minx, miny, z = grid.LL2XY.TransformPoint(minx, miny)
        maxx, maxy, z = grid.LL2XY.TransformPoint(maxx, maxy)
        mp.extent = mapscript.rectObj(minx, miny, maxx, maxy)
    
    # Render the image in memory
    img = mp.draw()
    
    # Send image to the web browser
    print "Content-type: " + img.format.mimetype + "\n"
    print img.getBytes()

TESTPAGE = """
<html>
<head>
<title>Map Image test form</title>
</head>
<body>
    <h1>Map Image test form</h1>
    
    <form action="mapimage.py" method="GET">
    <p>grid_filetype: <input type="text" name="grid_filetype" value="NETCDF"/></p>
    <p>grid_filename: <input type="text" name="grid_filename"/></p>
    <p>PM<sub>2.5</sub> variable name: <input type="text" name="pm25" value="PM2P5"/></p>
    <p>start_time: <input type="text" name="start_time"/></p>
    <p>Hours of data in file: <input type="text" name="hours" value="24"/></p>
    <p>Hour of data to render image: <input type="text" name="hour" value="0"/></p>
    <p>Bounding box of image: <input type="text" name="bbox"/></p>
    <input type="submit" value="Render Image"/>
    </form>
</body>
</html>
"""

def test():
    print "Content-Type: text/html"
    print "Content-Length: %d" % len(TESTPAGE)
    print
    print TESTPAGE
    
if __name__ == '__main__':
    main()
