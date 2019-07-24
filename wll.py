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
import urllib3
import socket
import math
import json
import write_profile
import owm_daily

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
        self.ip_address = None

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

        if False:
            http = urllib3.PoolManager()
            c = http.request('GET', request)
            wdata = c.data
            jdata = json.loads(wdata.decode('utf-8'))
            c.close()
            http.clear()
        else:
            jdata = {
"data":
{
    "did":"001D0A700002",
    "ts":1531754005,
    "conditions": [
    {
            "lsid":48308,                                  
            "data_structure_type":1,                       
            "txid":1,                                      
            "temp": 62.7,                                  
            "hum":1.1,                                     
            "dew_point": -0.3,                             
            "wet_bulb":null,                               
            "heat_index": 5.5,                             
            "wind_chill": 6.0,                             
            "thw_index": 5.5,                              
            "thsw_index": 5.5,                             
            "wind_speed_last":2,                           
            "wind_dir_last":null,                          
            "wind_speed_avg_last_1_min":4                  
            "wind_dir_scalar_avg_last_1_min":15            
            "wind_speed_avg_last_2_min":42606,             
            "wind_dir_scalar_avg_last_2_min": 170.7,       
            "wind_speed_hi_last_2_min":8,                  
            "wind_dir_at_hi_speed_last_2_min":0.0,         
            "wind_speed_avg_last_10_min":42606,            
            "wind_dir_scalar_avg_last_10_min": 4822.5,     
            "wind_speed_hi_last_10_min":8,                 
            "wind_dir_at_hi_speed_last_10_min":0.0,        
            "rain_size":2,                                 
            "rain_rate_last":0,                            
            "rain_rate_hi":null,                           
            "rainfall_last_15_min":null,                   
            "rain_rate_hi_last_15_min":0,                  
            "rainfall_last_60_min":null,                   
            "rainfall_last_24_hr":null,                    
            "rain_storm":null,                             
            "rain_storm_start_at":null,                    
            "solar_rad":747,                               
            "uv_index":5.5,                                
            "rx_state":2,                                  
            "trans_battery_flag":0,                        
            "rainfall_daily":63,                           
            "rainfall_monthly":63,                         
            "rainfall_year":63,                            
            "rain_storm_last":null,                        
            "rain_storm_last_start_at":null,               
            "rain_storm_last_end_at":null                  
    },
    {
            "lsid":3187671188,
            "data_structure_type":2,
            "txid":3,
            "temp_1":null,                                 
            "temp_2":null,                                 
            "temp_3":null,                                 
            "temp_4":null,                                 
            "moist_soil_1":null,                           
            "moist_soil_2":null,                           
            "moist_soil_3":null,                           
            "moist_soil_4":null,                           
            "wet_leaf_1":null,                             
            "wet_leaf_2":null,                             
            "rx_state":null,                               
            "trans_battery_flag":null                      
    },
    {
            "lsid":48307,
            "data_structure_type":4,
            "temp_in":78.0,                                
            "hum_in":41.1,                                 
            "dew_point_in":7.8,                            
            "heat_index_in":8.4                            
    },
    {
            "lsid":48306,
            "data_structure_type":3,
            "bar_sea_level":30.008,                       
            "bar_trend": null,                            
            "bar_absolute":30.008                        
    }]
},
"error":null }

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
                self.setDriver('CLITEMP', float(record['temp']), True, False)
            else:
                LOGGER.info('Skipping data type' + record['data_structure_type'])


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
            {'driver': 'CLITEMP', 'value': 0, 'uom': 4},   # temperature
            {'driver': 'CLIHUM', 'value': 0, 'uom': 22},   # humidity
            {'driver': 'BARPRES', 'value': 0, 'uom': 118}, # pressure
            {'driver': 'WINDDIR', 'value': 0, 'uom': 76},  # direction
            {'driver': 'GV0', 'value': 0, 'uom': 4},       # max temp
            {'driver': 'GV1', 'value': 0, 'uom': 4},       # min temp
            {'driver': 'GV4', 'value': 0, 'uom': 49},      # wind speed
            {'driver': 'GV6', 'value': 0, 'uom': 82},      # rain
            {'driver': 'GV13', 'value': 0, 'uom': 25},     # climate conditions
            {'driver': 'GV14', 'value': 0, 'uom': 22},     # cloud conditions
            {'driver': 'GV15', 'value': 0, 'uom': 83},     # visibility
            {'driver': 'GV16', 'value': 0, 'uom': 71},     # UV index
            ]


    
if __name__ == "__main__":
    try:
        polyglot = polyinterface.Interface('WLL')
        polyglot.start()
        control = Controller(polyglot)
        control.runForever()
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
        

