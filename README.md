
# Home Assistant Xiaomi Rooted Vacuum live map

## Thanks :
Special thanks to dustcloud project https://github.com/dgiese/dustcloud for giving method for rooting devices and also the base of my application to build the robot map.


## Requirement

What tou need :

- A Rooted Xiaomi Vacuum cleaner
- Home Assistant installed and configured
- Appdaemon running and plugged to home assistant
- python pillow package installed (needed for appdaemon app, in appdaemon venv if you installed it that way)

## Installation

### Create secret entries
```
xiaomi_vacuum_token: <token | used by HA>
xiaomi_vacuum_host: <host or IP | used by HA and AD>
xiaomi_vacuum_map_generated: <file path of output image | used by AD>
xiaomi_vacuum_map_base: <file path of input image as background | used by AD>
```

xiaomi_vacuum_map_base will define where you put the background image (ie the 2D floorplan of your house)
xiaomi_vacuum_map_generated will define where the generated map will bestored. Put it somewhere so that HA can use it as a local camera (see example in my package vacumm.yaml)

### Connectivity
Ensure that the user running appdaemon can connect to your robot
This means that appdaemon users has an SSH key that is allowed to connect as root to the robot

### Hass Configuration
Create at least those 3 input_number :
```
input_number:
  vacuum_mapbuilder_ratio:
    min: 0
    max: 100
    mode: box
    step: 0.001
  vacuum_mapbuilder_dock_x:
    min: 0
    max: 9999
    mode: box
  vacuum_mapbuilder_dock_y:
    min: 0
    max: 9999
    mode: box
```

### Appdaemon Configuration
Copy XiaomiVacuumCleaner.py to your appdaemon apps directory
Configure apps.yaml as follow:
```
XiaomiVacuumCleaner_MapBuilder:
module: XiaomiVacuumCleaner
class: MapBuilder
xiaomi_vacuum_host: !secret xiaomi_vacuum_host
xiaomi_vacuum_map_generated: !secret xiaomi_vacuum_map_generated
xiaomi_vacuum_map_base: !secret xiaomi_vacuum_map_base
```



## First run

Put your vacuum somewhere in your home but not docked
This will trigger the map building and image will be rebuilded every 2 seconds.

You can now adjust setting by changing in HA the input_numbers defined previously.
vacuum_mapbuilder_dock_x & vacuum_mapbuilder_dock_x: define the position of the vacuum when docked on your background image (in pixel)
vacuum_mapbuilder_ratio : define the ration to upscale / downscale the vacuum image.

Keep in mind the vacuum map is pretty low definition, in my house, I've an floorplan of 1748 × 958 and my ratio is 6.52

Each time you adjust setting, wait for the image to update and check everything is OK.




## How it works

AD will be listening on state change of the vacuum.
When the state of the vacuum is different from docked, it copies needed files to build the map.
Then locally, it cleans, upscales the vacuum map, draw the vacuum path and merge the background image
