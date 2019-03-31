__all__ = [
    'TimeSeriesTypes', 'TIME_SET_DIR_NAMES', 'IMAGE_PREFIXES',
    'TIME_SERIES_PRETTY_NAMES', 'CONFIG_COLOR_LABELS',
    'FILE_NAME_TIME_STAMP_PATTERNS', 'AquiptImageTypes',
    'AQUIPT_IMAGE_PREFIXES', 'AQUIPT_IMAGE_TYPE_PRETTY_NAMES'
]

class TimeSeriesTypes:
    """Effectively an enum of image time series types"""
    # Enum to represent different time series
    NUM_TYPES = 4
    HOURLY, THREE_HOUR, DAILY_MAXIMUM, DAILY_AVERAGE = range(NUM_TYPES)
    AQUIPT = NUM_TYPES
    ALL = list(range(NUM_TYPES))  # Note that 'ALL' excludes AQUIPT
    ALL_PLUS_AQUIPT = list(range(NUM_TYPES + 1))


# Define the time set keys, used in the image paths and filenames, here rather
# than hardcode multiple times below
# TODO: make these configurable?
TIME_SET_DIR_NAMES = {
    TimeSeriesTypes.HOURLY: 'hourly',
    TimeSeriesTypes.THREE_HOUR: 'three_hour',
    TimeSeriesTypes.DAILY_MAXIMUM: 'daily_maximum',
    TimeSeriesTypes.DAILY_AVERAGE: 'daily_average',
    TimeSeriesTypes.AQUIPT: 'aquipt',
}

IMAGE_PREFIXES = dict((t, TIME_SET_DIR_NAMES[t] + '_') for t in TimeSeriesTypes.ALL)

TIME_SERIES_PRETTY_NAMES = dict(
    (t, ' '.join([d.capitalize()
    for d in TIME_SET_DIR_NAMES[t].split('_')])) for t in TimeSeriesTypes.ALL
)

CONFIG_COLOR_LABELS = {
    TimeSeriesTypes.HOURLY: 'HOURLY_COLORS',
    TimeSeriesTypes.THREE_HOUR: 'THREE_HOUR_COLORS',
    TimeSeriesTypes.DAILY_MAXIMUM: 'HOURLY_COLORS',
    TimeSeriesTypes.DAILY_AVERAGE: 'DAILY_COLORS',
    TimeSeriesTypes.AQUIPT: 'AQUIPT_COLORS'
}

FILE_NAME_TIME_STAMP_PATTERNS = {
    TimeSeriesTypes.HOURLY:     "%Y%m%d%H%M",
    TimeSeriesTypes.THREE_HOUR:     "%Y%m%d%H%M",
    TimeSeriesTypes.DAILY_MAXIMUM: "%Y%m%d",
    TimeSeriesTypes.DAILY_AVERAGE: "%Y%m%d"
}


# AQUIPT Constants
class AquiptImageTypes:
    """Effectively an enum of AQUIPT image types"""
    _RANGE = range(5)
    MAXIMPACT,AVGIMPACT,PCNTSIMS,PERCENT,TIMPACT = _RANGE
    ALL = list(_RANGE)

AQUIPT_IMAGE_PREFIXES = {
    AquiptImageTypes.MAXIMPACT: "MAXIMPACT",
    AquiptImageTypes.AVGIMPACT: "AVGIMPACT",
    AquiptImageTypes.PCNTSIMS: "PCNTSIMS",
    AquiptImageTypes.PERCENT: "PERCENT",
    AquiptImageTypes.TIMPACT: "TIMPACT"
}

AQUIPT_IMAGE_TYPE_PRETTY_NAMES = {
    AquiptImageTypes.MAXIMPACT: "Maximum Impact",
    AquiptImageTypes.AVGIMPACT: "Average Impact",
    AquiptImageTypes.PCNTSIMS: "Percent Simulations",
    AquiptImageTypes.PERCENT: "Percent Time",
    AquiptImageTypes.TIMPACT: "Time Impacts"
}