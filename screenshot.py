#
# screenshot.py
#
# kevinabrandon@gmail.com
#

import sys
import time
from selenium import webdriver
from selenium.common import exceptions as seleniumexceptions
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from configparser import ConfigParser

# Read the configuration file for this application.
parser = ConfigParser()
parser.read('config.ini')

# Assign AboveTustin variables.
abovetustin_image_width = int(parser.get('abovetustin', 'image_width'))
abovetustin_image_height = int(parser.get('abovetustin', 'image_height'))

#  Check for Crop settings
if parser.has_section('crop'):
    do_crop = parser.getboolean('crop', 'do_crop')
    crop_x = parser.getint('crop', 'crop_x')
    crop_y = parser.getint('crop', 'crop_y')
    crop_width = parser.getint('crop', 'crop_width')
    crop_height = parser.getint('crop', 'crop_height')
    if do_crop:
        try:
            from PIL import Image
            from io import BytesIO
            print('will crop')
        except ImportError:
            print('Image manipulation module "Pillow" not found, cropping disabled')
            do_crop = False
else:
    do_crop = False

# Assign dump1090 variables.
dump1090_map_url = parser.get('dump1090', 'map_url')
dump1090_request_timeout = int(parser.get('dump1090', 'request_timeout'))


class AircraftDisplay(object):
    def __init__(self, url):
        self.url = url
        self.browser = None
        self.loadmap()

    def loadmap(self):
        raise NotImplementedError

    def reload(self):
        self.browser.quit()
        self.browser = None
        self.loadmap()

    def screenshot(self, name):
        '''
        screenshot()
        Takes a screenshot of the browser
        '''
        if do_crop:
            print('cropping screenshot')
            #  Grab screenshot rather than saving
            im = self.browser.get_screenshot_as_png()
            im = Image.open(BytesIO(im))

            #  Crop to specifications
            im = im.crop((crop_x, crop_y, crop_width, crop_height))
            im.save(name)
        else:
            self.browser.save_screenshot(name)
        print("success saving screenshot: %s" % name)

    def ClickOnAirplane(self, ident):
        raise NotImplementedError


class Dump1090Display(AircraftDisplay):
    def loadmap(self):
        '''
        loadmap()
        Creates a browser object and loads the webpage.
        It sets up the map to the proper zoom level.

        Returns the browser on success, None on fail.
        '''
        browser = webdriver.PhantomJS(desired_capabilities={'phantomjs.page.settings.resourceTimeout': '20000'})
        browser.set_window_size(abovetustin_image_width, abovetustin_image_height)

        print("getting web page...")
        browser.set_page_load_timeout(15)
        browser.get(self.url)

        # Need to wait for the page to load
        timeout = dump1090_request_timeout
        print ("waiting for page to load...")
        wait = WebDriverWait(browser, timeout)
        element = wait.until(EC.element_to_be_clickable((By.ID,'dump1090_version')))

        print("reset map:")
        resetbutton = browser.find_elements_by_xpath("//*[contains(text(), 'Reset Map')]")
        resetbutton[0].click()

        print("zoom in 4 times:")
        try:
            # First look for the Open Layers map zoom button.
            zoomin = browser.find_element_by_class_name('ol-zoom-in')
            print(zoomin)
        except seleniumexceptions.NoSuchElementException as e:
            # Doesn't seem to be Open Layers, so look for the Google
            # maps zoom button.
            zoomin = browser.find_elements_by_xpath('//*[@title="Zoom in"]')
            if zoomin:
                zoomin = zoomin[0]
        zoomin.click()
        zoomin.click()
        zoomin.click()
        zoomin.click()
        self.browser = browser

    def clickOnAirplane(self, text):
        '''
        clickOnAirplane()
        Clicks on the airplane with the name text, and then takes a screenshot
        '''
        element = self.browser.find_elements_by_xpath("//td[text()='%s']" % text)
        print("number of elements found: %i" % len(element))
        if len(element) > 0:
            print("click!")
            element[0].click()
            time.sleep(0.5) # if we don't wait a little bit the airplane icon isn't drawn.
            return self.screenshot('tweet.png')
        else:
            print("couldn't find the object")
