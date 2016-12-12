# AboveTustin
[AboveTustin](https://twitter.com/abovetustin) is an ADS-B Twitter Bot running on a Raspberry Pi 2.  It tracks airplanes and then tweets whenever an airplane flies overhead.

 * Uses [dump1090-mutability](https://github.com/mutability/dump1090) for ADSB message decoding, airplane tracking, and webserving.
 * It tweets an image of a map with the airplane's track.
 * It displays the flight name if available, or the reported icao code.
 * It displays altitude, ground speed and heading information of the airplane at it's closest point to the bot.
 * Gives different hashtags depending on altitude, speed and time of day.

## Example Tweets
![](http://i.imgur.com/fpzYXFTl.png)
![](http://i.imgur.com/t1Wzd1tl.png)
![](http://i.imgur.com/mjvbbPNl.png)

## Hardware
![Airplane Tracking Twitter Bot](http://i.imgur.com/zKuL5y1l.jpg)
 
 * $35 RaspberryPi 2 over a year old
 * $15 RTL-SDR dongle (NooElec)
 * $6 Coax adapter
 * Coax cable found in my closet
 * Home made cantenna ([instructions here](https://www.adsbexchange.com/forums/topic/beginners-2-cantenna-easy-diy-antenna-to-improve-rangeplane-count/))
 
## Future Plans
* Hopefully very soon it will be included in jprochazka's wonderful [adsb-receiver](https://github.com/jprochazka/adsb-receiver) project, which will simplify the instalation process for those who would like to create their own twitter bots.
* Add a calibrated sound meter to catch [noise ordinance](http://www.ocair.com/generalaviation/noise/) rule breakers.
* Add PTZ IP camera to capture video of the airplanes and auto-upload to YouTube
 * Some even more future day use OpenCV to video detect and track airplanes.

## Dependencies
* Uses [dump1090-mutability](https://github.com/mutability/dump1090) for ADSB message decoding, airplane tracking, and webserving.
* Uses [twitter](https://pypi.python.org/pypi/twitter) for tweeting.
* Uses [selenium](https://pypi.python.org/pypi/selenium) with [PhantomJS](http://phantomjs.org/) for capturing screenshots.
  * Use jprochazka's [build of PhantomJS](https://github.com/jprochazka/phantomjs-linux-armv7l)

## Contributors
* [Kevin Brandon](https://github.com/kevinabrandon)
* [Joseph Prochazka](https://github.com/jprochazka)
