#!/usr/bin/env python3
# This file is part of HoneyPi [honey-pi.de] which is released under Creative Commons License Attribution-NonCommercial-ShareAlike 3.0 Unported (CC BY-NC-SA 3.0).
# See file LICENSE or go to http://creativecommons.org/licenses/by-nc-sa/3.0/ for full license details.

import superglobal
import sys
import threading
import time
import logging
from logging.handlers import RotatingFileHandler

import RPi.GPIO as GPIO

from read_and_upload_all import start_measurement
from read_settings import get_settings, get_sensors
from utilities import scriptsFolder, logfile, stop_tv, stop_led, toggle_blink_led, start_led, stop_hdd_led, start_hdd_led, reboot, client_to_ap_mode, ap_to_client_mode, blink_led, miliseconds, shutdown, delete_settings, getStateFromStorage, setStateToStorage, update_wittypi_schedule, connect_internet_modem, get_default_gateway_linux, get_interface_upstatus_linux, get_pi_model, get_rpiscripts_version, runpostupgradescript, check_undervoltage, sync_time_ntp, offlinedata_prepare, check_wittypi, set_wittypi_rtc, fix_fileaccess, whoami

from multiprocessing import Process, Queue, Value
from OLed import oled_off, oled_start_honeypi,oled_diag_data,oled_interface_data, oled_init, main, oled_measurement_data, oled_maintenance_data, oled_view_channels
from read_gps import init_gps, timesync_gps
logger = logging.getLogger('HoneyPi.main')

# global vars
superglobal = superglobal.SuperGlobal()
measurement = None
settings = {}
isActive = 0 # flag to know if measurement is active or not
measurement_stop = threading.Event() # create event to stop measurement
time_rising = 0 # will be set by button_pressed event if the button is rised
# the following will be overwritten by settings.json:
debug = 0
GPIO_BTN = 16
GPIO_LED = 21 # GPIO for led
LED_STATE = 0

def oled():
    global settings
    oled_init()
    oled_start_honeypi()
    time.sleep(4)
    oled_diag_data()
    time.sleep(4)
    oled_measurement_data()
    time.sleep(4)
    oled_interface_data()
    ts_channels = settings["ts_channels"]
    oled_view_channels(offlinedata_prepare(ts_channels))
    time.sleep(4)
    oled_maintenance_data(settings)
    if not superglobal.isMaintenanceActive:
        oled_off()
    return

def timesync(settings, wittypi_status):
    try:
        strntptimediff=sync_time_ntp()
        ntptimediff = 0
        ntptimediff= abs(int(float(strntptimediff.replace("s",""))))
        if ntptimediff >= 60:
            logger.critical('Time syncronized to NTP - diff: ' + ntptimediff + ' was more than 60seconds')
            set_wittypi_rtc(settings, wittypi_status)
        else:
            logger.info('Time syncronized to NTP - diff: ' + strntptimediff)
    except Exception as ex:
        logger.exception("Exception in timesync" + str(ex))
    return False

def gpstimesync(gpsSensor, blank=None):
    try:
        timesync_gps(gpsSensor)
    except Exception as ex:
        logger.exception("Exception in gpstimesync" + str(ex))
    return False

def start_ap():
    global isActive, GPIO_LED, settings
    start_led(GPIO_LED)
    t1 = threading.Thread(target=client_to_ap_mode)
    t1.start()
    t1.join()
    isActive = 1 # measurement shall start next time
    logger.info(">>> Connect yourself to HoneyPi-AccessPoint Wifi")
    superglobal.isMaintenanceActive=True
    start_led(GPIO_LED)
    #isMaintenanceActive=setStateToStorage('isMaintenanceActive', True)
    if settings['display']['enabled']:
        oled_init()
        oled_maintenance_data(settings)

def stop_ap():
    global isActive, GPIO_LED, settings
    stop_led(GPIO_LED)
    t2 = threading.Thread(target=ap_to_client_mode)
    t2.start()
    t2.join()
    isActive = 0 # measurement shall stop next time
    superglobal.isMaintenanceActive=False
    #isMaintenanceActive=setStateToStorage('isMaintenanceActive', False)
    if settings['display']['enabled']:
        oled_off()

def get_led_state(self):
    global GPIO_LED, LED_STATE
    LED_STATE = GPIO.input(GPIO_LED)
    return LED_STATE

def close_script():
    global measurement_stop
    measurement_stop.set()
    print("Exit!")
    GPIO.cleanup()
    sys.exit()

def toggle_measurement():
    global isActive, measurement_stop, measurement, GPIO_LED
    if isActive == 0:
        logger.info(">>> Button was pressed: Stop measurement / start AccessPoint")
        # stop the measurement by setting event's flag
        measurement_stop.set()
        start_ap() # finally start AP
    elif isActive == 1:
        logger.info(">>> Button was pressed: Start measurement / stop AccessPoint")
        if measurement.is_alive():
            logger.warning("Thread should not be active anymore")
        # start the measurement by clearing event's flag
        measurement_stop.clear() # reset flag
        measurement_stop = threading.Event() # create event to stop measurement
        measurement = threading.Thread(target=start_measurement, args=(measurement_stop,))
        measurement.start() # start measurement
        stop_ap() # finally stop AP
    else:
        logger.error("Button press recognized but undefined state of Maintenance Mode")
    # make signal, that job finished
    tblink = threading.Thread(target=toggle_blink_led, args = (GPIO_LED, 0.2))
    tblink.start()

def button_pressed(channel):
    global GPIO_BTN, LED_STATE, GPIO_LED
    LED_STATE = get_led_state(GPIO_LED)
    if GPIO.input(GPIO_BTN): # if port == 1
        button_pressed_rising("button_pressed")
    else: # if port != 1
        button_pressed_falling("button_pressed")

def button_pressed_rising(self):
    global time_rising, debug, GPIO_LED, LED_STATE
    time_rising = miliseconds()

    logger.debug("button_pressed_rising")

def button_pressed_falling(self):
    global time_rising, debug, GPIO_LED, LED_STATE, settings
    time_falling = miliseconds()
    logger.debug("button_pressed_falling")
    time_elapsed = time_falling-time_rising
    time_rising = 0 # reset to prevent multiple fallings from the same rising
    logger.debug("Button was pressed for: " + str(time_elapsed) + " miliseconds")

    MIN_TIME_TO_ELAPSE = 50
    MAX_TIME_TO_ELAPSE_OLED = 500 # miliseconds
    MAX_TIME_TO_ELAPSE_MAINTENANCE = 3000
    MIN_TIME_TO_ELAPSE_SHUTDOWN = 5000
    MAX_TIME_TO_ELAPSE_SHUTDOWN = 10000
    MAX_TIME_TO_ELAPSE_RESET = 15000
    
    if time_elapsed >= 0 and time_elapsed <= 30000:
        if time_elapsed > MIN_TIME_TO_ELAPSE and time_elapsed <= MAX_TIME_TO_ELAPSE_OLED:
            if settings['display']['enabled']:
                pOLed = threading.Thread(target=oled, args=())
                pOLed.start()
        elif time_elapsed > MAX_TIME_TO_ELAPSE_OLED and time_elapsed <= MAX_TIME_TO_ELAPSE_MAINTENANCE:
            # normal button press to switch between measurement and maintenance
            tmeasurement = threading.Thread(target=toggle_measurement)
            tmeasurement.start()
        elif time_elapsed > MIN_TIME_TO_ELAPSE_SHUTDOWN and time_elapsed <= MAX_TIME_TO_ELAPSE_SHUTDOWN:
            # shutdown raspberry
            tblink = threading.Thread(target=blink_led, args = (GPIO_LED, 0.1))
            tblink.start()
            logger.critical("Shutting down because button was pressed more than "+ str(MIN_TIME_TO_ELAPSE_SHUTDOWN/1000) + " seconds.")
            shutdown(settings)
        elif time_elapsed > MAX_TIME_TO_ELAPSE_SHUTDOWN and time_elapsed <= MAX_TIME_TO_ELAPSE_RESET:
            if settings["enable_reset"]:
                # reset settings and shutdown
                tblink = threading.Thread(target=blink_led, args = (GPIO_LED, 0.1))
                tblink.start()
                delete_settings()
                update_wittypi_schedule("")
                logger.critical("Resetting settings and shutting down because button was pressed more than "+ str(MAX_TIME_TO_ELAPSE_SHUTDOWN/1000) + "seconds.")
                shutdown(settings)
            else:
                logger.critical("Button was pressed more than 10 seconds but NOT resetting settings and shutting down because feature disabled in webinterface.")
        else:
            time_elapsed_s = float("{0:.2f}".format(time_elapsed/1000)) # ms to s
            logger.warning("Too short Button press, Too long Button press OR inteference occured. Button was pressed for: " + str(time_elapsed_s) + "s.")

def main():
    try:
        global isActive, measurement_stop, measurement, debug, GPIO_BTN, GPIO_LED, settings

        # Zaehlweise der GPIO-PINS auf der Platine
        GPIO.setmode(GPIO.BCM)

        # read settings for number of GPIO pin
        settings = get_settings()
        debuglevel=int(settings["debuglevel"])
        debuglevel_logfile=int(settings["debuglevel_logfile"])

        logger = logging.getLogger('HoneyPi')
        logger.setLevel(logging.DEBUG)
        try:
            fh = RotatingFileHandler(logfile, maxBytes=5*1024*1024, backupCount=60)
        except PermissionError:
            #set file access
            fix_fileaccess(scriptsFolder + '/err*.*')
            fh = RotatingFileHandler(logfile, maxBytes=5*1024*1024, backupCount=60)

        fh.setLevel(logging.getLevelName(debuglevel_logfile))
        # create console handler with a higher log level
        ch = logging.StreamHandler()
        ch.setLevel(logging.getLevelName(debuglevel))
        # create formatter and add it to the handlers
        formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(name)s | %(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        # add the handlers to the logger
        logger.addHandler(fh)
        logger.addHandler(ch)

        time.sleep(1)

        if debuglevel <= 10:
            debug = True # flag to enable debug mode (HDMI output enabled and no rebooting)
        else:
            debug = False # flag to enable debug mode (HDMI output enabled and no rebooting)

        if debuglevel > 20:
            # stop HDMI power (save energy)
            logger.info('HoneyPi '+ get_rpiscripts_version() + ' Started on ' + get_pi_model() + ' as User ' + whoami() + ', Debuglevel: "' + logging.getLevelName(debuglevel) + '", Debuglevel logfile: "' + logging.getLevelName(debuglevel_logfile)+'"')
            stop_tv()
            stop_hdd_led()
        else:
            logger.info('HoneyPi '+ get_rpiscripts_version() + ' Started on ' + get_pi_model() + ' as User ' + whoami())
            start_hdd_led()
        q = Queue()
        if settings['display']['enabled']:
            tOLed = threading.Thread(target=oled, args=())
            tOLed.start()

        # check wittypi
        wittypi_status = check_wittypi(settings)
        
        gpsSensors = get_sensors(settings, 99)
        for (sensorIndex, gpsSensor) in enumerate(gpsSensors):
            init_gps(gpsSensor)
            tgpstimesync = threading.Thread(target=gpstimesync, args=(gpsSensor, None))
            tgpstimesync.start()
            break


        if settings["offline"] != 3:
            ttimesync = threading.Thread(target=timesync, args=(settings, wittypi_status))
            ttimesync.start()
        else:
            logger.debug('Offline mode - no time syncronization to NTP')

        runpostupgradescript()

        GPIO_BTN = settings["button_pin"]
        GPIO_LED = settings["led_pin"]

        # setup LED as output
        try:
            GPIO.setup(GPIO_LED, GPIO.OUT)
        except RuntimeError as ex:
            logger.critical("RuntimeError occuered on GPIO setup! Honeypi User '"+ whoami() + "' does not have access to GPIO!") # + str(ex))
            if not debug:
                time.sleep(60)
                reboot(settings)

        # blink with LED on startup
        tblink = threading.Thread(target=blink_led, args = (GPIO_LED,))
        tblink.start()

        # Call wvdial for surfsticks
        connect_internet_modem(settings)

        # check undervoltage for since system start
        check_undervoltage()

        
        # setup Button
        try:
            GPIO.setup(GPIO_BTN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # Set pin 16 to be an input pin and set initial value to be pulled low (off)
        except RuntimeError as ex:
            logger.critical("RuntimeError occuered on GPIO setup! Honeypi User '"+ whoami() + "' does not have access to GPIO!") # + str(ex))
            if not debug:
                time.sleep(60)
                reboot(settings)
        bouncetime = 100 # ignoring further edges for 100ms for switch bounce handling
        # register button press event
        GPIO.add_event_detect(GPIO_BTN, GPIO.BOTH, callback=button_pressed, bouncetime=bouncetime)

        #if settings['display']['enabled']:
        #    tOLed.join()

        if len(gpsSensors) >= 1:
            tgpstimesync.join(timeout=20)

        if settings["offline"] != 3:
            ttimesync.join(timeout=20)

        # start as seperate background thread
        # because Taster pressing was not recognised
        superglobal.isMaintenanceActive=False
        #isMaintenanceActive=setStateToStorage('isMaintenanceActive', False)
        measurement_stop = threading.Event() # create event to stop measurement
        measurement = threading.Thread(target=start_measurement, args=(measurement_stop,))
        measurement.start() # start measurement

        # Main Lopp: Cancel with STRG+C
        while True:
            time.sleep(0.2)  # wait 200 ms to give CPU chance to do other things
            pass

        print("This text will never be printed.")

    except Exception as ex:
        logger.critical("Unhandled Exception in main: " + repr(ex))
        if not debug:
            time.sleep(60)
            reboot(settings)

if __name__ == '__main__':
    try:
        main()

    except (KeyboardInterrupt, SystemExit):
        close_script()

    except Exception as ex:
        logger.exception("Unhandled Exception in __main__ ")
        #if not debug:
            #time.sleep(60)
            #reboot()
