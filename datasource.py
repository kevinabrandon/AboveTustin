import configparser

import flightdata
import screenshot


class Error(Exception):
        pass


DRIVERS = {
        'dump1090': dict(
                data=flightdata.Dump1090DataParser,
                map=screenshot.Dump1090Display),
        'virtualradarserver': dict(
                data=flightdata.VRSDataParser,
                map=screenshot.VRSDisplay)
}


DEFAULT_DRIVER = 'dump1090'


def get_driver():
        driver = DRIVERS.get(g_driver, None)
        if not driver:
                raise Error('Unknown driver: {}. Valid drivers are {}'.format(
                    g_driver, ', '.join(DRIVERS.keys())))
        return driver


def get_map_source():
        return get_driver()['map'](g_map_url)


def get_data_source():
        return flightdata.FlightData(
            data_url=g_data_url,
            parser=get_driver()['data']())


parser = configparser.ConfigParser()
parser.read('config.ini')
abovetustin = parser['abovetustin']
g_driver = abovetustin.get('driver', DEFAULT_DRIVER)
g_data_url = parser.get('abovetustin', 'data_url')
g_map_url = parser.get('abovetustin', 'map_url')
