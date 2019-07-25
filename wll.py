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

                    if self.ip_address == '':
                        self.addNotice("WeatherLink IP Address parameter must be set");
                        self.configured = False

    def start(self):
        LOGGER.info('Starting node server')

        self.check_params()
        # TODO: Discovery
        LOGGER.info('Node server started')

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

        if True:
            c = requests.get(request)
            jdata = c.json()
        else:
            with open('sample.json') as json_file:
                jdata = json.load(json_file)

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
                if record['temp'] != None:
                    self.setDriver('CLITEMP', float(record['temp']), True, False)
                self.setDriver('CLIHUM', float(record['hum']), True, False)
                self.setDriver('DEWPT', float(record['dew_point']), True, False)
                if record['wind_dir_last'] != None:
                    self.setDriver('WINDDIR', float(record['wind_dir_last']), True, False)
                if record['wet_bulb'] != None:
                    self.setDriver('GV0', float(record['wet_bulb']), True, False)
                self.setDriver('GV1', float(record['heat_index']), True, False)
                self.setDriver('GV2', float(record['wind_chill']), True, False)
                if record['wind_speed_last'] != None:
                    self.setDriver('GV3', float(record['wind_speed_last']), True, False)
                self.setDriver('GV4', float(record['rain_rate_last']), True, False)
                self.setDriver('GV5', self.rain_size(record['rain_size']), True, False)
                self.setDriver('GV6', float(record['solar_rad']), True, False)
                self.setDriver('GV7', float(record['uv_index']), True, False)
            elif record['data_structure_type'] == 3:  # pressure
                self.setDriver('BARPRES', float(record['bar_sea_level']), True, False)
                if record['bar_trend'] != None:
                    self.setDriver('GV8', float(record['bar_trend']), True, False)
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
            {'driver': 'WINDDIR', 'value': 0, 'uom': 76}, # direction
            {'driver': 'DEWPT', 'value': 0, 'uom': 17},   # direction
            {'driver': 'GV0', 'value': 0, 'uom': 17},     # wet bulb
            {'driver': 'GV1', 'value': 0, 'uom': 17},     # heat index
            {'driver': 'GV2', 'value': 0, 'uom': 17},     # wind chill
            {'driver': 'GV3', 'value': 0, 'uom': 48},     # wind speed
            {'driver': 'GV4', 'value': 0, 'uom': 24},     # rain rate
            {'driver': 'GV5', 'value': 0, 'uom': 105},    # rain size
            {'driver': 'GV6', 'value': 0, 'uom': 74},     # solar radiation
            {'driver': 'GV7', 'value': 0, 'uom': 71},     # UV index
            {'driver': 'GV8', 'value': 0, 'uom': 23},     # pressure trend
            ]


    
if __name__ == "__main__":
    try:
        polyglot = polyinterface.Interface('WLL')
        polyglot.start()
        control = Controller(polyglot)
        control.runForever()
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
        

