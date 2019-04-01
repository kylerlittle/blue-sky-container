#*****************************************************************************
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

_bluesky_version_ = "3.5.1"

import os
import tempfile
import zipfile
import time
import string, math, sys
from datetime import datetime, timedelta
from emissions import Emissions
from dispersion import Dispersion
from kernel.core import Process
from kernel.types import construct_type
from kernel.bs_datetime import BSDateTime, timezone_from_str, FixedOffset
from kernel.log import OUTPUT

class VSMOKEDispersion(Dispersion):
    def init(self):
        self.declare_input("fires", "FireInformation")
        self.declare_output("fires", "FireInformation")

    def run(self, context):
        fireInfo = self.get_input("fires")

        # Define variables to run VMSOKE and VSMOKEGIS
        VSMOKE_BINARY = self.config("VSMOKE_BINARY")
        VSMOKEGIS_BINARY = self.config("VSMOKEGIS_BINARY")
        inputFile= context.full_path("VSMOKE.IPT")
        isoinputFile = context.full_path("vsmkgs.ipt")

        # Define variables for making KML and KMZ files
        intervals = [int(x) for x in (self.config("VSMOKE_ISOPLETHS")).split()]

        contour_names = [str(x) for x in (self.config("VSMOKE_ISONAMES")).split()]
        if len(contour_names) <> len(intervals): 
           raise IOError("Number of contour names does not equal number of contours")
           
        contour_colors = [str(x) for x in (self.config("VSMOKE_ISOCOLORS")).split()]
        if len(contour_colors) <> len(intervals): 
           raise IOError("Number of contour colors does not equal number of contours")

        overlay_title = self.config("OVERLAY_TITLE")
        legend_image = self.config("LEGEND_IMAGE")
       
        self.log.debug("PM Isopleths =%s" % intervals) 
        self.log.debug("PM Isopleths Names =%s" % contour_names) 
        self.log.debug("PM Isopleths Colors =%s" % contour_colors) 

        # For each fire run VSMOKE and VSMOKEGIS
        for fireLoc in fireInfo.locations():

            # Make Vsmoke input variables object with information from standard input
            inputVar = INPUTVariables(fireLoc)

            # Get emissions for fire
            emissions = fireLoc["emissions"]
            consumption = fireLoc["consumption"]
            npriod = len(emissions.time)
            self.log.info("%d hour run time for fireID %s" % (npriod, fireLoc["id"]))

            # Define variables to make KML and KMZ files
            tempDir = tempfile.gettempdir()
            docKml = os.path.join(tempDir, inputVar.fireID + "doc.kml")
            self.log.debug("Fire kmz = %s" % docKml)
            kmzFiles = []
            kmzFiles = [docKml]
            date = self.config("DATE", BSDateTime)
            kmz_filename = os.path.join(self.config("OUTPUT_DIR"),(inputVar.fireID + "_" + self.config("KMZ_FILE")))
            kmz_filename = date.strftime(kmz_filename)
            self.log.debug("Creating KMZ file " + os.path.basename(kmz_filename))

            # Make KMZ object for fire
            mykmz = KMZAnimation(docKml)

            # Add header to context text
            mykmz.AddHeader(overlay_title, legend_image)
            
            # Run VSMOKE GIS for each hour
            for hour in range(npriod):
                # Make input file to be used by VSMOKEGIS
                self.writeIsoInput(fireInfo,emissions,consumption,intervals,hour,inputVar,isoinputFile)

                # Run VSMOKEGIS
                context.execute(VSMOKEGIS_BINARY)

                # Rename input and output files and archive
                isoOutput = "VSMKGS_" + fireLoc["id"] + "_hour" + str(hour+1) + ".iso"
                GISOutput = "VSMKGS_" + fireLoc["id"] + "_hour" + str(hour+1) + ".opt"
                isoInput = "VSMKGS_" + fireLoc["id"] + "_hour" + str(hour+1) + ".ipt"
                context.copy_file("vsmkgs.iso",isoOutput)
                context.copy_file("vsmkgs.opt",GISOutput)
                context.copy_file("vsmkgs.ipt",isoInput)
                context.archive_file(isoInput)
                context.archive_file(GISOutput)
                context.archive_file(isoOutput)
       
                # Make KML file
                isoOutputFile = context.full_path("vsmkgs.iso")
                Kmlname = inputVar.fireID + "_" + str(hour+1) + ".kml"
                Kmlfile = os.path.join(tempDir,Kmlname)
                self.makeKML(context, Kmlfile, tempDir, inputVar, isoOutputFile, intervals, contour_names, contour_colors)
                
                # Append KML file to list of KML files to be made into KMZ
                kmzFiles.append(Kmlfile)

                # Add body to context text for select hour
                mykmz.AddKml(Kmlname, fireLoc, hour)

            # Add footer to context text
            mykmz.AddFooter()

            # Write context text to main KML file
            mykmz.write()

            # Make KMZ file
            z = zipfile.ZipFile(kmz_filename, "w", zipfile.ZIP_DEFLATED)
            for kml in kmzFiles:
                if os.path.exists(kml):
                    z.write(kml, os.path.basename(kml))
                else:
                    self.log.error("Failure while trying to write KMZ file -- KML file does not exist")
                    self.log.debug('File "%s" does not exist', kml)
            z.close()
            
            # Run VSMOKE for fire
            # Write input files
            self.writeInput(fireInfo,emissions,consumption,npriod,inputVar,inputFile)
            context.execute(VSMOKE_BINARY)
            
            # Rename input and output files and archive
            fireInput = "VSMOKE_" + fireLoc["id"] + ".IPT"
            fireOutput = "VSMOKE_" + fireLoc["id"] + ".OUT"
            context.copy_file("VSMOKE.IPT",fireInput)
            context.copy_file("VSMOKE.OUT",fireOutput)
            context.archive_file(fireInput)
            context.archive_file(fireOutput)

        # DispersionData output
        dispersionData = construct_type("DispersionData")
        dispersionData["grid_filetype"] = "KMZ"
        dispersionData["grid_filename"] = kmz_filename
        dispersionData["parameters"] = {"pm25": "PM25"}
        #dispersionData["start_time"] = inputVar.firestart
        dispersionData["hours"] = npriod
        fireInfo.dispersion = dispersionData        
        self.set_output("fires", fireInfo)

    def writeInput(self,fireInfo,emissions,consumption,npriod,inputVar,inputFile):
        # This function will create the input file needed to run VSMOKE
        # These parameters are fixed or are not used since user should provide stability
        hrntvl = self.config("VSMOKE_HRNTVL", float)
        lstbdy = self.config("VSMOKE_LSTBDY")
        lqread = self.config("VSMOKE_LQREAD")
        lsight = self.config("VSMOKE_LSIGHT")
        cc0crt = self.config("VSMOKE_CC0CRT", float)
        viscrt = self.config("VSMOKE_VISCRT")
        tons = 0
        for hour in range(npriod):
            tons = tons + consumption["flaming"] + consumption["smoldering"] + consumption["residual"] + consumption["duff"] 
        efpm = self.config("VSMOKE_EFPM", float)
        efco = self.config("VSMOKE_EFCO", float)
        thot = self.config("VSMOKE_THOT", float)
        tconst = self.config("VSMOKE_TCONST", float)
        tdecay = self.config("VSMOKE_TDECAY", float)
        lgrise = self.config("VSMOKE_LGRISE")
        rfrc = self.config("VSMOKE_RFRC", float)
        emtqr = self.config("VSMOKE_EMTQR", float)
        lgrise = self.config("VSMOKE_LGRISE")
        emtqr = self.config("VSMOKE_EMTQR", float)

        if inputVar.tta is None:
             inputVar.tta = self.config("VSMOKE_TTA", float)
             self.log.warn("Used default surface temperature of %f for fire %s" % (inputVar.tta, inputVar.fireID))
        if inputVar.ppa is None:
             inputVar.ppa = self.config("VSMOKE_PPA", float)
             self.log.warn("Used default surface pressure of %f for fire %s" % (inputVar.ppa, inputVar.fireID))
        if inputVar.irha is None:
             inputVar.irha = self.config("VSMOKE_IRHA", int)
             self.log.warn("Used default relative humidity of %f for fire %s" % (inputVar.irha, inputVar.fireID))
        if inputVar.ltofdy is None:
             inputVar.ltofdy = self.config("VSMOKE_LTOFDY")
             self.log.warn("Using default of sunrise %s for fire %s" % (inputVar.ltofdy, inputVar.fireID))
        if inputVar.istaba is None:
             inputVar.istaba = self.config("VSMOKE_ISTABA", int)
             self.log.warn("Used default stability of %d for fire %s" % (inputVar.istaba, inputVar.fireID))
        if inputVar.amixa is None:
             inputVar.amixa = self.config("VSMOKE_AMIXA", float)
             self.log.warn("Used default mixing height of %f for fire %s" % (inputVar.amixa, inputVar.fireID))
        if inputVar.oyinta is None:
             inputVar.oyinta = self.config("VSMOKE_OYINTA", float)
             self.log.warn("Used default horizontal crosswind dispersion of %f for fire %s" % (inputVar.oyinta, inputVar.fireID))
        if inputVar.ozinta is None:
             inputVar.ozinta = self.config("VSMOKE_OZINTA", float)
             self.log.warn("Used default vertical crosswind dispersion of %f for fire %s" % (inputVar.ozinta, inputVar.fireID))
        if inputVar.bkgpma is None:
             inputVar.bkgpma = self.config("VSMOKE_BKGPMA", float)
             self.log.warn("Used default background PM2.5 of %f for fire %s" % (inputVar.bkgpma, inputVar.fireID))
        if inputVar.bkgcoa is None:
             inputVar.bkgcoa = self.config("VSMOKE_BKGCOA", float)
             self.log.warn("Used default background CO of %f for fire %s" % (inputVar.bkgcoa, inputVar.fireID))

        with open(inputFile, "w") as f:
             f.write("60\n")
             f.write("%s\n" % inputVar.ktitle)
             f.write("%f %f %f %d %d %d %d %f %f %s %s %s %f %s\n" % (inputVar.alat, inputVar.along, inputVar.timezone,inputVar.iyear,
                                                                      inputVar.imo, inputVar.iday, npriod, inputVar.hrstrt, 
                                                                      hrntvl, lstbdy, lqread, lsight, cc0crt, viscrt))
             f.write("%f %f %f %f %f %f %f %f %s %f\n" % (inputVar.acres, tons, efpm, efco, inputVar.tfire, thot, tconst, tdecay, 
                                                          lgrise, rfrc))
             for hour in range(npriod):
                 nhour = hour + 1
                 f.write("%d %f %f %d %s %d %f %f %f %f %f %f\n" % (nhour, inputVar.tta, inputVar.ppa, inputVar.irha, 
                                                                       inputVar.ltofdy, inputVar.istaba, inputVar.amixa,
                                                                       inputVar.ua, inputVar.oyinta, inputVar.ozinta, inputVar.bkgpma,
                                                                       inputVar.bkgcoa))

             for hour in range(npriod):
                 nhour = hour + 1
                 emtqh = (emissions["heat"][hour]) / 3414425.94972   # Btu to MW
                 emtqpm = (emissions["pm25"][hour].sum()) * 251.99576 # tons/hr to g/s
                 emtqco = (emissions["co"][hour].sum()) * 251.99576   # tons/hr to g/s
                 f.write("%d %f %f %f %f\n" % (nhour, emtqpm, emtqco, emtqh, emtqr))
          
    def writeIsoInput(self,fireInfo,emissions,consumption,intervals,hour,inputVar,inputFile):
        # This function will create the input file needed to run VSMOKEGIS
        # These parameters are fixed or are not used since user should provide stability

        # Plume rise characteristics
        lgrise = self.config("VSMOKE_LGRISE")
        emtqr = self.config("VSMOKE_EMTQR", float)

        # Starting and ending distance point for centerline concentrations
        xbgn = self.config("VSMOKE_XBGN", float)
        xend = self.config("VSMOKE_XEND", float)

        # Intervals between centerline receptors (0 default is 31 log points)
        xntvl = self.config("VSMOKE_XNTVL", float)

        # Tolerance for isolines
        chitol = self.config("VSMOKE_TOL", float)

        # Number of isolines
        niso = len(intervals)

        # Displacement of dispersion output from fire start
        UTME = self.config("VSMOKE_DUTMFE", float)
        UTMN = self.config("VSMOKE_DUTMFN", float)

        # If the user does not give input variables for time of day, stability, mixing height, 
        # initial horizontal and vertical disperions, and background PM default values from vsmoke.ini will be use

        if inputVar.ltofdy is None:
             inputVar.ltofdy = self.config("VSMOKE_LTOFDY")
             self.log.warn("Using default of sunrise %s for fire %s" % (inputVar.ltofdy, inputVar.fireID))
        if inputVar.istaba is None:
             inputVar.istaba = self.config("VSMOKE_ISTABA", int)
             self.log.warn("Used default stability of %d for fire %s" % (inputVar.istaba, inputVar.fireID))
        if inputVar.amixa is None:
             inputVar.amixa = self.config("VSMOKE_AMIXA", float)
             self.log.warn("Used default mixing height of %f for fire %s" % (inputVar.amixa, inputVar.fireID))
        if inputVar.oyinta is None:
             inputVar.oyinta = self.config("VSMOKE_OYINTA", float)
             self.log.warn("Used default horizontal crosswind dispersion of %f for fire %s" % (inputVar.oyinta, inputVar.fireID))
        if inputVar.ozinta is None:
             inputVar.ozinta = self.config("VSMOKE_OZINTA", float)
             self.log.warn("Used default vertical crosswind dispersion of %f for fire %s" % (inputVar.ozinta, inputVar.fireID))
        if inputVar.bkgpma is None:
             inputVar.bkgpma = self.config("VSMOKE_BKGPMA", float)
             self.log.warn("Used default background PM2.5 of %f for fire %s" % (inputVar.bkgpma, inputVar.fireID))

        with open(inputFile, "w") as f:
             emtqh = (emissions["heat"][hour]) / 3414425.94972   # Btu to MW
             emtqpm = (emissions["pm25"][hour].sum()) * 251.99576 # tons/hr to g/s
          
             f.write("%s\n" % inputVar.ktitle)
             f.write("%s %f %f %f %f\n" % (lgrise, inputVar.acres, emtqpm, emtqh, emtqr))
             f.write("%s %d %f %f %f %f %f %f\n" % (inputVar.ltofdy, inputVar.istaba, inputVar.amixa, inputVar.ua, inputVar.wdir, 
                                                    inputVar.oyinta, inputVar.ozinta, inputVar.bkgpma)) 
             f.write("%f %f %f %f %f %d\n" % (UTME, UTMN, xbgn, xend, xntvl, niso))
             for interval in intervals:
                 f.write("%d %f\n" % (interval, chitol))

    def makeKML(self, context, Kmlfile, tempdir, inputVar, isoOutputFile, intervals, contour_names, contour_colors):
        # This subroutine will make a KML file. 
        # Based on runvsmoke.py code used to run VSMOKEGIS
        # Used KML_File class 
        rlon = inputVar.along
        rlat = inputVar.alat
        dlat = 1./111325.
        dlon = 1./(111325. * math.cos(inputVar.alat*math.pi/180.))
        SmokeColor = '2caaaaaa'
        f = open(isoOutputFile, 'r')
        ds = f.readlines()
        iso = []
        for d in ds:
            q = d.strip().split(' ')
            while q.__contains__(''):
                q.remove('')
            try:
                q.remove('*')
            except:
                pass
            if len(q)>2:
                iso.append([(float(q[1]), float(q[2]))])
            elif len(q)==2:
                iso[-1].append((float(q[0]), float(q[1])))
            else:
                iso[-1].append(iso[-1][0])
                pass
        isopleths = {}
        for i,l in map(None, iso, intervals):
            Pts = []
            for pt in i:
                X = inputVar.along+dlon*pt[0]
                Y = inputVar.alat+dlat*pt[1]
                Pts.append((X,Y))
            isopleths[str(int(l))] = Pts

        # Write kml file
        mykml = KML_File(Kmlfile)

        #create styles
        for k, interval in enumerate(intervals):
            mykml.AddStyle(name=contour_names[k],LineColor=contour_colors[k],FillColor=SmokeColor)

        mykml.open_folder('Potential Health Impacts', Open=True)
        for c, interval in enumerate(intervals):
            Name = str(interval)
            mykml.add_placemarker(isopleths[Name], name=contour_names[c],TurnOn=1)
        mykml.close_folder()
        mykml.close()
        mykml.write()

class KML_File:
    "For creating KML files used for Google Earth"
    def __init__(self, filename='test.kml'):
        self.content = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><kml xmlns="http://earth.google.com/kml/2.2"><Document>'''
        self.name = filename
    
    def write(self):
        output=open(self.name, 'w')
        output.write(self.content)
        output.close()
    def AddStyle(self, name, LineColor='647800F0', FillColor='647800F0', width=2, outline=1, fill=1):
        self.content += '''<Style id="%s"><LineStyle><color>%s</color><width>%d</width></LineStyle><PolyStyle><color>%s</color><fill>%d</fill><outline>%d</outline></PolyStyle></Style>''' %(name, LineColor, width, FillColor, fill, outline)
    def close(self):
        self.content += '''</Document></kml>'''
    
    def open_folder(self, name, Open=True):
        if Open:
           self.content += '''<Folder><name>%s</name>''' % name
        else:
           self.content += '''<Folder><name>%s</name><Style><ListStyle><listItemType>checkHideChildren</listItemType><bgColor>00ffffff</bgColor></ListStyle></Style>''' % name
    def close_folder(self):
        self.content += '''</Folder>'''
    
    def add_placemarker(self, pts, description = " ", name = " ", TurnOn=0):
        self.content += '''<Placemark><description>%s</description><name>%s</name><visibility>%d</visibility><styleUrl>#%s</styleUrl><Polygon><outerBoundaryIs><LinearRing><coordinates>''' % (description, name, TurnOn, name) 
        pts.append(pts[1])
        for p in pts[1:]:
            self.content += "%s,%s,0 " % (str(p[0]),str(p[1])) 
	    self.content = self.content[:-1] # Remove extra space
        self.content += '''</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>'''

class KMZAnimation:
    "For creating a KMZ file used for Google Earth"
    def __init__(self, filename='doc.kml'):
        self.name = filename

    def AddHeader(self, overlay_title = " ", legend_image = " "):
        self.content = '''<?xml version="1.0" encoding="UTF-8"?>
        <kml xmlns="http://earth.google.com/kml/2.2">
            <Document>
                <name>%s</name>
                <open>0</open>
                <ScreenOverlay>
                    <name>Legend</name>
                    <overlayXY x="0" y="-16" xunits="pixel" yunits="pixel"/>
                    <screenXY x="0" y="0" xunits="fraction" yunits="fraction"/>
                    <size x="145" y="245" xunits="pixels" yunits="pixels"/>
                    <color>e0ffffff</color>
                    <Icon><href>http://www.getbluesky.org/images/%s</href></Icon>
                </ScreenOverlay>
        ''' % (overlay_title, legend_image)

    def AddKml(self, kmlfile, fireLoc, hour):
        fire_dt = fireLoc["date_time"]
        hourDelta = timedelta(hours=1)
        dt = fire_dt + hourDelta * hour
        self.content = self.content + '''
            <NetworkLink>
                <name>%s</name>
                <visibility>1</visibility>
                <TimeSpan><begin>%s</begin><end>%s</end></TimeSpan>
                <Link><href>%s</href></Link>
                <Style>
                    <ListStyle>
                        <listItemType>checkHideChildren</listItemType>
                    </ListStyle>
                </Style>
            </NetworkLink>
            ''' % (dt.strftime("Hour %HZ"), dt.isoformat(), (dt + hourDelta).isoformat(), kmlfile)

    def AddFooter(self):
        self.content = self.content + '''
            </Document>
        </kml>
        '''

    def write(self):
        output=open(self.name, 'w')
        output.write(self.content)
        output.close()

class INPUTVariables:
    # Defines input variables from Fire Location
    def __init__(self, fireLoc):
        # Fire ID used for naming input and output files
        self.fireID = fireLoc["id"]

        # The variables for stability, mixing height, wind speed, wind direction, and stability are 
        # required and program will stop if they are missing or are invalid

        # Stability
        #self.istaba = fireLoc["metadata"].get("vsmoke_stability", None)
        self.istaba = fireLoc["metadata"]["vsmoke_stability"]
        if self.istaba is None:
           raise IOError("Missing stability information for fire %s" % self.fireID)
        else:
           self.istaba = int(self.istaba)
           if self.istaba > 7 or self.istaba < 1:
              raise IOError("Stability value of %s for fire %s is out of bounds" % (self.istaba,self.fireID))

        # Mixing Height
        self.amixa = fireLoc["metadata"].get("vsmoke_mixht", None)
        if self.amixa is None:
           raise IOError("Missing mixing height information for fire %s" % self.fireID)
        else:
           self.amixa = float(self.amixa)
           if self.amixa >10000:
              raise IOError("Mixing height of %s for fire %s greater than 10,000m maximum" % (self.amixa,self.fireID))

        # Wind speed
        self.ua = fireLoc["metadata"].get("vsmoke_ws", None)
        if self.ua is None:
           raise IOError("Missing wind speed for fire %s" % self.fireID)
        else:
           self.ua = float(self.ua)
           if self.ua <=0:
              raise IOError("Windspeed must be > 0 for fire %s" % self.fireID)

        # Wind direction
        self.wdir = fireLoc["metadata"].get("vsmoke_wd", None)
        if self.wdir is None:
           raise IOError("Missing wind direction for fire %s" % self.fireID)
        else:
           self.wdir = float(self.wdir)
           if self.wdir <=0 or self.wdir > 360:
              raise IOError("Wind direction must be > 0 and < 360 degrees for fire %s" % self.fireID)

        # Time zone
        self.timezone = fireLoc["metadata"].get("vsmoke_tzone", None)
        if self.timezone is None:
           raise IOError("Missing time zone information for fire %s" % self.fireID)
        else:
           self.timezone = float(self.timezone)

        # Fire Date and time information
        fire_dt = fireLoc["date_time"]
        self.iyear = fire_dt.year
        self.imo = fire_dt.month
        self.iday = fire_dt.day
        self.hrstrt = fire_dt.hour
        self.tfire = fire_dt.hour
        self.firestart = fire_dt.strftime("%H%M")

        # Title for input files
        self.ktitle = ("'VSMOKE input for fire ID %s'" % fireLoc["id"])

        # Size of fire in acres
        self.acres = fireLoc["area"]

        # Latitude and longitude of fire
        self.alat = float(fireLoc["latitude"])
        self.along = float(fireLoc["longitude"])

        # Surface temperature
        self.tta = fireLoc["metadata"].get("vsmoke_temp", None)
        if self.tta is not None:
           self.tta = float(self.tta)

        # Surface pressure
        self.ppa = fireLoc["metadata"].get("vsmoke_pressure", None)
        if self.ppa is not None:
           self.ppa = float(self.ppa)

        # Surface relative humidity
        self.irha = fireLoc["metadata"].get("vsmoke_rh", None)
        if self.irha is not None:
           self.irha = int(self.irha)
 
        # Is fire during daylight hours or nighttime
        self.ltofdy = fireLoc["metadata"].get("vsmoke_sun", None)
        if self.ltofdy is not None:
           self.ltofdy = str(self.ltofdy)

        # Initital horizontal dispersion
        self.oyinta = fireLoc["metadata"].get("vsmoke_oyinta", None)
        if self.oyinta is not None:
           self.oyinta = float(self.oyinta)

        # Initial vertical dispersion
        self.ozinta = fireLoc["metadata"].get("vsmoke_ozinta", None)
        if self.ozinta is not None:
           self.ozinta = float(self.ozinta)

        # Background PM 2.5
        self.bkgpma = fireLoc["metadata"].get("vsmoke_bkgpm", None)
        if self.bkgpma is not None:
           self.bkgpma = float(self.bkgpma)

        # Background CO
        self.bkgcoa = fireLoc["metadata"].get("vsmoke_bkgco", None)
        if self.bkgcoa is not None:
           self.bkgcoa = float(self.bkgcoa)
