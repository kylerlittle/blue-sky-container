
from datetime import timedelta
import re

# Constants
OUTPUT_DATE_FORMAT = '%A, %B %d, %Y'

MAX_FCCS_ROWS = 5

def build_fire_location_description(fire_location):
    date_str = fire_location.start_date_time.strftime(OUTPUT_DATE_FORMAT).replace(' 0', ' ')
    body = """
        <h2 class="fire_title">
            {date}
        </h2>
        <div class="section">
            Anticipated Type: {fire_type}
        </div>
    """.format(date=date_str, fire_type=fire_location.fire_type)

    if fire_location.fccs_number:
        body += '<div class="section">FCCS #{fccs_number}</div>'.format(
            fccs_number=fire_location.fccs_number)

    return _build_description(body)

UNNAMED_MATCHER = re.compile('^Unnamed fire')

def build_fire_event_description(fire_event):
    start_str = fire_event.start_date_time.strftime(OUTPUT_DATE_FORMAT).replace(' 0', ' ')
    end_str = fire_event.end_date_time.strftime(OUTPUT_DATE_FORMAT).replace(' 0', ' ')
    name = UNNAMED_MATCHER.sub('Satellite Hotspot Detection(s)*', fire_event.name)
    body = """
        <h2 class="fire_title">
            {fire_name}
        </h2>
        <div class="section">
            <span class="header">Anticipated Type</span>: {fire_type}
        </div>
    """.format(fire_name=name, fire_type=fire_event.fire_type)
    body += _build_projected_growth_section(fire_event)
    body += _build_fuelbeds(fire_event)
    body += _build_emissions(fire_event)
    body += _build_disclaimer()
    return _build_description(body)

def _build_projected_growth_section(fire_event):
    # create "daily" summary boxes
    growth = []
    for date in _daterange(fire_event.start_date_time, fire_event.end_date_time):
        # This assumes that fire_event.[daily_area|daily_num_locations|
        # daily_emissions|daily_stats_by_fccs_num] have the same set of keys
        # (i.e. that each is defined for the same set of dates)
        if (not fire_event.daily_area.has_key(date)):
            continue

        date_str = date.strftime(OUTPUT_DATE_FORMAT).replace(' 0', ' ')
        growth.append("""
            <div class="item">
                {date}: {day_area:,} acres ({day_num_locations} location{plural_s})
            </div>
        """.format(
            date=date_str, day_area=int(fire_event.daily_area[date]),
            day_num_locations=fire_event.daily_num_locations[date],
            plural_s='s' if fire_event.daily_num_locations[date] > 1 else ''))
    if growth:
        return _convert_single_line("""
            <div class="section">
                <div class="header">Modeled Growth (based on persistence)</div>
                <div class="list">{growth}</div>
            </div>
        """.format(growth=''.join(growth)))
    return ""

def _build_fuelbeds(fire_event):
    fccs_stats = {}
    for day, daily_stats in fire_event.daily_stats_by_fccs_num.items():
        for fccs_num, fccs_dict in daily_stats.items():
            fccs_stats[fccs_num] = fccs_stats.get(fccs_num,
                {'total_area': 0.0, 'description': fccs_dict['description']})
            fccs_stats[fccs_num]['total_area'] += fccs_dict['total_area']

    if len(fccs_stats) > 0:
        fuelbeds = []
        sorted_stats = sorted(fccs_stats.items(), key=lambda e: -e[1]['total_area'])
        sorted_stats = sorted_stats[:MAX_FCCS_ROWS]
        days = len(fire_event.daily_stats_by_fccs_num)
        for fccs_num, fccs_dict in sorted_stats:
            fuelbeds.append(
                '<div class="item">'
                '<span class="fccs-num">#{fccs_num}</span> - '
                '<span class="fccs-area">{area:,} acres</span> - '
                '<span class="fccs-desc">{desc}</span>'
                '</div>'.format(
                area=int(fccs_dict['total_area'] / days), fccs_num=fccs_num,
                desc=fccs_dict['description']))
        return _convert_single_line("""
            <div class="section">
                <div class="header">FCCS Fuelbeds</div>
                <div class="list">{fuelbeds}</div>
            </div>
        """.format(fuelbeds=''.join(fuelbeds)))
    return ""

EMISSIONS_SPECIES = {
    'pm25': 'PM2.5',
    'pm10': 'PM10'
}
"""Emissions species to include in fire popups. The keys in EMISSIONS_SPECIES
are the keys in the emissions dict; the values are the 'pretty' names."""

def _build_emissions(fire_event):
    species = {}
    for key, name in EMISSIONS_SPECIES.items():
        for day in fire_event.daily_emissions:
            value = fire_event.daily_emissions[day].get(key)
            if value:
                species[name] = species.get(name, 0.0) + value

    if species:
        days = len(fire_event.daily_emissions)
        # Note: for now, we're hardcoding 'tons', since that's the unit
        # for all emissions listed in the popup.  This could change.
        template = """
            <div class="item">
                {name}: {value} tons
            </div>
        """
        species_divs = [
            template.format(name=n, value=v / days) for n,v in species.items()
        ]
        return _convert_single_line("""
            <div class="section">
                <div class="header">Modeled Daily Emissions</div>
                <div class="list">{species}</div>
            </div>
        """.format(species=''.join(species_divs)))
    return ""

def _build_disclaimer():
    return _convert_single_line("""
        <div class="disclaimer">
            *Modeled fire information is derived in part from satellite
            hotspot detections and other sources that can contain false
            detections and other errors.  Modeled fire information is
            provided here only to show what information was used within
            the smoke model run.
        </div>
    """)


def _build_description(body):
    description = """<html lang="en">
        <head>
            <meta charset="utf-8"/>
            <style>
                * {{
                    text-align: left;
                    background: #ffffff;
                    margin: 0;
                }}
                html, body {{
                    height: 100%;
                    margin: 0;
                    padding: 0;
                }}
                .summary {{
                    font-family: 'Helvetica Neue', Arial, Helvetica, sans-serif;
                    font-size: 12px;
                    width: 350px;
                    padding-bottom: 15px;
                }}
                .summary .fire_title {{
                    margin-bottom: 5px;
                }}
                .summary .section {{
                    margin: 0 0 10px 10px;
                }}
                .summary .section .header {{
                    font-weight: bold;
                }}
                .summary .section .list {{
                    margin-left: 5px;
                }}
                .summary .disclaimer {{
                    font-style: italic;
                }}
            </style>
        </head>
        <body>
            <div class="summary">
                {body}
            </div>
        </body>
    </html>
    """.format(body=body)
    return _convert_single_line(description)

def _daterange(start_date, end_date):
    for n in range(int((end_date - start_date).days)+1):
        yield start_date + timedelta(n)

def _convert_single_line(description):
    """Reduce description text to single line to help reduce kml file size."""
    description = description.replace('\n', '')  # Remove new line characters
    description = re.sub(' +', ' ', description)  # Reduce multiple spaces into a single space
    return description.strip()
