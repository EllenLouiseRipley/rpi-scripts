#!/usr/bin/env python3
# This file is part of HoneyPi [honey-pi.de] which is released under Creative Commons License Attribution-NonCommercial-ShareAlike 3.0 Unported (CC BY-NC-SA 3.0).
# See file LICENSE or go to http://creativecommons.org/licenses/by-nc-sa/3.0/ for full license details.

import RPi.GPIO as GPIO # import GPIO
import time

def setup_gpio(GPIO_PIN):
    GPIO.setmode(GPIO.BCM) # set GPIO pin mode to BCM numbering
    GPIO.setwarnings(False)
    GPIO.setup(GPIO_PIN, GPIO.OUT) # Set pin 20 to led output
    GPIO.setwarnings(True)
    # Output to pin GPIO_PIN
    GPIO.output(GPIO_PIN, 1)

def reset_gpio(GPIO_PIN):
    # Output to pin GPIO_PIN
    GPIO.output(GPIO_PIN, 0)
    time.sleep(0.1) # wait 100ms
    GPIO.output(GPIO_PIN, 1)
