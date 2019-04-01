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

from kernel.core import Process
from kernel.bs_datetime import BSDateTime
from datetime import timedelta
import os
import fpconst

class ColumnSpecificRecord(object):
    columndefs = []
    has_newline = True
    def __init__(self):
        object.__setattr__(self, "data", dict())
    
    def __setattr__(self, key, value):
        object.__getattribute__(self, "data")[key] = value
        
    def __getattr__(self, key):
        if key.startswith('_'):
            raise AttributeError(key)
        return object.__getattribute__(self, "data")[key]
    
    def __str__(self):
        outstr = ""
        for (fieldlen, name, datatype) in self.columndefs:
            try:
                data = self.data[name]
            except KeyError:
                data = None
            if data is None:
                data = ""
            elif datatype is float:
                if fpconst.isNaN(data):
                    data = ""
                elif fieldlen < 5:
                    data = str(int(data))
                elif fieldlen < 8:
                    data = "%5.4f" % data
                else:
                    data = "%8.6f" % data
            else:
                data = str(datatype(data))
            if len(data) > fieldlen:
                data = data[:fieldlen]
            if datatype is str:
                data = data.ljust(fieldlen, ' ')
            else:
                data = data.rjust(fieldlen, ' ')
            outstr += data
        return outstr + (self.has_newline and '\n' or '')

class PTINVRecord(ColumnSpecificRecord):
    has_newline = False
    columndefs = [ (  2, "STID",     int),
                   (  3, "CYID",     int),
                   ( 15, "PLANTID",  str),
                   ( 15, "POINTID",  str),
                   ( 12, "STACKID",  str),
                   (  6, "ORISID",   str),
                   (  6, "BLRID",    str),
                   (  2, "SEGMENT",  str),
                   ( 40, "PLANT",    str),
                   ( 10, "SCC",      str),
                   (  4, "BEGYR",    int),
                   (  4, "ENDYR",    int),
                   (  4, "STKHGT",   float),
                   (  6, "STKDIAM",  float),
                   (  4, "STKTEMP",  float),
                   ( 10, "STKFLOW",  float),
                   (  9, "STKVEL",   float),
                   (  8, "BOILCAP",  float),
                   (  1, "CAPUNITS", str),
                   (  2, "WINTHRU",  float),
                   (  2, "SPRTHRU",  float),
                   (  2, "SUMTHRU",  float),
                   (  2, "FALTHRU",  float),
                   (  2, "HOURS",    int),
                   (  2, "START",    int),
                   (  1, "DAYS",     int),
                   (  2, "WEEKS",    int),
                   ( 11, "THRUPUT",  float),
                   ( 12, "MAXRATE",  float),
                   (  8, "HEATCON",  float),
                   (  5, "SULFCON",  float),
                   (  5, "ASHCON",   float),
                   (  9, "NETDC",    float),
                   (  4, "SIC",      int),
                   (  9, "LATC",     float),
                   (  9, "LONC",     float),
                   (  1, "OFFSHORE", str) ]

class PTINVPollutantRecord(ColumnSpecificRecord):
    has_newline = False
    columndefs = [ ( 13, "ANN",  float),
                   ( 13, "AVD",  float),
                   (  7, "CE",   float),
                   (  3, "RE",   float),
                   ( 10, "EMF",  float),
                   (  3, "CPRI", int),
                   (  3, "CSEC", int) ]

class PTDAYRecord(ColumnSpecificRecord):
    columndefs = [ (  2, "STID",    int),
                   (  3, "CYID",    int),
                   ( 15, "FCID",    str),
                   ( 12, "SKID",    str),
                   ( 12, "DVID",    str),
                   ( 12, "PRID",    str),
                   (  5, "POLID",   str),
                   (  8, "DATE",    str),
                   (  3, "TZONNAM", str),
                   ( 18, "DAYTOT",  float),
                   (  1, "-dummy-", str),
                   ( 10, "SCC",     str) ]

class PTHOURRecord(ColumnSpecificRecord):
    columndefs = [ (  2, "STID",    int),
                   (  3, "CYID",    int),
                   ( 15, "FCID",    str),
                   ( 12, "SKID",    str),
                   ( 12, "DVID",    str),
                   ( 12, "PRID",    str),
                   (  5, "POLID",   str),
                   (  8, "DATE",    str),
                   (  3, "TZONNAM", str),
                   (  7, "HRVAL1",  float),
                   (  7, "HRVAL2",  float),
                   (  7, "HRVAL3",  float),
                   (  7, "HRVAL4",  float),
                   (  7, "HRVAL5",  float),
                   (  7, "HRVAL6",  float),
                   (  7, "HRVAL7",  float),
                   (  7, "HRVAL8",  float),
                   (  7, "HRVAL9",  float),
                   (  7, "HRVAL10", float),
                   (  7, "HRVAL11", float),
                   (  7, "HRVAL12", float),
                   (  7, "HRVAL13", float),
                   (  7, "HRVAL14", float),
                   (  7, "HRVAL15", float),
                   (  7, "HRVAL16", float),
                   (  7, "HRVAL17", float),
                   (  7, "HRVAL18", float),
                   (  7, "HRVAL19", float),
                   (  7, "HRVAL20", float),
                   (  7, "HRVAL21", float),
                   (  7, "HRVAL22", float),
                   (  7, "HRVAL23", float),
                   (  7, "HRVAL24", float),
                   (  8, "DAYTOT",  float),
                   (  1, "-dummy-", str),
                   ( 10, "SCC",     str) ]
    
    
class OutputSMOKEReadyFiles(Process):
    """ Output SMOKE-ready emissions files """
    _version_ = "1.0.0"
    
    def init(self):
        self.declare_input("fires", "FireInformation")
        #self.declare_output("fires", "FireInformation")
    
    def run(self, context):
        # Collect our inputs
        fireInfo = self.get_input("fires")
        
        ptinv_filename = os.path.join(
            self.config("OUTPUT_DIR"), 
            self.config("SMOKE_PTINV_FILE"))
        ptday_filename = os.path.join(
            self.config("OUTPUT_DIR"), 
            self.config("SMOKE_PTDAY_FILE"))
        pthour_filename = os.path.join(
            self.config("OUTPUT_DIR"), 
            self.config("SMOKE_PTHOUR_FILE"))
        filedt = self.config("DATE", BSDateTime)
        
        WRITE_PTINV_TOTALS = self.config("WRITE_PTINV_TOTALS", bool)
        WRITE_PTDAY_FILE = self.config("WRITE_PTDAY_FILE", bool)

        # The first country in this list will appear in SMOKE file headers
        countryProcessList = [x.strip() for x in self.config("COUNTRY_TO_PROCESS").split(",")]
        
        ptinv_filename = filedt.strftime(ptinv_filename)
        ptday_filename = filedt.strftime(ptday_filename)
        pthour_filename = filedt.strftime(pthour_filename)
        
        # Get open file handles
        ptinv = open(ptinv_filename, 'w')
        pthour = open(pthour_filename, 'w')

        # Write PTINV headers
        ptinv.write("#IDA\n#PTINV\n#COUNTRY %s\n" % countryProcessList[0])
        ptinv.write("#YEAR %d\n" % filedt.year)
        ptinv.write("#DESC POINT SOURCE BlueSky Framework Fire Emissions\n")
        ptinv.write("#DATA PM2_5 PM10 CO NH3 NOX SO2 VOC\n")

        if WRITE_PTDAY_FILE:
            # Write PTDAY headers
            ptday = open(ptday_filename, 'w')
            ptday.write("#EMS-95\n#PTDAY\n#COUNTRY %s\n" % countryProcessList[0])
            ptday.write("#YEAR %d\n" % filedt.year)
            ptday.write("#DESC POINT SOURCE BlueSky Framework Fire Emissions\n")
        
        # Write PTHOUR headers
        pthour.write("#EMS-95\n#PTHOUR\n#COUNTRY %s\n" % countryProcessList[0])
        pthour.write("#YEAR %d\n" % filedt.year)
        pthour.write("#DESC POINT SOURCE BlueSky Framework Fire Emissions\n")
        
        self.log.info("Writing fire locations to SMOKE-ready files")
        
        # Loop over fire locations
        numFires = 0
        skipNoEmis = 0
        skipNoPlume = 0
        skipNoFips = 0
        skipNoCountry = 0
        totalSkip = 0
        for fireLoc in fireInfo.locations():
            if fireLoc["emissions"] is None:
                self.log.debug("Fire %s has no emissions data; skip...", fireLoc)
                skipNoEmis += 1
                totalSkip += 1
                continue

            if fireLoc["plume_rise"] is None:
                self.log.debug("Fire %s has no plume rise data; skip...", fireLoc)
                skipNoPlume += 1
                totalSkip += 1
                continue

            if fireLoc['fips'] is None or fireLoc['fips'] == "-9999":
                self.log.debug("Invalid fips for %s, skip..." % fireLoc['id'])
                skipNoFips += 1
                totalSkip += 1
                continue
            
            if fireLoc['country'] not in countryProcessList:
                self.log.debug("Skipping non-%s fire %s..." % (countryProcessList[0],fireLoc['id']))
                skipNoCountry += 1
                totalSkip += 1
                continue
                
            if self.config("SEPARATE_SMOLDER", bool):
                fireTypes = ("flame", "smolder")
            else:
                fireTypes = ("total",)

            for fireType in fireTypes:
                # Calculate some vars 
                stid = fireLoc['fips'][0:2]    # State Code
                cyid = fireLoc['fips'][2:5]    # County Code
                fcid = fireLoc.uniqueid()      # Facility ID
                scc = fireLoc['scc']           # Source Classification Code
                if fireType == "total":
                    ptid = '1'                 # Point ID
                    skid = '1'                 # Stack ID
                elif fireType == "flame":
                    ptid = '1'                       # Point ID
                    skid = '1'                       # Stack ID
                    scc = scc[:-2] + "F" + scc[-1]
                elif fireType == "smolder":
                    ptid = '2'                       # Point ID
                    skid = '2'                       # Stack ID
                    scc = scc[:-2] + "S" + scc[-1]
                prid = ''                       # Process ID
                dt = fireLoc['date_time']
                date = dt.strftime('%m/%d/%y')  # Date
                
                # Figure out a valid timezone name per SMOKE's timezone list
                VALID_TIMEZONES = ['GMT','ADT','AST','EDT','EST','CDT','CST','MDT','MST','PDT','PST']
                try:
                    tzonnam = dt.tzinfo.tzname(dt)
                    if tzonnam not in VALID_TIMEZONES:
                        self.log.debug("Fire %s has timezone %s that SMOKE doesn't like" % (fcid, tzonnam))
                        tzoffset = abs(int(dt.utcoffset().seconds / 3600))
                        self.log.debug("Got tzoffset: %d" % tzoffset)
                        if tzoffset == 0:
                            tzonnam = 'GMT'
                        else:
                            tzonnam = ['EST','CST','MST','PST'][tzoffset - 5]
                        self.log.debug("Picked %s as timezone for %s" % (tzonnam, fcid))
                except IndexError:
                    self.log.debug("Can't get timezone code for %s, guessing EST" % fcid)
                    tzonnam = 'EST'
    
                num_hours = len(fireLoc["emissions"]["pm25"])
                start_hour = fireLoc["date_time"].hour
                num_hours += start_hour
                num_days = num_hours // 24
                if num_hours % 24 > 0: num_days += 1
    
                # Write PTINV record
                ptinv_rec = PTINVRecord()
                ptinv_rec.STID = stid
                ptinv_rec.CYID = cyid
                ptinv_rec.PLANTID = fcid
                ptinv_rec.POINTID = ptid
                ptinv_rec.STACKID = skid
                ptinv_rec.SCC = scc
                ptinv_rec.LATC = fireLoc["latitude"]
                ptinv_rec.LONC = fireLoc["longitude"]
                
                ptinv_rec_str = str(ptinv_rec)
                # Default to omitting pollutant records from PTINV, per Steve Reid
                if WRITE_PTINV_TOTALS:
                    for var, vkey in [('PM2_5', 'pm25'),
                                      ('PM10', 'pm10'),
                                      ('CO', 'co'),
                                      ('NH3', 'nh3'),
                                      ('NOX', 'nox'),
                                      ('SO2', 'so2'),
                                      ('VOC', 'voc')]:
                        if fireLoc["emissions"][vkey] is None: continue
                        prec = PTINVPollutantRecord()
                        prec.ANN = fireLoc["emissions"].sum(vkey)
                        prec.AVD = fireLoc["emissions"].sum(vkey)
                        ptinv_rec_str += str(prec)
                
                ptinv.write(ptinv_rec_str + "\n")
                
                # Write PTDAY records
                if WRITE_PTDAY_FILE:
                    for var, vkey in [('PM2_5', 'pm25'),
                                      ('PM10', 'pm10'),
                                      ('CO', 'co'),
                                      ('NH3', 'nh3'),
                                      ('NOX', 'nox'),
                                      ('SO2', 'so2'),
                                      ('VOC', 'voc')]:
                        if fireLoc["emissions"][vkey] is None: continue
                        for d in range(num_days):
                            dt = fireLoc["date_time"] + timedelta(days=d)
                            date = dt.strftime('%m/%d/%y')  # Date

                            ptday_rec = PTDAYRecord()
                            ptday_rec.STID = stid        # State Code
                            ptday_rec.CYID = cyid        # County Code
                            ptday_rec.FCID = fcid        # Facility ID
                            ptday_rec.SKID = ptid        # Stack ID
                            ptday_rec.DVID = skid        # Device ID
                            ptday_rec.PRID = prid        # Process ID
                            ptday_rec.POLID = var        # Pollutant name
                            ptday_rec.DATE = date        # Date
                            ptday_rec.TZONNAM = tzonnam  # Timezone name
                            
                            start_slice = max((24 * d) - start_hour, 0)
                            end_slice = min((24 * (d + 1)) - start_hour, len(fireLoc["emissions"][vkey]))
                            
                            if fireType == "flame":
                                if isinstance(fireLoc["emissions"][vkey], tuple):
                                    daytot = fireLoc["emissions"][vkey][0]
                                else:
                                    daytot = sum(tup.flame for tup in 
                                                 fireLoc["emissions"][vkey][start_slice:end_slice])
                            elif fireType == "smolder":
                                if isinstance(fireLoc["emissions"][vkey], tuple):
                                    daytot = fireLoc["emissions"][vkey][1] + fireLoc["emissions"][vkey][2]
                                else:
                                    daytot = sum((tup.smold + tup.resid) for tup in 
                                                  fireLoc["emissions"][vkey][start_slice:end_slice])
                            else:
                                if isinstance(fireLoc["emissions"][vkey], tuple):
                                    daytot = sum(fireLoc["emissions"][vkey])
                                else:
                                    daytot = sum([tup.sum() for tup in 
                                                  fireLoc["emissions"][vkey][start_slice:end_slice]])
                            
                            ptday_rec.DAYTOT = daytot                # Daily total
                            ptday_rec.SCC = scc                      # Source Classification Code
                            ptday.write(str(ptday_rec))
                
                # Write PTHOUR records               
                for var, vkey in [('PTOP', "percentile_100"), 
                                  ('PBOT', "percentile_000"), 
                                  ('LAY1F', "smoldering_fraction"),
                                  ('PM2_5', 'pm25'),
                                  ('PM10', 'pm10'),
                                  ('CO', 'co'),
                                  ('NH3', 'nh3'),
                                  ('NOX', 'nox'),
                                  ('SO2', 'so2'),
                                  ('VOC', 'voc')]:
                    if var in ('PTOP', 'PBOT', 'LAY1F'):
                        if fireLoc["plume_rise"] is None: continue
                    else:
                        if fireLoc["emissions"][vkey] is None: continue
                    for d in range(num_days):
                        dt = fireLoc["date_time"] + timedelta(days=d)
                        date = dt.strftime('%m/%d/%y')  # Date

                        pthour_rec = PTHOURRecord()
                        pthour_rec.STID = stid        # State Code
                        pthour_rec.CYID = cyid        # County Code
                        pthour_rec.FCID = fcid        # Facility ID
                        pthour_rec.SKID = ptid        # Stack ID
                        pthour_rec.DVID = skid        # Device ID
                        pthour_rec.PRID = prid        # Process ID
                        pthour_rec.POLID = var        # Pollutant name
                        pthour_rec.DATE = date        # Date
                        pthour_rec.TZONNAM = tzonnam  # Timezone name
                        pthour_rec.SCC = scc          # Source Classification Code
                           
                        daytot = 0.0
                        for hour in range(24):
                            h = (d * 24) + hour - start_hour
                            if h < 0:
                                setattr(pthour_rec, 'HRVAL' + str(hour+1), 0.0)
                                continue
                            try:
                                if var in ('PTOP', 'PBOT', 'LAY1F'):
                                    if fireType == "flame":
                                        if var == 'LAY1F':
                                            value = 0.0
                                        else:
                                            value = fireLoc.plume_rise.hours[h][vkey]
                                    elif fireType == "smolder":
                                        value = {'LAY1F': 1.0, 'PTOP': 0.0, 'PBOT': 0.0}[var]
                                    else:
                                        value = fireLoc.plume_rise.hours[h][vkey]
                                else:
                                    if fireType == "flame":
                                        value = fireLoc["emissions"][vkey][h].flame
                                    elif fireType == "smolder":
                                        value = (fireLoc["emissions"][vkey][h].smold 
                                               + fireLoc["emissions"][vkey][h].resid)
                                    else:
                                        value = fireLoc["emissions"][vkey][h].sum()
                                    daytot += value
                                setattr(pthour_rec, 'HRVAL' + str(hour+1), value)
                            except IndexError:
                                #self.log.debug("IndexError on hour %d for fire %s" % (h, fireLoc["id"]))
                                setattr(pthour_rec, 'HRVAL' + str(hour+1), 0.0)
                        
                        if var not in ('PTOP', 'PBOT', 'LAY1F'):
                            pthour_rec.DAYTOT = daytot
                        
                        pthour.write(str(pthour_rec))
                    
            numFires += 1
        
        if skipNoEmis > 0:
            self.log.info("Skipped %d fires because they had no emissions", skipNoEmis)
        if skipNoPlume > 0:
            self.log.info("Skipped %d fires because they had no plume rise", skipNoPlume)
        if skipNoFips > 0:
            self.log.info("Skipped %d fires because they had invalid FIPS codes", skipNoFips)
        if skipNoCountry > 0:
            self.log.info("Skipped %d fires because they were not in country %s", skipNoCountry,countryProcessList[0])
        if totalSkip >= len(fireInfo.locations()):
            self.log.warn("WARNING: No fires were written to SMOKE-ready files")
        else:
            self.log.info("Successfully wrote %d fires", numFires)
        
        # Clean up
        ptinv.close()
        if WRITE_PTDAY_FILE: ptday.close()
        pthour.close()
        #self.set_output("fires", fireInfo)
        
