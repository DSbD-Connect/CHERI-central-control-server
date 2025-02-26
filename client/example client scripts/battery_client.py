#!/usr/bin/python3

# A client script for a raspberry pi which controls
# some relay switches to control charging of a battery
# unit, and also some lights to represent an energy
# consumer

import RPi.GPIO as GPIO
import sys, time

import client_mod


GPIO.setmode(GPIO.BOARD)
GPIO.setup(7,GPIO.OUT)
GPIO.setup(11,GPIO.OUT)

client_mod.device_name = 'Power Storage and Lighting'
client_mod.server_reg_ip = 'xxx.xxx.xxx.xxx' # Needs to be filled in with
                                             # TAN address of central server
client_mod.iface_name = 'connect'


client_mod.bool_field_names = ['charging', 'lights on']
client_mod.str_field_names = ['status']


is_charging = False
is_USBon = False
status = 'ready'
GPIO.output(7,False)
GPIO.output(11,False)

def update_func():
        global is_charging, is_USBon
        return {'charging':is_charging,'lights on':is_USBon,'status':status}

update_func()
client_mod.update_freq = 20


def cmd_off(params):
        print("Got command: off")
        cmd_stop_charging({})
        GPIO.cleanup()
        print(f"Exiting")
        client_mod.main_loop_exit()

def cmd_start_charging(params):
        global is_charging
        print(f"Got command: start charging")
        is_charging=True
        GPIO.output(7,True)
        print(f"Charging started")
        status = "charging started"

def cmd_stop_charging(params):
        global is_charging
        print(f"Got command: stop charging")
        is_charging=False
        GPIO.output(7,False)
        print(f"Charging stopped")
        status = "charging stopped"

def cmd_flash_lights(params):
        global is_USBon, status
        try:
                n_flashes = int(params['num flashes'])
        except (ValueError,TypeError):
                print("Got bad flash lights command")
                return
        print(f"Got command: do {n_flashes} flashes")
        if n_flashes > 7:
                print("Will only do 7 flashes")
                n_flashes = 7
        GPIO.output(11,False)
        time.sleep(1)
        for _ in range(0,n_flashes):
                GPIO.output(11,True)
                time.sleep(0.5)
                GPIO.output(11,False)
                time.sleep(0.5)
        time.sleep(0.5)
        if is_USBon:
                GPIO.output(11,True)
        print(f"Flashes completed")
        status = f"done {n_flashes} flashes" 

def cmd_lights_on(params):
        global is_USBon
        print("Got command: turn on lights")
        is_USBon=True
        GPIO.output(11,True)
        print("lights are on")
        status = "lights turned on"

def cmd_lights_off(params):
        global is_USBon
        print("Got command: turn off lights")
        is_USBon=False
        GPIO.output(11,False)
        print("lights are off")
        status = "lights turned off"

client_mod.update_func = update_func

client_mod.commands['start charging'] = [{},
                                         cmd_start_charging]
client_mod.commands['stop charging'] = [{},
                                         cmd_stop_charging]
client_mod.commands['turn on lights'] = [{},
                                         cmd_lights_on]
client_mod.commands['turn off lights'] = [{},
                                          cmd_lights_off]
client_mod.commands['flash lights'] = [{'num flashes':'int'},
                                        cmd_flash_lights]
client_mod.commands['restart'] = [{},
                              cmd_off]

client_mod.main_loop()



