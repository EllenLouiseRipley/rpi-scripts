# rpi-scripts

HoneyPi is a measuring system based on the Raspberry Pi. It is an open source framework, which allows every beekeeper to monitor his bees. The data transfer takes place to the Internet of Things platform ThingSpeak. The measurement data is collected at the apiary and visualized in apps.


# difference to original version

sht3x script modified to deal with sht4x sensors. 

## Install

Check out the [main repo](https://github.com/Honey-Pi/HoneyPi#install) on how to install the entire measurement system on your Raspberry Pi Image with just a few commands. Or simply download a ready HoneyPi image from our [download page](https://www.honey-pi.de/downloads/). You can even create your own custom HoneyPi images using our [Raspbian image generator](https://github.com/Honey-Pi/HoneyPi-Build-Raspbian).

## Update to latest development state

1. Flash the [provided HoneyPi Image](https://www.honey-pi.de/downloads/) to your SD Card OR run our [installer](https://github.com/Honey-Pi/HoneyPi#install) which installs the webinterface and the measurement scripts to your Raspberry Pi.
2. Run the following commands to update the measurement scripts:

```
rm -rf /home/pi/HoneyPi/rpi-scripts
cd /home/pi/HoneyPi/
git clone --depth=1 https://github.com/Honey-Pi/rpi-scripts
```

Your settings won't be lost because they are stored at `/var/www/html/backend/settings.json`.

## How to Run the measurement routine

### Autostart

In previous versions the main.py was started within the `/etc/rc.local` to autostart the measurements scripts. But with the latest versions we created an systemd service which contains the call of our main.py script. This is necessary to autostart the measurement service after your Raspberry Pi booted. If you run the installer from our [main repo](https://github.com/Honey-Pi/HoneyPi#install) the autostart job is automatically added and therefore no additional action is required.

### Manually

But for manually testing you should be able to call the measurement script within your terminal as the following: `sudo python3 /home/pi/HoneyPi/rpi-scripts/main.py`
