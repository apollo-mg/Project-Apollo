
## Benefits:

### 1. High temperature

Because only the Coil is installed on the hotend, and all of other electronics are in the mainboard box.

there is no substantial difference between V1.3 and bdsensorM. they share the same electronic schematic and firmware, except the connector and length of wire to the coil.

### 2. Only 1.5g

It is the lightest probe for only the small coil is installed on the hotend with a very small cable (diameter:1.8mm, length:1.5meter) into the mainboard.




## How to install:

There are two ways to connect the BDsensorM to your mainboard:

1. With EXP1 connector(recommend). make sure the 5V,GND,SCK,SDA pin are in the right order. 
e.g.

![](https://raw.githubusercontent.com/markniu/Bed_Distance_sensor/new/doc/images/exp1_connect.jpg) 

2. With the white connector like the normal BDsensorV1.3
e.g.

![](https://raw.githubusercontent.com/markniu/Bed_Distance_sensor/new/doc/images/connect_white.jpg) 

### Note:
 1. We can only use the exp1 or white connector, please don't connect both the exp1 and white connector to the mainboard.
 2. The black cable is original designed for the IPEX wireless antenna, it is a little stiff, please don't bend it too much.
 3. the order number of the pins maybe different, please see the actual text string on the sensor. https://github.com/markniu/Bed_Distance_sensor/issues/178#issuecomment-2319621934