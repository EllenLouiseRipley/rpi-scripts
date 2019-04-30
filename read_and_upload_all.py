#!/usr/bin/env python3
# This file is part of HoneyPi [honey-pi.de] which is released under Creative Commons License Attribution-NonCommercial-ShareAlike 3.0 Unported (CC BY-NC-SA 3.0).
# See file LICENSE or go to http://creativecommons.org/licenses/by-nc-sa/3.0/ for full license details.

import math
import threading
import time
from pprint import pprint
import multiprocessing as mp
from multiprocessing import Process, Queue

import RPi.GPIO as GPIO
import thingspeak # https://github.com/mchwalisz/thingspeak/
import requests

from read_bme680 import measure_bme680, initBME680FromMain
from read_ds18b20 import measure_temperature, read_unfiltered_temperatur_values, filter_temperatur_values, filtered_temperature, checkIfSensorExistsInArray
from read_hx711 import measure_weight, compensate_temperature, init_hx711
from read_dht import measure_dht
from read_max import measure_tc
from read_settings import get_settings, get_sensors
from utilities import reboot, error_log, shutdown, start_single, stop_single
from write_csv import write_csv


class MyRebootException(Exception):
    """Too many ConnectionErrors => Rebooting"""
    pass

def start_measurement(measurement_stop):
    try:
        print("The measurements have started.")
        start_time = time.time()

        # load settings
        settings = get_settings()
        # ThingSpeak data
        channel_id = settings["ts_channel_id"]
        write_key = settings["ts_write_key"]
        interval = settings["interval"]
        debug = settings["debug"] # flag to enable debug mode (HDMI output enabled and no rebooting)
        shutdownAfterTransfer = settings["shutdownAfterTransfer"]
        offline = settings["offline"] # flag to enable offline csv storage

        if debug:
            print("Debug-Mode is enabled.")

        if interval and not isinstance(interval, int) or interval == 0 or not channel_id or not write_key:
            print("ThingSpeak settings are not complete or interval is 0")
            measurement_stop.set()

        # read configured sensors from settings.json
        ds18b20Sensors = get_sensors(settings, 0)
        bme680Sensors = get_sensors(settings, 1)
        weightSensors = get_sensors(settings, 2)
        dhtSensors = get_sensors(settings, 3)
        tcSensors = get_sensors(settings, 4)

        # -- Run Pre Configuration --
        # if bme680 is configured
        if bme680Sensors and len(bme680Sensors) == 1:
            bme680IsInitialized = initBME680FromMain()
        else:
            bme680IsInitialized = 0

        # if hx711 is set
        hxInits = []
        for (i, sensor) in enumerate(weightSensors):
            _hx = init_hx711(sensor, debug)
            hxInits.append(_hx)

        # ThingSpeak channel
        channel = thingspeak.Channel(id=channel_id, write_key=write_key)

        # counting connection Errors
        connectionErros = 0

        # start at -6 because we want to get 6 values before we can filter some out
        counter = -6
        time_measured = 0
        while not measurement_stop.is_set():
            counter += 1

            # read values from sensors every second
            for (sensorIndex, sensor) in enumerate(ds18b20Sensors):
                checkIfSensorExistsInArray(sensorIndex)
                if 'device_id' in sensor:
                    read_unfiltered_temperatur_values(sensorIndex, sensor['device_id'])

            # wait seconds of interval before next check
            # free ThingSpeak account has an upload limit of 15 seconds
            time_now = time.time()
            isTimeToMeasure = (time_now-time_measured >= interval) and counter > 0 # old: counter%interval == 0
            if isTimeToMeasure or interval == 1:
                now = time.strftime("%H:%M", time.localtime(time_now))
                lastMeasurement = time.strftime("%H:%M", time.localtime(time_measured))
                if time_measured == 0:
                    print("First time measurement. Now: " + str(now))
                else:
                    print("Last measurement was at " + str(lastMeasurement))
                    print("Time over for a new measurement. Time is now: " + str(now))
                time_measured = time.time()

                def measure(q):
                    global connectionErros

                    # filter the values out
                    for (sensorIndex, sensor) in enumerate(ds18b20Sensors):
                        filter_temperatur_values(sensorIndex)

                    # dict with all fields and values which will be tranfered to ThingSpeak later
                    ts_fields = {}

                    # measure every sensor with type 0
                    for (sensorIndex, sensor) in enumerate(ds18b20Sensors):
                        # if we have at leat one filtered value we can upload
                        if len(filtered_temperature[sensorIndex]) > 0 and 'ts_field' in sensor:
                            ds18b20_temperature = filtered_temperature[sensorIndex].pop() # get last value from array
                            ts_field_ds18b20 = sensor["ts_field"]
                            if ts_field_ds18b20:
                                ts_fields.update({ts_field_ds18b20: ds18b20_temperature})

                    # measure BME680 (can only be once) [type 1]
                    if bme680Sensors and len(bme680Sensors) == 1 and bme680IsInitialized:
                        bme680_values = measure_bme680(bme680Sensors[0], 30)
                        ts_fields.update(bme680_values)

                    # measure every sensor with type 3 [DHT11/DHT22]
                    for (i, sensor) in enumerate(dhtSensors):
                        tempAndHum = measure_dht(sensor)
                        ts_fields.update(tempAndHum)

                    # measure every sensor with type 4 [MAX6675]
                    for (i, sensor) in enumerate(tcSensors):
                        tc_temp = measure_tc(sensor)
                        ts_fields.update(tc_temp)

                    start_single()
                    # measure every sensor with type 2 [HX711]
                    for (i, sensor) in enumerate(weightSensors):
                        weight = measure_weight(sensor, hxInits[i])
                        weight = compensate_temperature(sensor, weight, ts_fields)
                        ts_fields.update(weight)
                    stop_single()

                    # print all measurement values stored in ts_fields
                    for key, value in ts_fields.items():
                        print(key + ": " + str(value))

                    if len(ts_fields) > 0:
                        if offline == 1 or offline == 3:
                            try:
                                write_csv(ts_fields)
                                if debug:
                                    error_log("Info: Data succesfully saved to CSV-File.")
                            except Exception as ex:
                                error_log(ex, "Exception")
                        if offline == 0 or offline == 1 or offline == 2:
                            try:
                                # update ThingSpeak / transfer values
                                channel.update(ts_fields)
                                if debug:
                                    error_log("Info: Data succesfully transfered to ThingSpeak.")
                                if connectionErros > 0:
                                    if debug:
                                        error_log("Info: Connection Errors (" + str(connectionErros) + ") Counting resetet.")
                                    # reset connectionErros because transfer succeded
                                    connectionErros = 0
                            except requests.exceptions.HTTPError as errh:
                                error_log(errh, "Http Error")
                            except requests.exceptions.ConnectionError as errc:
                                connectionErros += 1
                                error_log(errc, "Error Connecting " + str(connectionErros))

                                # Write to CSV-File if ConnectionError
                                if offline == 2:
                                    write_csv(ts_fields)
                                    if debug:
                                        error_log("Info: Data succesfully saved to CSV-File.")

                                # multiple connectionErrors in a row => MyRebootException
                                if connectionErros >= 5:
                                    raise MyRebootException
                            except requests.exceptions.Timeout as errt:
                                error_log(errt, "Timeout Error")
                            except requests.exceptions.RequestException as err:
                                error_log(err, "Something Else")
                            except Exception as ex:
                                error_log(ex, "Exception while sending Data")

                    else:
                        print("No measurement data was send.")


                q = Queue()
                p = Process(target=measure, args=(q,))
                p.start()
                p.join()

                # stop measurements after uploading once
                if interval == 1:
                    print("Only one measurement was set => stop measurements.")
                    measurement_stop.set()

                    if shutdownAfterTransfer:
                        print("Shutting down was set => Waiting 10seconds and then shutdown.")
                        time.sleep(10)
                        shutdown()

            time.sleep(6) # wait 6 seconds

        end_time = time.time()
        time_taken = end_time - start_time # time_taken is in seconds
        time_taken_s = float("{0:.2f}".format(time_taken)) # remove microseconds
        print("Measurement-Script runtime was " + str(time_taken_s) + " seconds.")

    except MyRebootException as re:
        error_log(re, "Too many ConnectionErrors in a row => Rebooting")
        if not debug:
            time.sleep(4)
            reboot()
    except Exception as e:
        error_log(e, "Unhandled Exception while Measurement")
        if not debug:
            time.sleep(10)
            reboot()
