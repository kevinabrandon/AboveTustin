
import cv2
print('opencv-' + cv2.__version__)

from configparser import ConfigParser


# Read the configuration file for this application.
parser = ConfigParser()
parser.read('config.ini')
cam_url = parser.get('simple-cam', 'cam_url')

print('cam url: ' + cam_url)
if (cam_url == '0'):
	cam_url = 0
if (cam_url == '1'):
	cam_url = 1


cap = cv2.VideoCapture(cam_url)

errCount = 0

while(1):
    ret, frame = cap.read()
    if not ret:
    	break
    
    cv2.imshow('VIDEO', frame)
    

    if cv2.waitKey(1) & 0xFF == ord('q'):
    	break

# When everything done, release the capture
cap.release()
cv2.destroyAllWindows()