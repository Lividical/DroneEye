"""
This is servo.py the servo python program for Jetson Orin Nano using a parallax 360 feedback servo and ADS1115 for the angle readings.

Servo controls:
	- stop() no spin
	- cw()	clockwise
	- ccw() counter clockwise
	- angle() reads the angle

"""

# imports
import Jetson.GPIO as GPIO #import of the gpio
from smbus2 import SMBus # will be used for the I2C
import time # used for the sleep function
import serial # this is used for the communication of jetson and esp32 over usb

# Constants

SERVO_CONTROL_PIN = 32 # The control pin for the servo
I2C_SDA_PIN = 27 # The SDA pin 27 for I2C
I2C_SCL_PIN = 28 # The SCL pin 28 for I2C

# Pulse widths in microseconds for the servo
PULSE_STOP = 1500
PULSE_CW   = 1435 # This number must be below 1500 and the minimum is 1280; The lower, the faster.
PULSE_KICK_CW = 1300  # This is for the initial kick due to lack of battery amperage and voltage
PULSE_CCW  = 1550 # This number must be above 1500 and the maximum is 1720; The higher, the faster
PULSE_KICK_CCW = 1700 # This is for the initial kick due to lack of battery amperage and voltage
PULSE_MIN  = 1280
PULSE_MAX  = 1720
MICRO = 1 / 1_000_000 # 10^-6 is micro seconds
PWM_FREQUENCY = 50 # 50 Hz PWM signal comes from manual of parralax 1/50 = 20,000 micro seconds of cycle time
PWM_CYCLE_TIME = (1/PWM_FREQUENCY) * (1/MICRO) # 1/50 = 0.02 * 10^6 = 20,000 micro seconds

# The pwm cycles that are intake are percentages duty cycle (PDC) (DUTYPULSE/CYCLE_TIME) * 100 = A PERCENTAGE
PDC_STOP = (PULSE_STOP/ PWM_CYCLE_TIME) * 100
PDC_CW =  (PULSE_CW/ PWM_CYCLE_TIME) * 100
PDC_KICK_CW = (PULSE_KICK_CW/ PWM_CYCLE_TIME) * 100
PDC_CCW = (PULSE_CCW/ PWM_CYCLE_TIME) * 100
PDC_KICK_CCW = (PULSE_KICK_CCW/ PWM_CYCLE_TIME) * 100
PDC_MIN = (PULSE_MIN/ PWM_CYCLE_TIME) * 100
PDC_MAX = (PULSE_MAX/ PWM_CYCLE_TIME) * 100

KICK_TIME = 0.2 # Choosen time to kick the motor raise or lower if needed.

# For the ADC (ADS1115) constants
ADC_ADDR = 0x48 # this is found by reading the i2c and seeing what address was recieving data
ADC_REG = 0x00 #where to put the results
ADC_REG_CONFIG = 0x01 #setting the reg
ADC_CONFIG = 0xF383 # setting up the settings. use A3 register, +/- 4.096V mode since 3.3v, single reading mode, and 128 samples per second which is 1/128 = 0.0078 < 0.01 time we wait which is good

# since we have 16 bits and 1 is signed part 16-1
# output will be from 0V - 4.096V so 3.3V/4.096V = 0.80566 * 2^(16-1) = 26400 -1 = 26399 but for error i'll keep it 26400 which in hex is 0x6720
ADC_MAX = 0x6720

# ESP 32 communincation constants
SERIAL_PORT = "/dev/ttyUSB0" # found when I checked what is the pathway to usb being plugged in
SERIAL_BAUD = 115200 # this is the baud rate set on both sides for communications

# global variables to use add global "" in begining of each function
ser = None # currently serial is nothing at the start will be set in init_servo
i2c_bus = None # Currently i2c_bus is nothing at the start and will be set in init_ADC

def init_servo():
	"""
	Initializing the Jetson GPIO
	"""
	global ser

	# set up the serial line to send the PDC
	ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=1) # set up the serial line
	time.sleep(2) # give time to setup serial line
	stop() # stop motor at start

	init_ADC()

# The following 3 funcitons set up stop, cw, ccw for the servo control pin pwm
def stop():
	send_duty(PDC_STOP) # Kickstart the servo

def cw():
#	send_duty(PDC_KICK_CW) # Kickstart the servo
#	time.sleep(KICK_TIME) # Wait the aloted time for it to kick start
	send_duty(PDC_CW) # Normal spin

def ccw():
#	send_duty(PDC_KICK_CCW) # Kickstart the servo
#	time.sleep(KICK_TIME) # Wait the aloted time for it to kick start
	send_duty(PDC_CCW) # Normal spin

def send_duty(duty):
	"""
	this will send the duty cycle to the esp32
	"""
	ser.write(f"{duty}\n".encode()) # encodes the data so it is bytes and sends the data to the esp32
	ser.flush() # tells the system to immediately send it not buffer it.

def init_ADC():
	"""
	Setting up the ADC
	"""
	global i2c_bus
	i2c_bus = SMBus(1) # makes i2c_bus object

def angle():
	"""
	start conversation, wait a second for it to talk, read the results, and convert it to a degree
	"""
	i2c_bus.write_word_data(ADC_ADDR, ADC_REG_CONFIG, swap_bytes(ADC_CONFIG)) #setting up the settings for it  to start writing
	
	time.sleep(0.01) # give time to write results
	
	output = i2c_bus.read_word_data(ADC_ADDR, ADC_REG) # read the results
	output = swap_bytes(output) # the results come in backwards


	# since it is a signed number lets do the conversion if it is higher than 0x7FFF then it is negative so output - 2^16 = negative output
	if (output > 0x7FFF):
		output -= 0x10000
	
	# output will be from 0V - 4.096V so 
	degree = (output / ADC_MAX) * 360 # turn into degree
	
	if(degree>360):  # we are over add limiter
		degree = 360
	if(degree<0): # we are under add limiter
		degree = 0

	return degree

def swap_bytes(value):
	# helper function that will the two bytes
	return ((value & 0xFF) << 8) | ((value >> 8) & 0xFF)
	

	
	
