#
# screenshot.py
#
# kevinabrandon@gmail.com
#

import sys
import time

from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

def loadmap():
    '''
    loadmap() 
    Creates a browser object and loads the webpage.  
    It sets up the map to the proper zoom level.

    Returns the browser on success, None on fail.
    '''
    try:
        browser = webdriver.PhantomJS()

        browser.set_window_size(1280,720)

        print ("getting web page...")
        browser.get("http://localhost/dump1090/gmap.html")

        # Need to wait for the page to load
        timeout = 20
        print ("waiting for page to load...")
        wait = WebDriverWait(browser, timeout)
        element = wait.until(EC.element_to_be_clickable((By.ID,'dump1090_version')))
    
        print("reset map:")
        resetbutton = browser.find_elements_by_xpath("//*[contains(text(), 'Reset Map')]")
        resetbutton[0].click()
        
        print("zoom in 4 times:")
        zoomin = browser.find_element_by_class_name('ol-zoom-in')
        zoomin.click()
        zoomin.click()
        zoomin.click()
        zoomin.click()

        return browser
    except:
        print("exception in loadmap()")
        print (sys.exc_info()[0])
        return None


def screenshot(browser, name):
    '''
    screenshot()
    Takes a screenshot of the browser
    '''
    try:
        browser.save_screenshot(name)
        print("suucess saving screnshot: %s" % name)
    except:
        print("exception in screenshot()")
        print(sys.exc_info()[0])


def clickOnAirplane(browser, text):
    '''
    clickOnAirplane()
    Clicks on the airplane with the name text, and then takes a screenshot
    '''
    try:
        element = browser.find_elements_by_xpath("//td[text()='%s']" % text)
        print("number of elements found: %i" % len(element))
        if len(element) > 0:
            print("click!")
            element[0].click()
            time.sleep(0.5) # if we don't wait a little bit the airplane icon isn't drawn.
            screenshot(browser, '/home/pi/AboveTustin/tweet.png')
            return True
        else:
            print("couldn't find the object")
    except:
        print("exception in clickOnAirplane()")
        print (sys.exc_info()[0])

    return False

