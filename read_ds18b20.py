#!/usr/bin/env python
# This file is part of HoneyPi which is released under Creative Commons License Attribution-NonCommercial-ShareAlike 3.0 Unported (CC BY-NC-SA 3.0).
# See file LICENSE or go to http://creativecommons.org/licenses/by-nc-sa/3.0/ for full license details.

# read temperature from DS18b20 sensor
import math
import numpy
from pprint import pprint

unfiltered_values = [[]] # here we keep all the unfilteres values
filtered_temperature = [[]]  # here we keep the temperature values after removing outliers

def measure_temperature(device_id):
    # read 1-wire slave file
    file = open('/sys/bus/w1/devices/' + device_id + '/w1_slave')
    file_content = file.read()
    file.close()

    # read temperature and convert temperature
    string_value = file_content.split("\n")[1].split(" ")[9]
    temperature = float(string_value[2:]) / 1000

    return float('%6.2f' % temperature)

# function for reading the value from sensor
def read_unfiltered_temperatur_values(sensorIndex, sensor):
    temperature = None
    try:
        temperature = measure_temperature(sensor["device_id"])
        print("temperature: " + str(temperature))

        if math.isnan(temperature) == False:
            unfiltered_values[sensorIndex].append(temperature)

    except IOError:
        print "IOError occurred: Maybe wrong Device-ID"    
    except TypeError:
        print "TypeError occurred"

# function which eliminates the noise by using a statistical model
# we determine the standard normal deviation and we exclude anything that goes beyond a threshold
# think of a probability distribution plot - we remove the extremes
# the greater the std_factor, the more "forgiving" is the algorithm with the extreme values
def filter_values(unfiltered_values, std_factor=2):
    mean = numpy.mean(unfiltered_values)
    standard_deviation = numpy.std(unfiltered_values)

    if standard_deviation == 0:
        return unfiltered_values

    final_values = [element for element in unfiltered_values if element > mean - std_factor * standard_deviation]
    final_values = [element for element in final_values if element < mean + std_factor * standard_deviation]

    return final_values

# function for appending the filter
def filter_temperatur_values(sensorIndex):
    # read the last 9 values
    # and filter them
    filtered_temperature[sensorIndex].append(numpy.mean(filter_values([x for x in unfiltered_values[sensorIndex][-9:]])))

def checkIfSensorExistsInArray(sensorIndex):
    try:
        filtered_temperature[sensorIndex]
    except IndexError:
        # handle this
        filtered_temperature.append([])
        unfiltered_values.append([])