#
# tracker.py
#
# kevinabrandon@gmail.com
#

import sys
import traceback
import time
from time import sleep
from twitter import *
import flightdata
import screenshot
from configparser import ConfigParser
from string import Template
import geomath
import fa_api

# Read the configuration file for this application.
parser = ConfigParser()
parser.read('config.ini')

# Assign AboveTustin variables.
abovetustin_distance_alarm = int(parser.get('abovetustin', 'distance_alarm'))	# The alarm distance in miles.
abovetustin_elevation_alarm = int(parser.get('abovetustin', 'elevation_alarm'))	# The angle in degrees that indicates if the airplane is overhead or not.
abovetustin_wait_x_updates = int(parser.get('abovetustin', 'wait_x_updates'))	# Number of updates to wait after the airplane has left the alarm zone before tweeting.
abovetustin_sleep_time = float(parser.get('abovetustin', 'sleep_time'))		# Time between each loop.

# Assign FlightAware variables.
fa_enable = parser.getboolean('flightaware', 'fa_enable')
fa_username = parser.get('flightaware', 'fa_username')
fa_api_key = parser.get('flightaware', 'fa_api_key')

# Assign Twitter variables.
twitter_consumer_key = parser.get('twitter', 'consumer_key')
twitter_consumer_secret = parser.get('twitter', 'consumer_secret')
twitter_access_token = parser.get('twitter', 'access_token')
twitter_access_token_secret = parser.get('twitter', 'access_token_secret')

# Login to twitter.
twit = Twitter(auth=(OAuth(twitter_access_token, twitter_access_token_secret, twitter_consumer_key, twitter_consumer_secret)))

# Given an aircraft 'a' tweet.  
# If we have a screenshot, upload it to twitter with the tweet.
def Tweet(a, havescreenshot):
	# compile the template arguments
	templateArgs = dict()
	templateArgs['flight'] = a.flight
	if templateArgs['flight'] == 'N/A':
		templateArgs['flight'] = a.hex
	templateArgs['flight'] = templateArgs['flight'].replace(" ", "")
	templateArgs['icao'] = a.hex
	templateArgs['icao'] = templateArgs['icao'].replace(" ", "")
	templateArgs['dist_mi'] = "%.1f" % a.distance
	templateArgs['dist_km'] = "%.1f" % geomath.mi2km(a.distance)
	templateArgs['dist_nm'] = "%.1f" % geomath.mi2nm(a.distance)
	templateArgs['alt_ft'] = a.altitude
	templateArgs['alt_m'] = "%.1f" % geomath.ft2m(a.altitude)
	templateArgs['el'] = "%.1f" % a.el
	templateArgs['az'] = "%.1f" % a.az
	templateArgs['heading'] = geomath.HeadingStr(a.track)
	templateArgs['speed_mph'] = "%.1f" % a.speed
	templateArgs['speed_kmph'] = "%.1f" % geomath.mi2km(a.speed)
	templateArgs['speed_kts'] = "%.1f" % geomath.mi2nm(a.speed)
	templateArgs['time'] = a.time.strftime('%H:%M:%S')
	templateArgs['squawk'] = a.squawk
	templateArgs['vert_rate_ftpm'] = a.vert_rate
	templateArgs['vert_rate_mpm'] = "%.1f" % geomath.ft2m(a.vert_rate)
	templateArgs['rssi'] = a.rssi
	if fa_enable and faInfo:
		templateArgs['orig_name'] = faInfo['orig_name']
		templateArgs['dest_name'] = faInfo['dest_name']
		if faInfo['orig_alt']:
			templateArgs['orig_alt'] = faInfo['orig_alt']
		else:
			templateArgs['orig_alt'] = faInfo['orig_code']
		if faInfo['dest_alt']:
			templateArgs['dest_alt'] = faInfo['dest_alt']
		else:
			templateArgs['dest_alt'] = faInfo['dest_code']
		if faInfo['dest_city']:
			templateArgs['dest_city'] = faInfo['dest_city']
		if faInfo['orig_city']:
			templateArgs['orig_city'] = faInfo['orig_city']
		if templateArgs['orig_alt'] and templateArgs['dest_alt']:
			tweet = Template(parser.get('tweet', 'fa_tweet_template')).substitute(templateArgs)
		else:
			tweet = Template(parser.get('tweet', 'tweet_template')).substitute(templateArgs)
	else:
		tweet = Template(parser.get('tweet', 'tweet_template')).substitute(templateArgs)
	#conditional hashtags:
	hashtags = []
	if a.time.hour < 7 or a.time.hour >= 23 or (a.time.weekday() == 7 and a.time.hour < 8):
		hashtags.append(" #AfterHours")
	if a.altitude < 1000:
		hashtags.append(" #2CloseForComfort")
	if a.altitude >= 1000 and a.altitude < 2500 and (templateArgs['heading'] == "S" or templateArgs['heading'] == "SW"):
		hashtags.append(" #ProbablyLanding")
	if a.altitude > 20000 and a.altitude < 35000:
		hashtags.append(" #UpInTheClouds")
	if a.altitude >= 35000:
		hashtags.append(" #WayTheHeckUpThere")
	if a.speed > 300 and a.speed < 500:
		hashtags.append(" #MovingQuickly")
	if a.speed >= 500 and a.speed < 770:
		hashtags.append(" #FlyingFast")
	if a.speed >= 700:
		hashtags.append(" #SpeedDemon")

	# add the conditional hashtags as long as there is room in 140 chars
	for hash in hashtags: 
		if len(tweet) + len(hash) <= 280:
			tweet += hash

	# add the default hashtags as long as there is room
	for hash in parser.get('tweet', 'default_hashtags').split(' '):
		if len(tweet) + len(hash) <= 279:
			tweet += " " + hash

	# send tweet to twitter!
	if havescreenshot:
		with open('tweet.png', "rb") as imagefile:
			imagedata = imagefile.read()
		params = {"media[]": imagedata, "status": tweet}
		twit.statuses.update_with_media(**params)
	else:
		twit.statuses.update(status=tweet)

	# send the tweet to stdout while we're at it
	print(tweet)

if __name__ == "__main__":

	lastReloadTime = time.time()
	browser = screenshot.loadmap()
	if browser == None:
		print("unable to load browser!")
	else:
		print("browser loaded!")

	alarms = dict() # dictonary of all aircraft that have triggered the alarm
			# Indexed by it's hex code, each entry contains a tuple of
			# the aircraft data at the closest position so far, and a 
			# counter.  Once the airplane is out of the alarm zone,
			# the counter is incremented until we hit [abovetustin_wait_x_updates]
			# (defined above), at which point we then Tweet

	fd = flightdata.FlightData()
	lastTime = fd.time

	while True:
		if time.time() > lastReloadTime + 3600 and len(alarms) == 0:
			print("one hour since last browser reload... reloading now")
			if browser != None:
				browser.quit()
			browser = screenshot.loadmap()
			lastReloadTime = time.time()

		sleep(abovetustin_sleep_time)
		fd.refresh()
		if fd.time == lastTime:
			continue
		lastTime = fd.time

		print("Now: {}".format(fd.time))

		current = dict() # current aircraft inside alarm zone

		# loop on all the aircarft in the receiver
		for a in fd.aircraft:
			# if they don't have lat/lon or a heading skip them
			if a.lat == None or a.lon == None or a.track == None:
				continue

			# check to see if it's in the alarm zone:
			if a.distance < abovetustin_distance_alarm or a.el > abovetustin_elevation_alarm:

				# add it to the current dictionary
				current[a.hex] = a 

				print("{}/{}: {}mi, {}az, {}el, {}alt, {}dB, {}seen".format(
					a.hex, a.flight, "%.1f" % a.distance, "%.1f" % a.az, "%.1f" % a.el,
					a.altitude, "%0.1f" % a.rssi, "%.1f" % a.seen))

				if a.hex in alarms:
					#if it's already in the alarms dict, check to see if we're closer
					if a.distance < alarms[a.hex][0].distance:
						#if we're closer than the one already there, then overwrite it
						alarms[a.hex] = (a, 0)
				else:
					#add it to the alarms
					alarms[a.hex] = (a, 0)

		finishedalarms = []
		# loop on all the aircraft in the alarms dict
		for h, a in alarms.items():
			found = False
			# check to see if it's in the current set of aircraft
			for h2, a2 in current.items():
				if h2 == h:
					print("{} not yet, dist, elv: {}, {}".format(h, "%.1f" % a[0].distance, "%.1f" % a[0].el))
					found = True
					break
			# if it wasn't in the current set of aircraft, that means it's time to tweet!
			if not found:
				if a[1] < abovetustin_wait_x_updates:
					alarms[h] = (a[0], a[1]+1)
				else:				
					havescreenshot = False
					if browser != None:
						print("time to create screenshot:")
						hexcode = a[0].hex
						hexcode = hexcode.replace(" ", "")
						hexcode = hexcode.replace("~", "")

						havescreenshot = screenshot.clickOnAirplane(browser, hexcode)

					if fa_enable:
						print("Getting FlightAware flight details")
						faInfo = fa_api.FlightInfo(a[0].flight, fa_username, fa_api_key)
					else:
						faInfo = False

					print("time to tweet!!!!!")
					
					try:
						Tweet(a[0], havescreenshot)
					except Exception:
						print("exception in Tweet():")
						traceback.print_exc()
					finishedalarms.append(a[0].hex)
		
		# for each alarm that is finished, delete it from the dictionary
		for h in finishedalarms:
			del(alarms[h])

		# flush output for following in log file
		sys.stdout.flush()
