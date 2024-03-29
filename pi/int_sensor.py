import smbus2
import time
import json
import paho.mqtt.client as mqtt
from gpiozero import LED,Button

def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))
    client.subscribe("IC.embedded/Erasmus/user")
    client.subscribe("IC.embedded/Erasmus/ext_sensor")

def on_message(client, userdata, msg):
	print("a msg received")
	msg.payload = msg.payload.decode("utf-8")	

	global desired_temp
	global min_humid
	global max_humid
	global mode
	global enable   #1 is on
	if msg.topic == "IC.embedded/Erasmus/user":
		print("msg received from user: ",msg.payload)
		desired_temp, min_humid, max_humid, mode, enable = msg.payload.split(',')

		desired_temp = float(desired_temp)
		min_humid = float(min_humid)
		max_humid = float(max_humid)
		enable = int(enable)
		mode = int(mode)
		print("desired temp received: ",desired_temp)
		print("min_humid: ",min_humid)
		print("max_humid: ",max_humid)
		if(enable == 0):
			mode = 5
		print("received mode: ",mode)

	global ext_temp
	global ext_humid
	global ext_tvoc

	if msg.topic == "IC.embedded/Erasmus/ext_sensor":
		print("msg received from ext sensor: ",msg.payload)
		ext_temp,ext_humid,ext_tvoc = msg.payload.split(",")
		ext_temp = float(ext_temp)
		ext_humid = float(ext_humid)
		ext_tvoc = float(ext_tvoc)

def setup_aq_sensors():
    #air quality
    meas_co2 = smbus2.i2c_msg.write(0x5A,[0x00])
    bus.i2c_rdwr(meas_co2)
    read_result  = smbus2.i2c_msg.read(0x5A, 1)
    bus.i2c_rdwr(read_result)
    meas_co2 = smbus2.i2c_msg.write(0x5A, [0xF4])
    bus.i2c_rdwr(meas_co2)

    meas_co2 = smbus2.i2c_msg.write(0x5A,[0x00])
    bus.i2c_rdwr(meas_co2)
    read_result  = smbus2.i2c_msg.read(0x5A, 1)
    bus.i2c_rdwr(read_result)
    print("air quality: Entering application mode") 
    meas_co2 = smbus2.i2c_msg.write(0x5A, [0x01,0b00011000 ])
    bus.i2c_rdwr(meas_co2)

    meas_co2 = smbus2.i2c_msg.write(0x5A,[0x00])
    bus.i2c_rdwr(meas_co2)
    read_result  = smbus2.i2c_msg.read(0x5A, 1)
    bus.i2c_rdwr(read_result)
    print("Entering measuring mode")

def read_humid(curr_humid):
    bus.i2c_rdwr(meas_humid)
    time.sleep(0.1)
    read_result = smbus2.i2c_msg.read(0x40,2)
    bus.i2c_rdwr(read_result)

    humid = int.from_bytes(read_result.buf[0]+read_result.buf[1],'big')
    new_humid = (125*humid/65536)-6
    if new_humid>=0 and new_humid<=80:
        return new_humid
    else:
        print("invalid humidity")
        return curr_humid

def read_temp(curr_temp):
    bus.i2c_rdwr(meas_temp)
    time.sleep(0.1)
    read_result = smbus2.i2c_msg.read(0x40,2)
    bus.i2c_rdwr(read_result)

    temp = int.from_bytes(read_result.buf[0]+read_result.buf[1],'big')
    new_temp = (175.72*temp/65536)-46.85
    if new_temp>=-10 and new_temp <=85:
        return new_temp
    else:
        print("invalid temp")
        return curr_temp

def read_tvoc(curr_tvoc):
    meas_co2 = smbus2.i2c_msg.write(0x5A,[0x02])
    bus.i2c_rdwr(meas_co2)
    read_result  = smbus2.i2c_msg.read(0x5A, 8)
    bus.i2c_rdwr(read_result)
    tvoc_high = (int.from_bytes(read_result.buf[2],'big')&(0b01111111))*256
    tvoc_low = int.from_bytes(read_result.buf[3],'big')
    new_tvoc = tvoc_high + tvoc_low
    if new_tvoc>=0 and new_tvoc<=1187:
        return new_tvoc
    else:
        print("invalid tvoc")
        return curr_tvoc

def process_data(mode,desired_temp,min_humid,max_humid,int_temp,ext_temp,int_humid,ext_humid,int_tvoc,ext_tvoc,window_status,heater_status,ac_status):

    #default values
    w_t = 0.6
    w_h = 0.2
    w_a = 0.2
    temp_thresh = 5

    if mode == 0 :
        print("mode: default")
    elif mode == 1 :
        print("mode: energy save")
        temp_thresh = 9999   #infinite
    elif mode == 2 :
        print("mode: temp priority")
        temp_thresh = 2
    elif mode == 3 :
        print("mode: air quality priority")
        w_t = 0.4
        w_h = 0.2
        w_a = 0.4
    elif mode == 4 :
        print("mode: humidity priority")
        w_t = 0.4
        w_h = 0.4
        w_a = 0.2
    elif mode == 5 :
        print("mode: control system off") 
        w_t = 0
        w_h = 0
        w_a = 0
        temp_thresh = 9999            #infinite  

    temp_cont = abs(int_temp - desired_temp) - abs(ext_temp - desired_temp)
    temp_cont = (temp_cont*100)/95    #range is -10 to 85

    if(int_humid<min_humid):
        int_humid_cont = min_humid - int_humid
    elif(int_humid>max_humid):
        int_humid_cont = int_humid - max_humid
    else:
        int_humid_cont = 0

    if(ext_humid<min_humid):
        ext_humid_cont = min_humid - ext_humid
    elif(ext_humid>max_humid):
        ext_humid_cont = ext_humid - max_humid
    else:
        ext_humid_cont = 0

    humid_cont = ext_humid_cont - int_humid_cont
    humid_cont = (humid_cont*100)/80   #range is 0 to 80

    air_cont =   ext_tvoc - int_tvoc
    air_cont = (air_cont*100)/1187    #range is 0 to 1187

    #desired temp achiveable without ac/heater
    temp_achievable = ((abs(int_temp - desired_temp))<temp_thresh) or ((abs(ext_temp - desired_temp))<temp_thresh)

    #negative value mean inside better -> close window
    window = w_t * temp_cont + w_h * humid_cont + w_a * air_cont

    if(temp_achievable):
        ac_status = "off"
        heater_status = "off"
    elif(temp_achievable==0):
        if(int_temp-desired_temp)<0:
            ac_status = "off"
            heater_status = "on"
        else:
            ac_status = "on"
            heater_status = "off"

    #so window doesnt reapetedly open/close at threshold
    if(window<-3):
        window_status = "open"
    elif(window>3):
        window_status = "closed"
    return window_status, heater_status, ac_status


def set_io(window_status,ac_status,heater_status):
    print("setting io")
    if window_status == "open":
        led_window.on()
    else:
        led_window.off()

    if ac_status == "on":
        led_ac.on()
    else:
        led_ac.off()

    if heater_status == "on":
        led_heater.on()
    else:
        led_heater.off()

#setup I2c
bus = smbus2.SMBus(1)

#air quality
setup_aq_sensors()

time.sleep(0.5)

#setup mqtt
client = mqtt.Client()
client.tls_set(ca_certs="mosquitto.org.crt", certfile="client.crt",keyfile="client.key")
client.on_connect = on_connect
client.on_message = on_message
client.connect("test.mosquitto.org",port=8884)
client.loop_start()

#humidity and temperature read
meas_humid = smbus2.i2c_msg.write(0x40,[0xe5])
meas_temp = smbus2.i2c_msg.write(0x40,[0xe0])

#initialise values
mode = 0
desired_temp = 24
min_humid = 30
max_humid = 50
ext_temp = 20
ext_humid = 40
ext_tvoc = 0
heater_status = "off"
ac_status = "off"
window_status = "open"  #0 is open
int_temp = 0
int_humid = 0
int_tvoc = 0

#initialize io
led_window = LED(24)  #green led
led_ac = LED(23)      #left led
led_heater = LED(10)  #top led
switch = Button(17)

while(1):
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    int_temp = read_temp(int_temp)
    int_humid = read_humid(int_humid)
    int_tvoc = read_tvoc(int_tvoc)

    if switch.is_pressed:   #switch turns off automation
        window_status, heater_status, ac_status = process_data(5,desired_temp,min_humid,max_humid,int_temp,ext_temp,int_humid,ext_humid,int_tvoc,ext_tvoc,window_status,heater_status,ac_status)
    else:
        window_status, heater_status, ac_status = process_data(mode,desired_temp,min_humid,max_humid,int_temp,ext_temp,int_humid,ext_humid,int_tvoc,ext_tvoc,window_status,heater_status,ac_status)


    set_io(window_status,ac_status,heater_status)

    if switch.is_pressed:
        print("switch pressed")

    print("temp, humidity, tvoc, window status, ac status, heater status")
    temp = str(int_temp) + "," + str(int_humid) + "," + str(int_tvoc) + "," + window_status + "," +  ac_status + "," + heater_status 
    print("msg: ",temp)

    MSG_INFO = client.publish("IC.embedded/Erasmus/int_sensor",temp)

    time.sleep(1)

