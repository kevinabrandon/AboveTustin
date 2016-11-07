#
# tracker.py
#
# kevinabrandon@gmail.com
#

import sys
from time import sleep
from twitter import *
import flightdata
import screenshot

distanceAlarm = 1 	# the alarm distance in miles.
elevationAlarm = 50 # the angle in degrees that indicates if the airplane is overhead or not.
nCoast = 5			# number of updates to wait after the airplane has left the alarm zone before tweeting.
sleepTime = 0.5 	# time between each loop.

# simple routine to read in the key files
def loadKeyFile(name):
	with open(name, 'r') as keyfile:
		return keyfile.read()

# read all 4 key files and login to twitter
token = loadKeyFile('keys/token')
token_secret = loadKeyFile('keys/token_secret')
consumer_key = loadKeyFile('keys/consumer_key')
consumer_secret = loadKeyFile('keys/consumer_secret')
twit = Twitter(auth=(OAuth(token, token_secret, consumer_key, consumer_secret)))

# Given an aircraft 'a' tweet.  
# If we have a screenshot, upload it to twitter with the tweet.
def Tweet(a, havescreenshot):
	# find the direction the airplane is heading
	direction = "?"
	if a.track != None:
		if a.track < 22.5 or a.track >= 337.5:
			direction = "N"
		elif a.track >=22.5 and a.track < 67.5:
			direction = "NE"
		elif a.track >= 67.5 and a.track < 112.5:
			direction = "E"
		elif a.track >= 112.5 and a.track < 157.5:
			direction = "SE"
		elif a.track >= 157.5 and a.track < 202.5:
			direction = "S"
		elif a.track >= 202.5 and a.track < 247.5:
			direction = "SW"
		elif a.track >= 247.5 and a.track < 292.5:
			direction = "W"
		elif a.track >= 292.5 and a.track < 337.5:
			direction = "NW"

	#conditional hashtags:
	hashtags = []
	if a.time.hour < 7 or a.time.hour >= 23 or (a.time.weekday() == 7 and a.time.hour < 8):
		hashtags.append(" #AfterHours")
	if a.altitude < 1000:
		hashtags.append(" #2CloseForComfort")
	if a.altitude >= 1000 and a.altitude < 2500 and (direction == "S" or direction == "SW"):
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
	hashtags.append(" #AboveTustin")
	hashtags.append(" #RaspberryPi")
	hashtags.append(" #ADSB")
	hashtags.append(" #dump1090")

	#use the flight number if we have it, otherwise use the hex code
	flight = a.flight
	if flight == 'N/A':
		flight = h
	flight = flight.replace(" ", "")

	# create the text part of the tweet
	tweet = "{}:{}mi away @ {}ft and {}° frm hrzn, heading {}@ {}mi/h {}.".format(
		flight,
		"%.1f" % a.distance,
		a.altitude,
		"%.1f" % a.el,
		direction,
		"%.1f" % a.speed,
		a.time.strftime('%H:%M:%S')
		)

	# add the hashtag as long as there is room in 140 chars
	for hash in hashtags: 
		if len(tweet) + len(hash) <= 140: 
			tweet += hash

	# send tweet to twitter!
	if havescreenshot:
		with open('/home/pi/AboveTustin/tweet.png', "rb") as imagefile:
			imagedata = imagefile.read()
		params = {"media[]": imagedata, "status": tweet}
		twit.statuses.update_with_media(**params)
	else:
		twit.statuses.update(status=tweet)

	# send the tweet to stdout while we're at it
	print(tweet)


if __name__ == "__main__":

	browser = screenshot.loadmap()
	if browser == None:
		print("unable to load browser!")
	else:
		print("browser loaded!")

	alarms = dict() # dictonary of all aircraft that have triggered the alarm
	                # Indexed by it's hex code, each entry contains a tuple of
			# the aircraft data at the closest position so far, and a 
			# counter.  Once the airplane is out of the alarm zone,
			# the counter is incremented until we hit [nCoast] (defined
			# above), at which point we then Tweet

	fd = flightdata.FlightData()
	lastTime = fd.time

	while True:
		sleep(sleepTime)
		fd.refresh()
		if fd.time == lastTime:
			continue
		lastTime = fd.time

		print("Now: {}".format(fd.time))

		current = dict() # current aircraft inside alarm zone

		# loop on all the aircarft in the receiver
		for a in fd.aircraft:
			# if they don't have lat/lon skip them
			if a.lat == None or a.lon == None: 
				continue

			# check to see if it's in the alarm zone:
			if a.distance < distanceAlarm or a.el > elevationAlarm:

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
				if a[1] < nCoast:
					alarms[h] = (a[0], a[1]+1)
				else:				
					havescreenshot = False
					if browser != None:
						print("time to create screenshot:")
						hexcode = a[0].hex
						hexcode = hexcode.replace(" ", "")
						hexcode = hexcode.replace("~", "")

						havescreenshot = screenshot.clickOnAirplane(browser, hexcode)

					print("time to tweet!!!!!")
					

					Tweet(a[0], havescreenshot)

					finishedalarms.append(a[0].hex)
		
		# for each alarm that is finished, delete it from the dictionary
		for h in finishedalarms:
			del(alarms[h])

		# flush output for following in log file
		sys.stdout.flush()
