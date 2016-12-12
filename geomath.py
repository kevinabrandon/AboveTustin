#
# geomath.py
#
# some geo coordinate math that I found on the internet
#
# kevinabrandon@gmail.com
#

import math

def HeadingStr(heading):
	"""
	Gives a heading string given the heading float
	"""
	headstr = "?"
	if heading != None:
		if heading < 22.5 or heading >= 337.5:
			headstr = "N"
		elif heading >=22.5 and heading < 67.5:
			headstr = "NE"
		elif heading >= 67.5 and heading < 112.5:
			headstr = "E"
		elif heading >= 112.5 and heading < 157.5:
			headstr = "SE"
		elif heading >= 157.5 and heading < 202.5:
			headstr = "S"
		elif heading >= 202.5 and heading < 247.5:
			headstr = "SW"
		elif heading >= 247.5 and heading < 292.5:
			headstr = "W"
		elif heading >= 292.5 and heading < 337.5:
			headstr = "NW"
	return headstr


def knot2mph(k):
	"""
	Converts knots to miles per hour.
	"""
	if k == None:
		return None
	return k * 1.15078


def distance(pointA, pointB):
	"""
	Calculate the great circle distance between two points 
	on the earth (specified in decimal degrees)

	http://stackoverflow.com/questions/15736995/how-can-i-quickly-estimate-the-distance-between-two-latitude-longitude-points
	"""
	# convert decimal degrees to radians 
	lon1, lat1, lon2, lat2 = map(math.radians, [pointA[1], pointA[0], pointB[1], pointB[0]])

	# haversine formula 
	dlon = lon2 - lon1 
	dlat = lat2 - lat1 
	a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
	c = 2 * math.asin(math.sqrt(a)) 
	r = 3956  # Radius of earth in miles. Use 6371 for kilometers
	return c * r

def bearing(pointA, pointB):
	"""
	Calculates the bearing between two points.

	Found here: https://gist.github.com/jeromer/2005586

	The formulae used is the following:
	    θ = atan2(sin(Δlong).cos(lat2),
	              cos(lat1).sin(lat2) − sin(lat1).cos(lat2).cos(Δlong))

	:Parameters:
	  - `pointA: The tuple representing the latitude/longitude for the
	    first point. Latitude and longitude must be in decimal degrees
	  - `pointB: The tuple representing the latitude/longitude for the
	    second point. Latitude and longitude must be in decimal degrees

	:Returns:
	  The bearing in degrees

	:Returns Type:
	  float
	"""
	if (type(pointA) != tuple) or (type(pointB) != tuple):
		raise TypeError("Only tuples are supported as arguments")

	lat1 = math.radians(pointA[0])
	lat2 = math.radians(pointB[0])

	diffLong = math.radians(pointB[1] - pointA[1])

	x = math.sin(diffLong) * math.cos(lat2)
	y = math.cos(lat1) * math.sin(lat2) - (math.sin(lat1) 
		* math.cos(lat2) * math.cos(diffLong))

	initial_bearing = math.atan2(x, y)

	# Now we have the initial bearing but math.atan2 return values
	# from -180° to + 180° which is not what we want for a compass bearing
	# The solution is to normalize the initial bearing as shown below
	initial_bearing = math.degrees(initial_bearing)
	compass_bearing = (initial_bearing + 360) % 360

	return compass_bearing
