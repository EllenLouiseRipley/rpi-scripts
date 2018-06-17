import os
from signal import pause

import RPi.GPIO as GPIO
from gpiozero import Button # sudo apt install python3-gpiozero

from read_settings import get_settings
from read_and_upload_all import start_read_and_upload_all, stop_read_and_upload_all

settings = get_settings()

gpio = settings["button_pin"] # SET GPIO Button-Pin
button = Button(gpio)  # value is the GPIO pin

i = 0
os.system("sudo ifconfig wlan0 down")


def start_ap():
    os.system("sudo ifconfig wlan0 up")
    i = 1


def shutdown_ap():
    os.system("sudo ifconfig wlan0 down")
    i = 0


def main():
    while True:
        if i == 0:
            start_read_and_upload_all()
            button.when_pressed = start_ap
            pause()
        else:
            stop_read_and_upload_all()
            button.when_pressed = shutdown_ap
            pause()


if __name__ == '__main__':
    try:
        main()

    except (KeyboardInterrupt, SystemExit):
        stop_read_and_upload_all()
