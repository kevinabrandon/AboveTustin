# AboveTustin

> **Status, November 2026:** AboveTustin is being rebuilt. The original Raspberry Pi
> bot described below stopped working when the services it depended on
> (dump1090-mutability, PhantomJS, the Twitter v1.1 API, FlightAware FlightXML3) were
> retired. Its final code is preserved at tag
> [`v1.0.0`](https://github.com/kevinabrandon/AboveTustin/tree/v1.0.0). The rebuild
> is landing on `master` as a series of small pull requests, so `master` is a work in
> progress until the new bot runs.
>
> The idea stays the same: watch a local ADS-B receiver, notice when an aircraft passes
> close overhead, and post a short note with a map of its track. Underneath, v2 reads
> from [readsb](https://github.com/wiedehopf/readsb) and
> [tar1090](https://github.com/wiedehopf/tar1090) instead of dump1090, posts to
> Bluesky instead of Twitter, and is a proper Python 3.12 package with tests and CI
> instead of a handful of scripts. Internally everything is in SI units, with
> conversions to the feet and miles in the posts handled at the edges by pint. The
> alarm-zone tracking logic from v1 carries over.

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
 * Home made cantenna ([instructions here](https://web.archive.org/web/20170909005202/https://www.adsbexchange.com/forums/topic/beginners-2-cantenna-easy-diy-antenna-to-improve-rangeplane-count/))
 
## Future Plans
* Hopefully very soon it will be included in jprochazka's wonderful [adsb-receiver](https://github.com/jprochazka/adsb-receiver) project, which will simplify the instalation process for those who would like to create their own twitter bots.
* Add a calibrated sound meter to catch [noise ordinance](http://www.ocair.com/generalaviation/noise/) rule breakers.
* Add PTZ IP camera to capture video of the airplanes and auto-upload to YouTube
 * Some even more future day use OpenCV to video detect and track airplanes.

## Dependencies
* v2 uses [pint](https://pint.readthedocs.io/) for unit handling; see `CONTRIBUTING.md` for the unit policy.
* Uses [dump1090-mutability](https://github.com/mutability/dump1090) for ADSB message decoding, airplane tracking, and webserving.
* Uses [twitter](https://pypi.python.org/pypi/twitter) for tweeting.
* Uses [selenium](https://pypi.python.org/pypi/selenium) with [PhantomJS](http://phantomjs.org/) for capturing screenshots.
  * Use jprochazka's [build of PhantomJS](https://github.com/jprochazka/phantomjs-linux-armv7l)

## Contributors
* [Kevin Brandon](https://github.com/kevinabrandon)
* [Joseph Prochazka](https://github.com/jprochazka)
