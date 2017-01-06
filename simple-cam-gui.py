#
# simple-cam-gui.py
#
# The is a little program that displays the output of a webcam or ipcamera and
# overlays information whenever an airplane flys into view.
#
# It includes several trackbars used for setting the fov and orientation of the
# camera.  The intention is to use this program for calibrating a fixed camera.
#
# **** not full implemented
# * currently it is not connected to the flight data and is just testing video
# * connection, and reminding myself how to use opencv trackbars and overlays.
#

print("Press 'q' to quit")

# first read in the config file and load the variables
from configparser import ConfigParser
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

def nothing(jnk):
# a dummy function that does nothing
	pass

def getTargetPoint(loc, fov, size):
# Return the point on an image of a target at the location loc (az,el)
# given a feild of view fov (horiz,vert), and an image size (w, h)
	x = size[0] *(loc[0] / fov[0]/2 + 0.5)
	y = size[1] *(-loc[1] / fov[1]/2 + 0.5)
	return (x,y)
def getTargetPointI(loc, fov, size):
	xy = getTargetPoint(loc, fov, size)
	return (int(xy[0]), int(xy[1]))

# beginning of opencv stuff let's import it
import numpy as np
import cv2

#some consts values we'll be using
green = (0, 255, 0)
font = cv2.FONT_HERSHEY_SIMPLEX
font_sz = 0.33

# create the named window and the trackbars...
winName = 'AboveTustin'
cv2.namedWindow(winName)
cv2.createTrackbar('fov_horz', winName, int(cam_horz), 180, nothing)
cv2.createTrackbar('fov_vert', winName, int(cam_vert), 180, nothing)
cv2.createTrackbar('target_az', winName, 90, 180, nothing)
cv2.createTrackbar('target_el', winName, 90, 180, nothing)

# open the camera
cap = cv2.VideoCapture(cam_url)

# create a tick for FPS calculation
lastTick = cv2.getTickCount()

# the main loop
while(cap.isOpened()):
	# get an image from the camera
	ret, img = cap.read()
	if not ret:
		print('Unable to get image from camera')
		break

	# get the image size
	h, w, c = img.shape
	size = (w,h)

	# get the fov according to the trackbar
	horz = cv2.getTrackbarPos('fov_horz', winName)
	vert = cv2.getTrackbarPos('fov_vert', winName)
	fov = (horz, vert)

	# get the target location in img according to trackbar
	az = cv2.getTrackbarPos('target_az', winName) - 90
	el = cv2.getTrackbarPos('target_el', winName) - 90
	loc = (az,el)

	# get target point in pixels
	target = getTargetPointI(loc, fov, size)
	cv2.circle(img, target, 15, green, 2)

	# get fps
	tick = cv2.getTickCount()
	fps = cv2.getTickFrequency() / (tick-lastTick)
	lastTick = tick

	# overlay text
	text = '(%d,%d)' % (az, el)
	cv2.putText(img, text, (10, 20), font, font_sz, green, 1)
	text = '%.1f FPS' % (fps)
	cv2.putText(img, text, (10, 40), font, font_sz, green, 1)

	# show the window
	cv2.imshow(winName, img)

	# check for key presses
	if cv2.waitKey(1) & 0xFF == ord('q'):
		print("User hit the 'q' key, quitting!")
		break

# clean up
cap.release()
cv2.destroyAllWindows()
