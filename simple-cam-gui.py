#
# simple-cam-gui.py
#
# The is a little program that displays the output of a webcam or ipcamera and
# overlays information whenever an airplane flys into view.
#
# It includes several trackbars used for setting the fov and orientation of the
# camera.  The intention is to use this program for calibrating a fixed camera.
#
# Jan 2017 - KAB - kevinabrandon@gmail.com
#

import numpy as np
import cv2
from configparser import ConfigParser
import flightdata

print("Press 'q' to quit")

# first read in the config file and load the variables
config = ConfigParser()
config.read('config.ini')

# get the cam_url, first try to get an integer (webcam)
try:
	cam_url = config.getint('simple-cam', 'cam_url')
	print('Using webcam %d' % (cam_url))
except:
	#if not an integer, then it is either the picam or an IP camera:
	cam_url = config.get('simple-cam', 'cam_url')
	if(cam_url == 'picam'):
		print("Using picam, unfortunately this isn't implemented yet.")
	else:
		print('Using IP Cam: ' + cam_url)

# read the field of view info from the config file.
cam_horz = config.getfloat('simple-cam', 'cam_horz')
cam_vert = config.getfloat('simple-cam', 'cam_vert')
cam_fov = (cam_horz, cam_vert)
print('Field of view: %.1f°x%.1f°' % cam_fov)

# read the orientation info from the config file.
cam_az = config.getfloat('simple-cam', 'cam_az')
cam_el = config.getfloat('simple-cam', 'cam_el')
cam_orient = (cam_az, cam_el)
print('orientation: %.1f°x%.1f°' % cam_orient)

# read the time between flight data updates
time_between_updates = config.getfloat('abovetustin', 'sleep_time')

# a dummy function that does nothing
def nothing(jnk):
	pass

# returns the number of seconds since between the ticks
def time_since(old_tick, new_tick):
	return (new_tick - old_tick) / cv2.getTickFrequency()

# returns true if the aircraft is in the field of view of the aircraft
def is_aircraft_in_fov(a, fov, orient):
	az = orient[0]
	el = orient[1]
	horz = fov[0]
	vert = fov[1]

	az_diff = (az - a.az + 900) % 360 - 180
	el_diff = (el - a.el + 900) % 360 - 180

	if abs(az_diff) > az + horz/2:
		return False
	if abs(el_diff) > el + vert/2:
		return False

	return True

# Return the point on an image of a target at the location loc (az,el) +/- 180°
# given a feild of view fov (horiz,vert), and an image size (w, h)
def get_target_point(loc, fov, size):
	x = size[0] *(loc[0] / fov[0]/2 + 0.5)
	y = size[1] *(-loc[1] / fov[1]/2 + 0.5)
	return (x,y)
def get_target_point_int(loc, fov, size):
	xy = get_target_point(loc, fov, size)
	return (int(xy[0]), int(xy[1]))

# gets the size of the cirlce to display for the aircraft
def size_of_radius(a):
	max_radius = 1
	min_radius = 30
	max_distance = 100
	min_distance = 1
	d = a.distance
	if d > max_distance:
		d = max_distance
	if d < min_distance:
		d = min_distance
	norm_distance = (d - min_distance)/(max_distance - min_distance)
	radius = norm_distance * (max_radius - min_radius) + min_radius
	return int(radius)

#some consts values we'll be using
green = (0, 255, 0)
font = cv2.FONT_HERSHEY_SIMPLEX
font_sz = 0.33

# create the named window and the trackbars...
winName = 'AboveTustin'
cv2.namedWindow(winName)
cv2.createTrackbar('fov_horz', winName, int(cam_horz), 180, nothing)
cv2.createTrackbar('fov_vert', winName, int(cam_vert), 180, nothing)
cv2.createTrackbar('orient_az', winName, int(cam_az), 360, nothing)
cv2.createTrackbar('orient_el', winName, int(cam_el), 360, nothing)

# open the camera
cap = cv2.VideoCapture(cam_url)

# create a tick for FPS calculation
last_tick = cv2.getTickCount()
last_fd_update_tick = last_tick

# the flight data:
fd = flightdata.FlightData()

# refreshes the flightdata and returns the time it took to do it
def fd_refresh():
	fd_start = cv2.getTickCount()
	fd.refresh()
	fd_stop = cv2.getTickCount()

	return time_since(fd_start, fd_stop)

fd_refresh_time = fd_refresh()

# the aircraft in the camera's field of view
aircraft_in_fov = dict()

# number of flightdata updates
n_updates = 0

# the main loop
while(cap.isOpened()):

	# get fps
	tick = cv2.getTickCount()
	fps = 1 / time_since(last_tick, tick)
	last_tick = tick

	# get the fov according to the trackbar
	horz = cv2.getTrackbarPos('fov_horz', winName)
	vert = cv2.getTrackbarPos('fov_vert', winName)
	fov = (horz, vert)

	# get the camera orientation according to trackbar
	az = cv2.getTrackbarPos('orient_az', winName) + 360
	el = cv2.getTrackbarPos('orient_el', winName)
	orient = (az,el)

	# see if we need to update the flight data:
	if time_since(last_fd_update_tick, tick) >= time_between_updates:
		aircraft_in_fov.clear()         # clear the dictionary
		last_fd_update_tick = tick      # save the tick
		fd_refresh_time = fd_refresh()  # refresh the flight data
		n_updates += 1

		# loop on all the aircarft in the receiver
		for a in fd.aircraft:
			# if they don't have az/el/distance then skip them
			if a.az == None or a.el == None or a.distance == None:
				continue
			if a.lat == None or a.lon == None:
				continue
			if a.altitude == None or a.altitude == 0:
				continue

			# check to see if it's the fov the camera and the distace isn't too far:
			if is_aircraft_in_fov(a, fov, orient):
				aircraft_in_fov[a.hex] = a

	# get an image from the camera
	ret, img = cap.read()
	if not ret:
		print('Unable to get image from camera')
		break

	# get the image size
	h, w, c = img.shape
	size = (w,h)

	# for each aircraft in the fov draw it on the image
	for h, a in aircraft_in_fov.items():
		target_loc = ((a.az - az + 900)%360-180, (a.el - el + 900)%360-180) # the target location
		target_point = get_target_point_int(target_loc, fov, size)          # get it's loaction in pixels
		circle_radius = size_of_radius(a)                                   # get the circle radius
		cv2.circle(img, target_point, circle_radius, green, 2)              # draw the cirlce
		# draw text for the flight...
		flight_text = a.flight.strip()
		if (flight_text == 'N/A'):
			flight_text = h.strip()
		text = '%s: (%.0f,%.0f) %.1f mi %.1f ft, %.1f mi/h' % (flight_text, a.az, a.el, a.distance, a.altitude, a.speed)
		text_point = (target_point[0]-circle_radius-20, target_point[1]-circle_radius-5)
		cv2.putText(img, text, text_point, font, font_sz, green, 1)

	# overlay stats text
	text = '%.1f FPS' % (fps)
	cv2.putText(img, text, (10, 20), font, font_sz, green, 1)
	text = '%d tracks' % (len(aircraft_in_fov))
	cv2.putText(img, text, (10, 40), font, font_sz, green, 1)
	text = '%d n_updates' % (n_updates)
	cv2.putText(img, text, (10, 60), font, font_sz, green, 1)
	text = '%.3f fd_refresh_time' % (fd_refresh_time)
	cv2.putText(img, text, (10, 80), font, font_sz, green, 1)

	# show the window
	cv2.imshow(winName, img)

	# check for key presses
	if cv2.waitKey(1) & 0xFF == ord('q'):
		print("User hit the 'q' key, quitting!")
		break

# clean up
cap.release()
cv2.destroyAllWindows()
