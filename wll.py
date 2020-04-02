#!/usr/bin/env python3
"""
Polyglot v2 node server Davice WeatherLink Live weather data
Copyright (C) 2018 Robert Paauwe
"""

CLOUD = False
try:
    import polyinterface
except ImportError:
    import pgc_interface as polyinterface
    CLOUD = True
import sys
import time
import datetime
import requests
import socket
import math
import json

LOGGER = polyinterface.LOGGER

class Controller(polyinterface.Controller):
    id = 'weather'
    #id = 'controller'
    hint = [0,0,0,0]
    def __init__(self, polyglot):
        super(Controller, self).__init__(polyglot)
        self.name = 'WeatherLink'
        self.address = 'weather'
        self.primary = self.address
        self.configured = False
        self.myConfig = {}
        self.ip_address = ''
        self.has_soil = False
        self.has_indoor = False

        self.poly.onConfig(self.process_config)

    # Process changes to customParameters
    def process_config(self, config):
        if 'customParams' in config:
            # Check if anything we care about was changed...
            if config['customParams'] != self.myConfig:
                changed = False
                if 'IP Address' in config['customParams']:
                    if self.ip_address != config['customParams']['IP Address']:
                        self.ip_address = config['customParams']['IP Address']
                        changed = True

                self.myConfig = config['customParams']
                if changed:
                    self.removeNoticesAll()
                    self.configured = True
                    self.discover_nodes()

                    if self.ip_address == '':
                        self.addNotice("WeatherLink IP Address parameter must be set");
                        self.configured = False

    def start(self):
        LOGGER.info('Starting node server')

        self.check_params()
        # TODO: Discovery
        LOGGER.info('Node server started')

        self.discover_nodes()
        if self.has_indoor:
            LOGGER.info('Creating node for indoor conditions')
            self.addNode(IndoorNode(self, self.address, 'indoor', 'Indoor'))
        if self.has_soil:
            LOGGER.info('Creating node for soil conditions')
            self.addNode(SoilNode(self, self.address, 'soil', 'Soil'))

        # Do an initial query to get filled in as soon as possible
        self.query_conditions()

    def longPoll(self):
        pass

    def shortPoll(self):
        self.query_conditions()

    def rain_size(self, size):
        if size == None:
            return 0
        if size == 1:
            return 0.01 # inch
        if size == 2:
            return 0.2 # mm
        if size == 3:
            return 0.1 # mm
        if size == 4:
            return 0.001 # inch

        return 0

    def update(self, driver, value):
        if value != None:
            self.setDriver(driver, float(value), True, False)

    def discover_nodes(self):
        if not self.configured:
            return
        request = 'http://' + self.ip_address + '/v1/current_conditions'
        c = requests.get(request)
        jdata = c.json()
        for record in jdata['data']['conditions']:
            if record['data_structure_type'] == 2:
                self.has_soil = True
            elif record['data_structure_type'] == 1:
                self.has_indoor = True

    def query_conditions(self):
        # Query for the current conditions. We can do this fairly
        # frequently, probably as often as once a minute.
        #
        # By default JSON is returned

        request = 'http://' + self.ip_address + '/v1/current_conditions'
        LOGGER.debug('request = %s' % request)

        if not self.configured:
            LOGGER.info('Skipping connection because we aren\'t configured yet.')
            return

        c = requests.get(request)
        jdata = c.json()

        LOGGER.debug(jdata)

        # 4 record types can be returned. Lets use a separate
        # node for each.  We'll start with the ISS current
        # condition record as that has the outside info
        #
        # Other records are:
        #  Leaf/Soil Moisture
        #  LSS BAR
        #  LSS temperature/humidity
        #
        # { "data":
        #    { "did: , "ts": , "conditions": [
        #        {"data_structure_type": 1

        for record in jdata['data']['conditions']:
            if record['data_structure_type'] == 1:
                # We have a local sensor ID and transmitter ID. Do we
                # need to look at these?
                LOGGER.info('Found current conditions')

                # Update node with values in <record>
                self.update('CLITEMP', record['temp'])
                self.update('CLIHUM', record['hum'])
                self.update('DEWPT', record['dew_point'])
                self.update('WINDDIR', record['wind_dir_last'])
                self.update('GV0', record['wet_bulb'])
                self.update('GV1', record['heat_index'])
                self.update('GV2', record['wind_chill'])
                self.update('SPEED', record['wind_speed_last'])
                self.update('SOLRAD', record['solar_rad'])
                self.update('GV7', record['uv_index'])
                self.update('GV9', record['wind_speed_hi_last_2_min'])

                # rainfall is in counts and 1 count = 0.01 inches
                # rain size is the tipping bucket calibration. 
                #  size = 1 means 0.01 inches
                #  size = 2 means 0.2 mm
                #  size = 3 means 0.1 mm
                #  size = 4 means 0.001 inches
                if record['rain_size'] == 1:
                    rain_cal = 0.01
                elif record['rain_size'] == 2:
                    rain_cal = 0.0787
                elif record['rain_size'] == 3:
                    rain_cal = 0.0394
                elif record['rain_size'] == 4:
                    rain_cal = 0.001
                else:
                    rain_cal = 0.01
                #self.setDriver('GV5', self.rain_size(record['rain_size']), True, False)
                if record['rainfall_daily'] != None:
                    rain = rain_cal * int(record['rainfall_daily'])
                    self.setDriver('GV10', rain, True, False)

                if record['rain_rate_last'] != None:
                    rain = rain_cal * int(record['rain_rate_last'])
                    self.setDriver('RAINRT', rain, True, False)

                if record['rainfall_year'] != None:
                    rain = rain_cal * int(record['rainfall_year'])
                    self.setDriver('GV5', rain, True, False)


                # wind gust? wind_speed_hi_last_2_min
                # hi temperature
                # low temperature
                # rain today rainfall_daily  (in counts????)
            elif record['data_structure_type'] == 3:  # pressure
                if record['bar_sea_level'] != None:
                    self.setDriver('BARPRES', float(record['bar_sea_level']), True, False)
                if record['bar_trend'] != None:
                    self.setDriver('GV8', float(record['bar_trend']), True, False)
            elif record['data_structure_type'] == 4 and self.has_indoor:  # Indoor conditions
                LOGGER.info(record)
                # self.nodes['indoor'].setDriver(...
                # 'temp-in'
                # 'hum-in'
                # 'dew_point_in'
                # 'heat_index_in'
                if record['temp_in'] != None:
                    self.nodes['indoor'].setDriver('CLITEMP', float(record['temp_in']), True, False)
                if record['hum_in'] != None:
                    self.nodes['indoor'].setDriver('CLIHUM', float(record['hum_in']), True, False)
                if record['dew_point_in'] != None:
                    self.nodes['indoor'].setDriver('DEWPT', float(record['dew_point_in']), True, False)
                if record['heat_index_in'] != None:
                    self.nodes['indoor'].setDriver('GV0', float(record['heat_index_in']), True, False)
            elif record['data_structure_type'] == 2 and self.has_soil:  # Soil Conditions
                # self.nodes['soil'].setDriver(...
                if record['temp_1'] != None:
                    self.nodes['soil'].setDriver('GV0', float(record['temp_1']), True, False)
                if record['temp_2'] != None:
                    self.nodes['soil'].setDriver('GV1', float(record['temp_2']), True, False)
                if record['temp_3'] != None:
                    self.nodes['soil'].setDriver('GV2', float(record['temp_3']), True, False)
                if record['temp_4'] != None:
                    self.nodes['soil'].setDriver('GV3', float(record['temp_4']), True, False)
                if record['moist_soil_1'] != None:
                    self.nodes['soil'].setDriver('GV4', float(record['moist_soil_1']), True, False)
                if record['moist_soil_2'] != None:
                    self.nodes['soil'].setDriver('GV5', float(record['moist_soil_2']), True, False)
                if record['moist_soil_3'] != None:
                    self.nodes['soil'].setDriver('GV6', float(record['moist_soil_3']), True, False)
                if record['moist_soil_4'] != None:
                    self.nodes['soil'].setDriver('GV7', float(record['moist_soil_4']), True, False)
                if record['wet_leaf_1'] != None:
                    self.nodes['soil'].setDriver('GV8', float(record['wet_leaf_1']), True, False)
                if record['wet_leaf_2'] != None:
                    self.nodes['soil'].setDriver('GV9', float(record['wet_leaf_2']), True, False)
            else:
                LOGGER.info('Skipping data type %d' % record['data_structure_type'])


    def query(self):
        for node in self.nodes:
            self.nodes[node].reportDrivers()

    def discover(self, *args, **kwargs):
        # Create any additional nodes here
        LOGGER.info("In Discovery...")

    # Delete the node server from Polyglot
    def delete(self):
        LOGGER.info('Removing node server')

    def stop(self):
        LOGGER.info('Stopping node server')

    def update_profile(self, command):
        st = self.poly.installprofile()
        return st

    def check_params(self):
        if 'IP Address' in self.polyConfig['customParams']:
            self.ip_address = self.polyConfig['customParams']['IP Address']

        self.configured = True

        self.addCustomParam( {
            'IP Address': self.ip_address} )


        self.removeNoticesAll()
        if self.ip_address == '':
            self.addNotice("WeatherLink IP Address parameter must be set");
            self.configured = False

    def remove_notices_all(self, command):
        self.removeNoticesAll()


    commands = {
            'DISCOVER': discover,
            'UPDATE_PROFILE': update_profile,
            'REMOVE_NOTICES_ALL': remove_notices_all
            }

    # The controller node has the main current condition data
    #
    drivers = [
            {'driver': 'ST', 'value': 1, 'uom': 2},   # node server status
            {'driver': 'CLITEMP', 'value': 0, 'uom': 17}, # temperature
            {'driver': 'CLIHUM', 'value': 0, 'uom': 22},  # humidity
            {'driver': 'BARPRES', 'value': 0, 'uom': 23}, # pressure
            {'driver': 'DEWPT', 'value': 0, 'uom': 17},   # dew point
            {'driver': 'WINDDIR', 'value': 0, 'uom': 76}, # direction
            {'driver': 'SPEED', 'value': 0, 'uom': 48},   # wind speed
            {'driver': 'GV9', 'value': 0, 'uom': 48},     # wind gust
            {'driver': 'GV0', 'value': 0, 'uom': 17},     # wet bulb
            {'driver': 'GV1', 'value': 0, 'uom': 17},     # heat index
            {'driver': 'GV2', 'value': 0, 'uom': 17},     # wind chill
            {'driver': 'RAINRT', 'value': 0, 'uom': 24},     # rain rate
            {'driver': 'GV5', 'value': 0, 'uom': 105},    # rain size
            {'driver': 'SOLRAD', 'value': 0, 'uom': 74},  # solar radiation
            {'driver': 'GV7', 'value': 0, 'uom': 71},     # UV index
            {'driver': 'GV8', 'value': 0, 'uom': 23},     # pressure trend
            {'driver': 'GV10', 'value': 0, 'uom': 105},   # daily rainfall
            {'driver': 'GV11', 'value': 0, 'uom': 17},    # indoor temp
            {'driver': 'GV12', 'value': 0, 'uom': 22},    # indoor humidity
            ]

class IndoorNode(polyinterface.Node):
    id = 'indoor'
    drivers = [
	{'driver': 'CLITEMP', 'value': 0, 'uom': 17},
	{'driver': 'CLIHUM', 'value': 0, 'uom': 22},
	{'driver': 'DEWPT', 'value': 0, 'uom': 17},
	{'driver': 'GV0', 'value': 0, 'uom': 17},
	]


class SoilNode(polyinterface.Node):
    id = 'soil'
    drivers = [
	{'driver': 'GV0', 'value': 0, 'uom': 17},
	{'driver': 'GV1', 'value': 0, 'uom': 17},
	{'driver': 'GV2', 'value': 0, 'uom': 17},
	{'driver': 'GV3', 'value': 0, 'uom': 17},
	{'driver': 'GV4', 'value': 0, 'uom': 87},
	{'driver': 'GV5', 'value': 0, 'uom': 87},
	{'driver': 'GV6', 'value': 0, 'uom': 87},
	{'driver': 'GV7', 'value': 0, 'uom': 87},
	{'driver': 'GV8', 'value': 0, 'uom': 56},
	{'driver': 'GV9', 'value': 0, 'uom': 56},
	]

    
if __name__ == "__main__":
    try:
        polyglot = polyinterface.Interface('WLL')
        polyglot.start()
        control = Controller(polyglot)
        control.runForever()
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
        
