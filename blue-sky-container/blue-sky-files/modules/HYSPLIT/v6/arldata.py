#
# arldata.py
#
# Utility module to read ARL packed data format files
#

_bluesky_version_ = "3.5.1"

from Scientific.IO.FortranFormat import FortranFormat, FortranLine
import datetime
import os
import itertools

#import _scanf as scanf
#scanf.alwaysIgnoreWhitespaceForWidthLimitedHandlers = False

class Header:
    def __init__( self, format, varnames, vardict ):
        self.__varnames = varnames
        self.__format = format
        for x in self.__varnames:
            setattr( self, x, vardict.get(x) )

    def keys( self ):
        return self.__varnames

    def values( self ):
        return [ getattr(self, x) for x in self.__varnames ]

    def dump( self ):
        print "Encoded form:", self
        print "Variables:"
        for x in self.__varnames:
            print "    %s: %s" % ( x, self.__dict__[x] )

    def __str__( self ):
        return str( FortranLine( self.values(), self.__format ) )
        #return self.__format % tuple( self.values() )

class HeaderParser:
    def __init__( self, format, varnames ):
        self.__format = FortranFormat( format )
        self.length = sum( x[1] for x in self.__format.fields )
        self.format = format
        self.varnames = varnames

    def parse( self, o ):
        try:
            if isinstance( o, basestring ):
                #t = scanf.sscanf( o, self.format )
                t = FortranLine( o, self.__format )
            elif isinstance( o, file ):
                #t = scanf.fscanf( o, self.format )
                data = o.read( self.length )
                t = FortranLine( data, self.__format )
            else:
                raise TypeError( "Cannot parse object of type: " + o.__class__.__name__ )
        #except scanf.IncompleteCaptureError:
        except:
            t = ()

        d = dict( zip(self.varnames, t) )
        rec = Header( self.format, self.varnames, d )
        return rec

HEADER_SIZE = 50
header_parser = HeaderParser(
    #"%2d%2d%2d%2d%2d%2d%2d%4s%4d%14f%14f",
    '(7I2,A4,I4,2E14.7)',
    [ "year", "month", "day", "hour", "forecast", "level", "grid", "variable",
      "exponent", "precision", "value" ]
    )
EMPTY_HEADER = " 0 0 0 0-1 0 0NULL   0             0             0"

INDEX_HEADER_SIZE = 108
index_parser = HeaderParser(
    #"%4s%3d%2d%7f%7f%7f%7f%7f%7f%7f%7f%7f%7f%7f%7f%3d%3d%3d%2d%4d",
    '(A4,I3,I2,12F7.0,3I3,I2,I4)',
    [ "data_source", "fcst_hour", "time_minutes", "pole_lat", "pole_long",
      "tangent_lat", "tangent_long", "grid_size", "orientation", "cone_angle",
      "x_synch_pnt", "y_synch_pnt", "synch_pnt_lat", "synch_pnt_long",
      "reserved", "numb_x_pnts", "numb_y_pnts", "numb_levels",
      "vertical_coordsys_flag", "record_len" ] )
EMPTY_INDEX_HEADER = " " * INDEX_HEADER_SIZE

index_level_parser = HeaderParser( #"%6f%2d", 
                                   '(F6,I2)',
                                   ["height", "num_vars"] )
index_var_parser = HeaderParser( #"%4s%3d%1c", 
                                 '(A4,I3,1X)',
                                 ["variable","checksum","reserved"] )

class Record(Header):
    def __init__( self, header, data ):
        self.__header = header
        self.__data = data
        for x, y in zip( header.keys(), header.values() ):
            setattr( self, x, y )

    def dump( self ):
        return self.__header.dump()

    def __str__( self ):
        return self.__data


class TimePeriod(Record):
    def __init__( self, arlfile, record, header, index_header, levels ):
        self.__arlfile = arlfile
        self.__record = record
        self.__index_header = index_header
        self.levels = levels

        keys = header.keys() + index_header.keys()
        values = header.values() + index_header.values()
        
        for x, y in zip( keys, values ):
            setattr( self, x, y )

        time_t = (2000 + int(self.year), int(self.month),
                  int(self.day), int(self.hour), 0, 0, 0)
        self.datetime = datetime.datetime( *time_t )
        
        # Build an empty record for use by iterRecords() if needed
        e = header_parser.parse( EMPTY_HEADER )
        # Set attributes on the empty record to correspond to this datetime
        for i in ["year","month","day","hour"]:
            setattr( e, i, getattr(self, i) )
        self.__EMPTY_RECORD = str(e).ljust( self.__arlfile.record_size )

    def getSource( self ):
        return self.__arlfile

#    def iterRecords_old( self, records_per_time=None ):
#        records_per_time = records_per_time or self.__arlfile.records_per_time
#        i = self.__record
#        j = 0
#        while (i < len(self.__arlfile.headers) and (i == self.__record or
#                self.__arlfile.headers[i].variable != "INDX")):
#            yield self.__arlfile.getRecord( i )
#            i += 1
#            j += 1
#            
#        # Ensure that records_per_time is a constant throughout the file
#        while j < records_per_time:
#            # Return empty records
#            yield self.__arlfile.EMPTY_RECORD
#            i += 1
#            j += 1
            
    def iterRecords(self):
        # First, we need to yield the INDX record for this timeperiod
        
        # Get the outer record for this timeperiod
        header = self.__arlfile.getHeader( self.__record )
        idxrec = str(header)

        # Build the index
        idxstr = ""
        for level in self.levels:
            idxstr += str( level )
            for var in level.vars:
                idxstr += str( var )
        
        # Find the record length
        record_len = index_parser.length + len( idxstr )
        
        # Build a header object to reconstruct the index header
        index_header = self.__index_header
        index_header.record_len = record_len
        idxheader = Header( index_parser.format, index_parser.varnames, 
                            dict(zip(index_header.keys(), index_header.values())) )
        
        # Construct the INDX record
        idxrec += str( idxheader )
        idxrec = idxrec.ljust( self.__arlfile.record_size )
        
        # Yield the INDX record
        yield Record( header, idxrec )        
        
        # Use the index to yield all the remaining records for this timeperiod
        for rec in self.getIndex():
            if rec["record_id"] is None:
                # If we have records in the index that don't exist, yield EMPTY_RECORD instead
                yield self.__EMPTY_RECORD
            else:
                # Use the record_id to find the record in the corresponding arlfile instance
                yield self.__arlfile.getRecord( rec["record_id"] )

    def reindex( self, arlfile ):
        # reindex will reconstruct the levels[] (and nested vars[]) arrays, as
        # well as the self.__index structure, to make the index structure match 
        # that of timeperiods from the passed-in arlfile argument.  This 
        # influences how iterRecords() returns records.       
        other = arlfile.time[0]
        
        # If the indexes are equivalent, we have nothing further to do!
        if min( i["height"] == j["height"] and i["variable"] == j["variable"]
                for i, j in zip(self.getIndex(), other.getIndex()) ) == True:
            return
        
        new_levels = []
        empty_var = lambda var: Header( index_var_parser.format, 
                                        index_var_parser.varnames,
                                        dict( variable=var.variable, checksum=0, reserved='X' ) )
        
        # Loop through the levels
        for level in other.levels:
            # Create a new empty level object
            new_level = Header( index_level_parser.format,
                                index_level_parser.varnames,
                                dict( height=level.height, num_vars=0 ))
            new_level.vars = []
            
            match = [ l for l in self.levels if l.height == level.height ]
            if len(match) == 1:
                my_level = match[0]
            else:
                # We don't have a matching level
                my_level = None
                
            # OK, now loop through the variables in this level
            for var in level.vars:
                if my_level:
                    match = [ v for v in my_level.vars if v.variable == var.variable ]
                else:
                    match = []
                
                # If we have a match, copy it over
                if len(match) == 1:
                    my_var = match[0]
                else:
                    # We don't have a matching variable, so create one
                    my_var = empty_var( var )
                    
                # Append the new var to our new vars array
                new_level.vars.append( my_var )
                new_level.num_vars += 1
                
            # Append the new level to our new levels array
            new_levels.append( new_level )
            
        # And replace our old levels array with the new one
        self.levels = new_levels

    
    def getIndex(self):
        i = 1
        ar = []
        for level in self.levels:
            for var in level.vars:
                if var.reserved == 'X':
                    record_id = None
                else:
                    record_id = self.__record + i
                    i += 1
                ar.append( dict( height=level.height, variable=var.variable, record_id=record_id  ) )
        return ar

#    def __len__( self ):
#        i = self.__record
#        while (i < len(self.__arlfile.headers) and (i == self.__record or
#                self.__arlfile.getHeader(i).variable != "INDX")):
#            i += 1
#        return i - self.__record
    
    def __len__( self ):
        myrec = self.__record
        recnums = [ t.__record for t in self.__arlfile.time ] + [len(self.__arlfile.headers)]
        nextrec = min( rec for rec in recnums if rec > myrec )
        return nextrec - myrec

    def __str__( self ):
        return "".join( str(rec) for rec in self.iterRecords() )

class ARLFile:
    def __init__( self, filename, fast=False ):
        self.file = filename
        self.reindex = False
        self.refresh(fast)
    
    def refresh( self, quickSearch ):
        # Get the outer file header
        f = open( self.file, "rb" )
        file_header = header_parser.parse( f )
        assert( file_header.variable=="INDX" )
        index = index_parser.parse( f )
        self.mainHeader = index

        # Calculate the record size
        self.record_size = (index.numb_x_pnts * index.numb_y_pnts) + HEADER_SIZE
        #self.EMPTY_RECORD = EMPTY_HEADER + (" " * (index.numb_x_pnts * index.numb_y_pnts))

        # Seek back to the start of the file
        f.seek(0)
        
        # Initialize header arrays
        self.time = []
        self.headers = []
        i = 0

        # Scan through the file and extract header information
        while True:
            try:
                f.seek( i * self.record_size )
                data = f.read( HEADER_SIZE )
            except IOError:
                break

            # Are we at EOF?
            if not data: break
            
            # Parse the record header
            #header = header_parser.parse( data )
            #self.headers.append( header )
            
            # Just insert a dummy value; we'll parse the header later if we need to
            self.headers.append( None )
                        
            # Is this an index record?
            #if header.variable == "INDX":
            if data[14:18] == "INDX":
                
                # OK, it's an index record, so we have to parse the header data
                header = header_parser.parse( data )
                self.headers[-1] = header
                
                # Extract the next INDEX_HEADER_SIZE bytes from the record
                index_block = f.read( INDEX_HEADER_SIZE )
                
                if index_block == EMPTY_INDEX_HEADER:
                    # Ignore the premature end of data, and treat the file as if it had
                    # just ended
                    break
                
                # Parse the index header
                index = index_parser.parse( index_block )
                
                levels = []
                for j in range( index.numb_levels ):
                    level = index_level_parser.parse( f )
                    level.vars = []
                    for k in range( level.num_vars ):
                        data = f.read( 8 )
                        var = index_var_parser.parse( data )
                        level.vars.append( var )
                    levels.append( level )

                # Save the time period information
                self.time.append( TimePeriod( self, i, header, index, levels ) )

                # For a quick search, hit the first two time periods to determine the intervan,
                #   then skip straight to the last 50 byte header label to read the last time period
                if quickSearch and i > 1:
                    i += 1
                    f.seek(-self.record_size,os.SEEK_END)
                    data = f.read( HEADER_SIZE )
                    header = header_parser.parse( data )
                    self.time.append( TimePeriod( self, i, header, index, levels ) )
                    break

            # Increment our counter
            i += 1

        # Save the start and end datetimes
        self.start = self.time[0].datetime
        self.end = self.time[-1].datetime

        # Calculate the time interval
        if len(self.time) >= 2:
            self.interval = self.time[1].datetime - self.time[0].datetime
        else:
            self.interval = None
            
        # Calculate the records per time
        if len(self.time) >= 1:
            self.records_per_time = len( self.time[0] )
        else:
            self.records_per_time = 0

        # And close the file handle
        f.close()

    def getFileName( self ):
        # Return the file name (without path)
        return os.path.split( self.file )[1]

    def __len__( self ):
        return len( self.time )

    def __getitem__( self, i ):
        return self.time[i]

    def __iter__( self ):
        for i in range( len(self.time) ):
            yield self[i]

    def merge( self, other, timeperiod_filter=None ):
        # Make sure we have the right type of object
        if not isinstance( other, ARLFile ):
            raise TypeError( "Merge only works with other ARLFile instances!" )

        # Get the time periods from other that we want to merge into self
        timeperiods = self.getMergeTimePeriods( other )

        # Filter the timeperiods (if filter function passed in)
        if callable(timeperiod_filter):
            timeperiods = filter( timeperiod_filter, timeperiods )

        # Call mergeTimePeriods() to actually do the merge
        self.mergeTimePeriods( *timeperiods )

        # Return the time periods we appended
        return timeperiods

    def mergeTimePeriods( self, *timeperiods ):
        if self.reindex:
            for t in timeperiods:
                # Re-index all the timeperiods to match this ARLFile instance
                t.reindex( self )
            
        if len( timeperiods ) == 0:
            # If there are no time periods to merge, return now
            return
        elif len( timeperiods ) == 1:
            # We only have one timeperiod, so get its records
            record_iter = timeperiods[0].iterRecords()
        else:
            # Build an iterator of records for all the timeperiods
            iterators = [ time.iterRecords() for time in timeperiods ]
            record_iter = itertools.chain( *iterators )

        # And actually append these records onto the current file
        self.append( record_iter )

    def getMergeTimePeriods( self, other, startpos=None ):
        # If we have no interval (the current file contains only one record)
        # then use the other file's interval, so that we don't end up with
        # uneven data spacing (which causes the HYSPLIT model to crash)
        interval = self.interval or other.interval

        if interval is None:
            # There is only one record in this file and only one record
            # in the other file: just grab that record and append it
            times = list( other.time )
        else:
            # Start at the end of the current file, unless we have a
            # different starting position passed in.  (Pass in a different
            # startpos at your own risk! This is mainly only intended to
            # allow functions like getMultiMergeTimePeriods from arltool.py
            # to get a set of hypothetical time periods to merge if something
            # else is merged first.)
            pos = startpos or self.end
            times = []
            # Loop through the timeperiods in the other file
            for time in other.time:
                # If the timeperiod is exactly interval from the current
                # position...
                if time.datetime - pos == interval:
                    # Then we want to use this timeperiod
                    times.append( time )
                    # And move our position ahead accordingly
                    pos = time.datetime

        return times

    def append( self, record_iter, backup_extension=".bak" ):
        # Start by making a backup copy
        backup_file = self.file + backup_extension
        if os.path.exists( backup_file ):
            os.remove( backup_file )
        os.rename( self.file, backup_file )

        # Point this object at the backup file while we create the new one
        new_file, self.file = self.file, backup_file

        # Open file for writing
        f = open( new_file, "wb" )

        # Chain together the records from the current file and the records
        # in the new record iterator, and loop through records in the chain...
        for rec in itertools.chain( self.iterRecords(), record_iter ):
            # ... write them to the new file ...
            f.write( str(rec) )
        
        # ... and finally close the file handle.
        f.flush()
        f.close()

        # Point this object at the new file, and rescan it so our internal
        # state is up to date
        self.file = new_file
        self.refresh()

    def __iadd__( self, other ):
        # Make sure we have the right type of object
        if not isinstance( other, TimePeriod ):
            raise TypeError( "Can only add TimePeriod objects to ARLFile!" )

        # Make sure it's the right time period to append to this file
        if self.interval is not None:
            if other.datetime - self.end != self.interval:
                raise ValueError( "Time interval varies!" )

        # Append the records from the TimePeriod
        self.append( other.iterRecords() )

        # Finally, return self
        return self
    
    def getRecordData( self, i ):
        # Open the file
        f = open( self.file, "rb" )
        
        # Get the position of the corresponding data record in the file
        record_pos = self.record_size * i
        f.seek( record_pos )
        
        # Read the record data
        data = f.read( self.record_size )
        f.close()
        
        # And return it
        return data
    
    def getHeader( self, i ):
        # Get the header from our local storage
        header = self.headers[i]
        
        # Have we not cached this header yet?
        if header is None:
            # Get the data record
            data = self.getRecordData( i )
            
            # Parse the header from the record
            header = header_parser.parse( data )
            
        # And return the header object
        return header 
    
    def getRecord( self, i ):
        # Get the header number i
        #header = self.headers[i]

        # Get the data record
        data = self.getRecordData( i )
        
        # Parse the header from the record
        header = header_parser.parse( data )

        # Return a Record object
        return Record( header, data )

    def iterRecords( self ):
        for i in range( len(self.headers) ):
            yield self.getRecord(i)


def main():
    import sys
    if len(sys.argv) >= 2:
        filename = sys.argv[1]
    else:
        filename = r"C:\hysplit4\testdata\current_archive"
        
    # Open the file
    print 'Parsing file: "%s"...' % filename,
    arlfile = ARLFile( filename )
    print "done!"
    # Loop through it
    for i, timeperiod in enumerate( arlfile ):
        print "%d: %s, contains %d records"  % ( i, timeperiod.datetime, len( timeperiod ) )
        #for level in timeperiod.levels:
        #    print "    height: %d; variables: %s" % ( level.height, 
        #                                              ", ".join( v.variable for v in level.vars ) )

def main3():
    dir = r"C:\hysplit4\testdata\temp"
    for f in [ "current_archive", "current_forecast" ]:
        filename = os.path.join( dir, f )
        # Open the file
        print 'Parsing file: "%s"...' % filename,
        arlfile = ARLFile( filename )
        print "done!"
        
        print "Records per time:", arlfile.records_per_time
        timeperiod = arlfile.time[0]
        
        for level in timeperiod.levels:
            print "    height: %d; variables: %s" % ( level.height, 
                                                      ", ".join( v.variable for v in level.vars ) )

if __name__ == "__main__":
    main()
