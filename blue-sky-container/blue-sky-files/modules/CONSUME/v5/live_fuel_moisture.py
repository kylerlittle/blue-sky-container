import re
import time
import sys
import os
import urllib2
import shutil
from datetime import date
from datetime import datetime
from xml.dom.minidom import parseString
from numpy import array
from numpy import argwhere
from numpy import argsort
from numpy import insert as insert
from os import path
from kernel.grid import open_grid

def process_lfm(latitude, longitude, date_time, inpath):
    """ Returns a live fuel moisture value for a given latitude, longitude, and date-time stamp of a fire object.

    This function receives a latitude (of type float), longitude (of type float), a date_time (of type string e.g.
    '2008-05-01 00:00:00-04:00'), and a path (of type string) as inputs. It uses the date_time value to choose a
    live fuel moisture file of the same season which is coincident/closest in time to the fire object from amongst the list
    of live fuel moisture files available online at http://eastfire.gmu.edu/project/. If the chosen live fuel moisture
    file does not already exist in the input path, the file is downloaded. The live fuel moisture values of all the pixels
    that are within 5 km of the input coordinates are extracted from the file. The invalid live fuel moisture values are
    removed from these values, and the remaining values averaged and returned. If the pixel corresponding to the input
    coordinates is invalid, -999 is returned instead.

    This function is dependent on the BlueSky framework because it uses the module grid from the BlueSky kernel folder.

    Written by Loayeh Jumbam, Sonoma Technology, Inc., August 2012.

    """
	
    # Extract and Validate the Date from the Input date_time String.
    try:
        Date = date_time.split(' ')[0]
        Date = datetime.strptime(Date, '%Y-%m-%d')
    except:
        print "ERROR: Invalid date stamp format"
        return -999.

    # Open the url where the live fuel moisture files reside
    try:
        url = urllib2.urlopen('http://eastfire.gmu.edu/project/')
    except:
        print "ERROR: Failed to connect to the page http://eastfire.gmu.edu/project/"
        return -999.

    # Read all elements from the url with tag name = <a> (elements that have links to data)
    html = url.read()
    dom = parseString(html)
    tags = dom.getElementsByTagName('a')

    # Close the url
    url.close()

    # Get list of files (files ending with .dat) from elements of tag <a> with an attribute of href (i.e get the attribute value)
    try:
        href = [str(a.attributes['href'].value) for a in tags if str(a.attributes['href'].value).endswith('.dat')]
    except:
        print "ERROR: There are no files in http://eastfire.gmu.edu/project/ with the extension .dat"
        return -999.

    # Convert Input Date to Julian Date (string)
    input_jdate = time.mktime((Date.year, Date.month, Date.day, 0, 0, 0, 0, 0, 0))
    input_jdate = str(time.gmtime(input_jdate)[0]) + str(time.gmtime(input_jdate)[7])

    # Get the Julian Day and the Julian Year of the input date
    input_jday = int(input_jdate[4:])
    input_jyear = int(input_jdate[0:4])

    # Get list of Julian dates from the names of files in href (i.e. dates attached to the names of the live fuel moisture files)
    jdate = [re.sub('[a-zA-Z_./]', '', jd) for jd in href]
    jdate = [d[1:] for d in jdate]

    # Get list of Julian days and Julian years from list of Julian dates of the live fuel moisture files
    jday = [int(days[4:]) for days in jdate]
    jyear = [int(years[0:4]) for years in jdate]

    # Determine which Julian date from the list of files online is the best match
    #   Get two arrays showing the absolute difference between the list of available dates, and the input dates
    day_diff = abs(input_jday - array(jday))
    year_diff = abs(input_jyear - array(jyear))

    #   Loop through the number of days in a year (by intervals of 8 days from 0 to 366). At each interval, get an array
    #   of all elements in day_diff that fall within the interval. Get indices of the numbers in this retrieved array and
    #   use the indices to retrieve the corresponding years in year_diff. Sort both retrieved arrays by the retrieved year_diff
    #   sub array. Pick the first date at the top of the arrays. Stop iteration once a date has been picked.
    interval_start = 0
    for days in range(0, 368, 8): # Up to 368 so as to include every day of year

        interval_end = days

        index_day_diff = argwhere((day_diff >= interval_start) & (day_diff < interval_end))
        sub_arr_day_diff = day_diff[index_day_diff]
        sub_arr_year_diff = year_diff[index_day_diff]
        if len(sub_arr_day_diff) == 0 | len(sub_arr_year_diff) == 0:
            continue
        index_year_diff = argsort(sub_arr_year_diff)

        for i in range(0, len(index_year_diff)):
            if (len(sub_arr_year_diff[index_year_diff[i]]) !=0) & (len(sub_arr_day_diff[index_year_diff[i]]) != 0):
                file_to_download = href[index_day_diff[index_year_diff[i]]]
                break
        try:
            file_to_download
            break
        except:
            interval_start = days

    # Download the file to the input directory, inpath, if the file doesn't arleady exist there. Also make file header
    file_name = file_to_download.replace('./', '/')
    if (path.isfile(r'' + inpath + file_name + '') == False):

        # Since file of interest does not exist, delete one of the live fuel moisture files in the directory in_path
        # to make room for a new file. Folder should hold not more than three live fuel moisture files
        lfm_files = [f for f in os.listdir(inpath) if f.endswith('.dat')]
        if len(lfm_files) >= 4:
            file_to_delete = lfm_files[len(lfm_files)-1]
            header_to_delete = file_to_delete.replace('.dat','.hdr')
            try:
                os.remove(r'' + inpath + '/' + file_to_delete + '')
                os.remove(r'' + inpath + '/' + header_to_delete + '')
            except:
                print "WARNING: Could not delete an old live fuel moisture file and/or its header."

        # Download the file
        f_url = urllib2.urlopen('http://eastfire.gmu.edu/project/' + file_to_download, 'rb')
        print "Downloading live fuel moisture file " + file_to_download
        content = f_url.read()
        in_file = open(r'' + inpath + file_name + '', 'wb')
        in_file.write(content)
        in_file.close()
        f_url.close()

        # Make a copy of a header file for the downloaded live fuel moisture file
        header_name = file_name.replace('.dat', '.hdr')
        try:
            shutil.copy2(r'' + inpath + '/LFM_Header.hdr', r'' + inpath + header_name + '')
        except:
            print "WARNING: Could not create header file. Make sure the template 'LFM_Header.hdr' exists in the input directory."

    # Open the live fuel moisture file
    grid = open_grid(inpath + file_name)

    # Get location of cell corresponding to input lat/lon
    x,y = grid.getCellByLatLon(latitude, longitude)

    # Extract the values of all 5 x 5 pixels around the cell with location x, y into an array
    pix = 5.0 # Smoothing resolution (has to be an odd number)
    arr = array([])

    if (grid.getValueAt(latitude, longitude) > 0): # First ensure that value of cell x,y is not invalid (i.e. not negative)
        for i in range(x - int((pix / 2) - 0.5), x + 1 + int((pix / 2) - 0.5)):
            for j in range(y - int((pix / 2) - 0.5), y + 1 + int((pix / 2) - 0.5)):
                # Get the value of the cell (i,j). Validate it and insert it into array
                try:
                    lat,lon = grid.getLatLonByCell(i, j)
                    value = grid.getValueAt(lat, lon)
                    # Validate value
                    if value < 0:
                        break
                    arr = insert(arr, 0, value)
                except:
                    continue
        mean_arr = arr.mean()
    else:
        mean_arr = -999.

    # Close the live fuel moisture file
    grid.close()

    return mean_arr
