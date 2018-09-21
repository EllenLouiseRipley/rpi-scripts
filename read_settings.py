#!/usr/bin/env python
# This file is part of HoneyPi which is released under Creative Commons License Attribution-NonCommercial-ShareAlike 3.0 Unported (CC BY-NC-SA 3.0).
# See file LICENSE or go to http://creativecommons.org/licenses/by-nc-sa/3.0/ for full license details.

# read settings.json which is saved by rpi-webinterface
import io
import json
from pathlib import Path

def get_settings():
    filename = "/var/www/html/backend/settings.json"
    my_file = Path(filename)
    settings = {}

    try:
        my_abs_path = my_file.resolve()
    except FileNotFoundError:
        # doesn"t exist => default values
        settings["button_pin"] = 17

    else:
        # exists => read values from file
        with io.open(filename, encoding="utf-8") as data_file:
            settings = json.loads(data_file.read())

        return settings

# get sensors by type
def get_sensors(type):
    settings = get_settings()
    try:
        all_sensors = settings["sensors"]
    except TypeError:
        # doesn"t exist => return empty array
        return []

    sensors = [x for x in all_sensors if x["type"] == type]
    # not found => return empty array
    if len(sensors) < 1:
        return []
    else:
        return sensors