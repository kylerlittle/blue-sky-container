#
#
# IndexedDataLocation.py
#
# Written by Daniel Pryden, February 2006
# Last modified by Daniel Pryden, April 15, 2008
# Adapted for use by BlueSky Framework by Ken Craig, February 22, 2010
# Copyright Sonoma Technology, Inc. (STI); All Rights Reserved
#

# This class generates a list of ARL files based on a starting date,
# a simulation length, a data directory, and an ARL index file.
# You must generate the index file with your own process.
#
# The index file consists of a 1-line header, followed by 
# one csv record for each file in the indexed archive.  Historical data
# are assumed to be on 6 hour intervals, and have sorting priority over
# forecast files, which are assumed to be on 3 hour intervals.  Times
# are assumed to be in UTC.
#
# The header and one sample record looks like this:
#
# filename,start,end,interval 
# D:\HYSPLITdata\current\EDASARC.2010020100.arl,2010-01-31 09:00:00,2010-01-31 18:00:00,3
#
# Note that the full path need not be present, as it is replaced by the data
# directory provided on class instantiation.

_bluesky_version_ = "3.5.1"

import os
import datetime
import calendar
import glob
import time
import fnmatch

import arldata

# ----------------------------------------------------------------------------
# TO DO: In Python 2.5, datetime objects gained a strptime function for this
#        very purpose.
# ----------------------------------------------------------------------------
def parseDate( datestr, format="%Y-%m-%d %H:%M:%S" ):
    time_t = time.strptime( datestr, format )
    return datetime.datetime( *time_t[0:6] )

class Error(Exception):
    def __init__(self, detail="", *args, **kwargs):
        self.type = self.__module__ + '.' + self.__class__.__name__
        self.detail = detail
        Exception.__init__(self, detail, *args, **kwargs)

class DataNotAvailableError(Error):
    pass


class CatalogIndexedData:
    DATE_FORMAT = "%Y-%m-%d" # format 2012-11-30

    def __init__(self, catalog_data_index_file_path, catalog_file_path=None, arl_data_base_dir=None):
        self._catalog_data_index_file_path = catalog_data_index_file_path
        self._catalog_file_path = catalog_file_path
        self._arl_data_base_dir = arl_data_base_dir

        # Read index file into memory
        self._arl_data_index = dict()
        self._read_index_file()

        # Read catalog file into memory
        self._arl_file_catalog = dict()
        if not self._catalog_file_path is None:
            self._read_catalog_file()

        # Collect unknown arl files
        self._arl_files_unknown = []
        if (not self._arl_data_base_dir is None) and (not self._arl_data_base_dir is None):
            self._collect_unknown_arl_files()

    def _read_index_file(self):
        if os.path.exists(self._catalog_data_index_file_path): # else we have an empty dictionary
            for arl_index_line in open(self._catalog_data_index_file_path, 'r'):
                arl_index_line = arl_index_line.strip()
                date_index, time_resolution, time_step_idxs, assoc_files = arl_index_line.split(',')

                date_index = datetime.datetime.strptime(date_index, self.DATE_FORMAT).date()
                time_resolution = int(time_resolution)

                # Transform found timestep indices into boolean list
                time_step = [False] * (24 / time_resolution)
                for index in time_step_idxs.split(' '):
                    time_step[int(index)] = True

                files = list()
                for file in assoc_files.split(' '):
                    files.append(file)

                # Put it all together
                self._arl_data_index[date_index] = dict()
                self._arl_data_index[date_index]['time_res'] = time_resolution
                self._arl_data_index[date_index]['time_step'] = time_step
                self._arl_data_index[date_index]['files'] = files


    def _read_catalog_file(self):
        if self._catalog_file_path is None:
            raise DataNotAvailableError("Catalog file was not defined during object creation.")

        if os.path.exists(self._catalog_file_path): # else we have an empty dictionary
            for arl_file_path in open(self._catalog_file_path, 'r'):
                self._arl_file_catalog[arl_file_path.strip()] = True


    def _collect_unknown_arl_files(self):
        if (self._catalog_file_path is None) or (self._arl_data_base_dir is None):
            raise DataNotAvailableError("Catalog file or arl base dir was not defined during object creation.")

        for root, dirnames, filenames in os.walk(self._arl_data_base_dir):
            for filename in fnmatch.filter(filenames, '*.arl'):
                full_filename = os.path.join(root, filename)
                if not full_filename in self._arl_file_catalog:
                    self._arl_files_unknown.append(full_filename)


    def index_unknown_arl_files(self):
        one_hour = datetime.timedelta(hours=1)
        for arl_file in self._arl_files_unknown:
            try:
                arl_file_data = arldata.ARLFile(arl_file)
                time_resolution = arl_file_data.interval.seconds // one_hour.seconds
                for time_step in arl_file_data.time:
                    date_index = time_step.datetime.date() # key is a date object for sorting later
                    time_step_index = time_step.datetime.hour / time_resolution
                    if not date_index in self._arl_data_index:
                        self._arl_data_index[date_index] = dict()
                        self._arl_data_index[date_index]['files'] = list()
                        self._arl_data_index[date_index]['time_res'] = time_resolution
                        self._arl_data_index[date_index]['time_step'] = [False] * (24 / time_resolution)

                    # Update time step index with new data
                    self._arl_data_index[date_index]['time_step'][time_step_index] = True
                    if not arl_file in self._arl_data_index[date_index]['files']:
                        self._arl_data_index[date_index]['files'].append(arl_file)
            except Exception, e:
                print str(e)
                continue


    def update_catalog_file(self):
        if self._catalog_file_path is None:
            raise DataNotAvailableError("Catalog file was not defined during object creation.")

        catalog_file = open(self._catalog_file_path, 'a')
        for arl_file in self._arl_files_unknown:
            catalog_file.write(arl_file + '\n')
        catalog_file.close()


    def _sort_dates_indexed(self):
        # Get a reverse order sorted list of dates for arl data index
        self._dates_indexed_sorted = self._arl_data_index.keys()
        self._dates_indexed_sorted.sort()
        self._dates_indexed_sorted.reverse()


    def write_data_index_file(self, requested_data_date):
        # Collect sorted data index dates
        self._dates_indexed_sorted = list()
        self._sort_dates_indexed()

        # Write data to index file
        data_index_file = open(self._catalog_data_index_file_path, 'w')
        for index_date in self._dates_indexed_sorted:
            time_resolution  = self._arl_data_index[index_date]['time_res']

            # write time_steps
            time_step = str()
            for i, has_time_step in enumerate(self._arl_data_index[index_date]['time_step']):
                if has_time_step:
                    time_step += str(i) + ' '
            time_step = time_step[:-1]

            # write files
            files = str()
            for file in self._arl_data_index[index_date]['files']:
                files += file + ' '
            files = files[:-1]

            data_index_file.write(str(index_date) + ',' + str(time_resolution) + ',' + time_step + ',' + files + '\n')
        data_index_file.close()

        # Return dict containing list of indexed dates occurring after requested date
        new_dates = dict()
        new_dates['complete_days'] = list()
        for index_date in self._dates_indexed_sorted:
            # Stop if requested date reached
            if index_date <= requested_data_date:
                break
            # Skip if time step data is incomplete
            if False in self._arl_data_index[index_date]['time_step']:
                continue
            new_dates['complete_days'].append(str(index_date))
        return new_dates


    def get_input_files(self, dt, hours_to_run):
        dt = dt.replace(minute=0, second=0, microsecond=0)
        days_range = range((hours_to_run / 24) + 1)
        date_list = [ dt + datetime.timedelta(days=d) for d in days_range ]

        file_set = dict()
        num_files_per_date = 12/len(date_list)
        for date in date_list:
            d = date.date()
            if d in self._arl_data_index:
                file_count = 0
                for file in self._arl_data_index[d]['files'][::-1]:
                    if file_count >= num_files_per_date:
                        break
                    file_set[file] = True
                    file_count += 1
        return file_set.keys()



class IndexedDataLocation:
    def __init__(self, path, historicalPath, arlindex):
        self.dataPath = path
        self.historicalDataPath = historicalPath
        self.arlindex = arlindex

    def getInputFiles( self, dt, hours ):
        """Return complete set of input files needed by the model
        This function calls getDataIndex() to construct a list of 
        available files, and getHourIntervals() to retrieve a list 
        of intervals for which we need data.  It then loops through 
        the datetime intervals and creates lists of files which could 
        be used to satisfy the data requirement for that time interval.
        It passes these lists to the appendUnique() function, which 
        assembles them into a master list of files that contains the 
        smallest number of files possible to satisfy all the data 
        requirements of the model.  This master list is then returned.
        """
        # Get index of files we will be searching for inputs
        index = self.getDataIndex()
                
        # Sort the index list by interval first (so that the EDASARC data, 
        # which is on 3-hr intervals, sorts before the forecast data, which is
        # on 6-hr intervals), and then by date.  (For forecast data, sort
        # by reversed date, because we want the *most recent* forecast that
        # contains the data we need.
        def mysort(a,b):
            if a[3] == b[3]: # is the interval equal?
                if a[3] == 6:  # is it forecast data?
                    return cmp(b[1],a[1]) # reversed sort by start date
                else:
                    return cmp(a[1],b[1]) # sort by start date
            else:
                return cmp(a[3],b[3]) # sort by interval
        index.sort( cmp=mysort )
        
        # This is the files array that we will return when complete
        files = []
        
        # Maximum gap between data files
        maxgap = datetime.timedelta(hours=3)
        mingap = datetime.timedelta(hours=0)
        
        # Loop through the time intervals we will need data for
        for cur_hr, cur_dt in enumerate( self.getSingleHourIntervals(dt, hours) ):
            
            # First, try the historical archive data
            archive_files = self.getArchiveFiles( cur_dt )
            foundIt = True
            for f in archive_files:
                if f not in files:                    
                    if os.path.exists( f[0] ):
                        files.append( f )
                    else:
                        foundIt = False
            if foundIt:
                continue
            
            # Find the coverage (the range of dates covered by data files
            # that we've already selected to be a part of the input file set)
            try:
                coverage_min = min( start for filename, start, end, interval in files )
                coverage_max = max( end for filename, start, end, interval in files )
            except:
                coverage_min = None
                coverage_max = None
            
            # Are we already covered for this time period?
            if coverage_max and coverage_min <= cur_dt <= coverage_max:
                continue           
            
            # Next, scan the index for matching files
            matching = [ (filename, start, end, interval)
                        # Select files from the index where...
                        for filename, start, end, interval in index
                        # ... the current file contains the current date
                        if (start <= cur_dt <= end)
                        # ... or the current date is between the current file
                        # and the edge of our coverage, but the gap between
                        # is smaller than or equal to our maximum allowable gap
                        or (coverage_min 
                            and end <= cur_dt <= coverage_min 
                            and (coverage_min - end) <= maxgap 
                        ) 
                        # ... and the same thing for the other side of the data
                        # coverage (since we may be going either forwards or
                        # backwards here)
                        or (coverage_max
                            and coverage_max <= cur_dt <= start
                            and (start - coverage_max) <= maxgap
                        ) ]
            
            # Get the preferred matches (3-hr data)
            preferred = [ tup for tup in matching if tup[3] == 3 ]
            if preferred:
                # If we have any preferred data that matched, use it exclusively
                matching = preferred
                        
            # We couldn't find any matching data!
            if not matching:
                # Do we have at least 75% of the data requested?
                if cur_hr > abs(hours * 0.75):
                    # Then let's just stop here and let the user at least get a partial
                    # trajectory.  But we really should propagate some kind of warning, at least...
                    break
                    
                # If we don't even have that much, let's raise an error here
                raise DataNotAvailableError( "Could not find indexed ARL data for date: " + str(cur_dt) )
            
            # Append our data to the master files list
            files = self.appendUnique( files, matching, coverage_min, coverage_max )

        # Truncate the files list if we have more than 12 files in it.
        # NOTE: This should never happen, but it's in here as a failsafe.
        # KJC...the HYSPLIT wrapper should trap for this so avoid silent truncation
        #    in this case.
        #if len(files) > 12:
        #    if hours < 0:
        #        files = files[-12:]
        #    else:
        #        files = files[:12]
        
        # Return the list of files, stripping out the extra information; all
        # TrajectoryModel.writeControlFile() cares about is the file name
        return [ filename for filename, start, end, interval in files ]
    
    def appendUnique(self, files, newfiles, coverage_min, coverage_max):
        """Given a master list and a list of new files, build a new master list
        This function provides a key capability: we must be able to build
        a new master list that contains the smallest yet best list of input
        files for the model.  This function works by looping through the new
        files, and checking if any already exist in our master list.  If any
        exist, it is considered a sufficient condition, and no further work is
        performed.  Otherwise, the first option from the new list is appended
        to the master list.  This function makes the assumption that all the
        alternatives in the new files list are either completely equivalent,
        or else already sorted in order of preference.
        """
        # If the files list is empty, just return the first element from the
        # newfiles list
        if not files:
            return [ newfiles[0] ]
        
        # Loop through the options
        for f in newfiles:
            # Do we already have this one in our list?
            if f in files:
                # Then we don't need to do anything; our current list
                # already contains the file
                return files
            
        # OK, we didn't find a matching file in our existing list, so
        # we need to add one.  We need to choose the file with the least
        # overlap with any existing files.
        
        # Find out how much new coverage each candidate file would add
        newcoverage = [ max( coverage_min - start, end - coverage_max ) 
                        for filename, start, end, interval in newfiles ]
        # The maximum value is what we're going to add
        addhours = max(newcoverage)
        # Find the files tuple that matches the max() value that we
        # just calculated
        idx = [ i for i, x in enumerate(newcoverage) if x == addhours ][0]
        
        # Append the selected candidate and return the files list
        return files + [ newfiles[idx] ]
       
    def getSingleHourIntervals( self, dt, hours ):
        """Find the hour intervals needing input data
        Given a datetime and a range of hours, this function calculates every
        1-hr interval between the datetime and the endpoint.
        """
        # Truncate the starting date to hour accuracy
        dt = dt.replace(minute=0, second=0, microsecond=0)
        step = hours < 0 and -1 or 1
        #hour_range = sorted( range( 0, hours, step ) + [hours] )
        hour_range = range( 0, hours, step ) + [hours]
        return [ dt + datetime.timedelta(hours=h) for h in hour_range ]
        
    def getArchiveFiles( self, dt ):
        """Find the name of the archive file for a given date
        Without querying the file system, this function constructs a path to
        the ARL EDAS archive data file that would contain the given date.
        """
        filename = dt.strftime( r"%Y/edas.%b%y.00" ).lower()  # KJC fixed for unix environment
        last_day_of_month = calendar.monthrange( dt.year, dt.month )[1]
            
        # Construct the filename and date range contained in this file
        if dt.day < 16:
            filename += "1"
            start = datetime.datetime( dt.year, dt.month, 1, 0 )
            end = datetime.datetime( dt.year, dt.month, 15, 21 )
        else:
            filename += "2"
            start = datetime.datetime( dt.year, dt.month, 16, 0 )
            end = datetime.datetime( dt.year, dt.month, last_day_of_month, 21 )

        # Build the archive_file tuple to go into our master files list
        archive_file = [( os.path.join(self.historicalDataPath, filename), start, end, 3 )]

        if dt.day in (15, last_day_of_month) and dt.hour >= 21:
            # If we're in the gap between files, make sure to pass in both
            # the file before and after the given datetime
            archive_file += self.getArchiveFiles( dt + datetime.timedelta(1) )
        
        return archive_file

    def getDataIndex( self ):
        """Read the arlindex.txt file to determine what data are available"""
        # KJC modified to ignore file paths in the arlindex file and use 
        # self.dataPath instead.

        csvfile = self.arlindex
        f = open( csvfile )
        headers = f.readline()
        index = []
        for line in f:
            s = line.split(',')
            if "\\" in s[0]:
                filename = s[0].split('\\')[-1] # DOS way
            else:
                filename = s[0].split('/')[-1] # UNIX way
            t = ( os.path.join(self.dataPath,filename), parseDate(s[1]), parseDate(s[2]), int(s[3]) )
            index.append( t )
        f.close()
        return index
