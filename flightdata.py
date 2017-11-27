#
# flightdata.py
#
# This was originally pulled from here: 
# https://github.com/martinohanlon/flightdata
#
# I made changes to work with the current mutability version of dump1090 and some tweaks to the default output
# kevinabrandon@gmail.com
#
# Original LICENSE from martinohanlon:
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#


import traceback
from urllib.request import urlopen
import json
from time import sleep
import geomath
import math
from datetime import datetime
from configparser import ConfigParser

# Read the configuration file for this application.
parser = ConfigParser()
parser.read('config.ini')

# Assign receiver variables.
receiver_latitude = float(parser.get('receiver', 'latitude'))
receiver_longitude = float(parser.get('receiver', 'longitude'))

class FlightData():
    def __init__(self, data_url=None, parser=None):
        self.data_url = data_url
        self.parser = parser
        self.aircraft = None
        self.refresh()

    def refresh(self):
        try:
            #open the data url
            self.req = urlopen(self.data_url)

            #read data from the url
            self.raw_data = self.req.read()

            #load in the json
            self.json_data = json.loads(self.raw_data.decode())

            #get time from json
            self.time = datetime.fromtimestamp(self.parser.time(self.json_data))

            #load all the aircarft
            self.aircraft = self.parser.aircraft_data(self.json_data, self.time)

        except Exception:
            print("exception in FlightData.refresh():")
            traceback.print_exc()


class AirCraftData():
    def __init__(self,
                 dhex,
                 squawk,
                 flight,
                 registration,
                 lat,
                 lon,
                 altitude,
                 vert_rate,
                 track,
                 speed,
                 messages,
                 seen,
                 mlat,
                 nucp,
                 seen_pos,
                 rssi,
                 dist, 
                 az,
                 el,
                 time):
        self.hex = dhex
        self.squawk = squawk
        self.flight = flight
        self.registration = registration
        self.lat = lat
        self.lon = lon
        self.altitude = altitude
        self.vert_rate = vert_rate
        self.track = track
        self.speed = speed
        self.messages = messages
        self.seen = seen
        self.mlat = mlat
        self.nucp = nucp
        self.seen_pos = seen_pos
        self.rssi = rssi
        self.distance = dist
        self.az = az
        self.el = el
        self.time = time

    def __str__(self):
        return '<{} {} dist={} el={}>'.format(
            self.__class__.__name__,
            self.ident_desc(),
            self.distance,
            self.el)

    def ident_desc(self):
        idents = [self.hex, self.registration]
        if self.flight != self.registration:
            idents.append(self.flight)
        idents = [i for i in idents if i]
        return '/'.join(idents)

class AircraftDataParser(object):
    def __init__(self):
        pass

    def aircraft_data(self, json_data, time):
        raise NotImplementedError

    def time(self, json_data):
        raise NotImplementedError


class VRSDataParser(AircraftDataParser):
    def _parse_aircraft_data(self, a, time):
        alt = a.get('Alt', 0)
        dist = -1
        az = 0
        el = 0
        if 'Lat' in a and 'Long' in a:
            rec_pos = (receiver_latitude, receiver_longitude)
            ac_pos = (a['Lat'], a['Long'])
            dist = geomath.distance(rec_pos, ac_pos)
            az = geomath.bearing(rec_pos, ac_pos)
            el = math.degrees(math.atan(alt / (dist * 5280)))
        speed = 0
        if 'Spd' in a:
            speed = geomath.knot2mph(a['Spd'])
        if 'PosTime' in a:
            last_seen_time = datetime.fromtimestamp(a['PosTime'] / 1000.0)
            seen = (time - last_seen_time).total_seconds()
        else:
            seen = 0
        ac_data = AirCraftData(
            a.get('Icao', None).upper(),
            a.get('Sqk', None),
            a.get('Call', None),
            a.get('Reg', None),
            a.get('Lat', None),
            a.get('Long', None),
            alt,
            a.get('Vsi', 0),
            a.get('Trak', None),
            speed,
            a.get('CMsgs', None),
            seen,
            a.get('Mlat', False),
            None,  # NUCP
            None,  # Seen pos
            10.0 * math.log10(a.get('Sig', 0) / 255.0 + 1e-5),
            dist,
            az,
            el,
            time)
        return ac_data

    def aircraft_data(self, json_data, time):
        aircraft_list = [self._parse_aircraft_data(d, time) for d in json_data['acList']]
        return aircraft_list

    def time(self, json_data):
        return json_data['stm'] / 1000.0


class Dump1090DataParser(AircraftDataParser):
    def aircraft_data(self, json_data, time):
        aircraft_list = []
        for a in json_data["aircraft"]:

            alt = a["altitude"] if "altitude" in a else 0
            if alt == "ground":
                alt = 0
            dist = -1
            az = 0
            el = 0
            if "lat" in a and "lon" in a:
                dist = geomath.distance((receiver_latitude, receiver_longitude), (a["lat"], a["lon"]))
                az = geomath.bearing((receiver_latitude, receiver_longitude), (a["lat"], a["lon"]))
                el = math.degrees(math.atan(alt / (dist*5280)))
            speed = 0
            if "speed" in a:
                speed = geomath.knot2mph(a["speed"])

            aircraftdata = AirCraftData(
                a["hex"].upper() if "hex" in a else None,
                a["squawk"] if "squawk" in a else None,
                a["flight"] if "flight" in a else None,
                None,
                a["lat"] if "lat" in a else None,
                a["lon"] if "lon" in a else None,
                alt,
                a["vert_rate"] if "vert_rate" in a else 0,
                a["track"] if "track" in a else None,
                speed,
                a["messages"] if "messages" in a else None,
                a["seen"] if "seen" in a else None,
                a["mlat"] if "mlat" in a else None,
                a["nucp"] if "nucp" in a else None,
                a["seen_pos"] if "seen_pos" in a else None,
                a["rssi"] if "rssi" in a else None,
                dist,
                az,
                el,
                time)

            aircraft_list.append(aircraftdata)
        return aircraft_list

    def time(self, json_data):
        return json_data['now']


if __name__ == "__main__":
    import os

    flightdata = FlightData()
    while True:
        os.system('clear')
        print("Now: {}".format(flightdata.time.strftime('%Y-%m-%d %H:%M:%S')))
        print("|  icao   | flight  | miles |   az  |  el  |  alt  | mi/h  | vert  | rssi  | mesgs | seen |")
        print("|---------+---------+-------+-------+------+-------+-------+-------+-------+-------+------|")
        sortedlist = []
        for a in flightdata.aircraft:
            if a.lat == None or a.lon == None:
                continue
            sortedlist.append(a)
        
        sortedlist.sort(key=lambda x: x.distance) # actually do the sorting here

        for a in sortedlist:
            print("| {:<7} | {:^8}| {:>5} | {:>5} | {:>4} | {:>5} | {:>5} | {:>+5} | {:>5} | {:>5} | {:>4} |".format(
                a.hex, 
                a.flight, 
                "%.1f" % a.distance,
                "%.1f" % a.az,
                "%.1f" % a.el,
                a.altitude, 
                "%.1f" % a.speed,
                a.vert_rate,
                "%0.1f" % a.rssi,
                a.messages,
                "%.1f" % a.seen))
        sleep(0.5)
        flightdata.refresh()

