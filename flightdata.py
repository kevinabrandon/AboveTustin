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


from urllib.request import urlopen
import json
from time import sleep
import geomath
import math
from datetime import datetime
from dateutil import tz
from configparser import ConfigParser

# Read the configuration file for this application.
parser = ConfigParser()
parser.read('config.ini')

# Assign dump1090 variables.
dump1090_data_url = parser.get('dump1090', 'data_url')

# Assign receiver variables.
receiver_latitude = float(parser.get('receiver', 'latitude'))
receiver_longitude = float(parser.get('receiver', 'longitude'))
receiver_time_zone = tz.gettz(parser.get('receiver', 'time_zone'))

# Other variables used by this script.
utc_time_zone = tz.gettz('UTC')

class FlightData():
    def __init__(self, data_url = dump1090_data_url):

        self.data_url = data_url
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

            #get time from json and convert to our time zone
            self.time = datetime.fromtimestamp(self.json_data["now"])
            self.time = self.time.replace(tzinfo=utc_time_zone)
            self.time = self.time.astimezone(receiver_time_zone)

            #load all the aircarft
            self.aircraft = AirCraftData.parse_flightdata_json(self.json_data, self.time)

        except:
            print("exception in FlightData.refresh()")
            import sys
            print (sys.exc_info()[0])

class AirCraftData():
    def __init__(self,
                 dhex,
                 squawk,
                 flight,
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

    @staticmethod
    def parse_flightdata_json(json_data, time):
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
                a["hex"] if "hex" in a else None,
                a["squawk"] if "squawk" in a else None,
                a["flight"] if "flight" in a else "N/A",
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

