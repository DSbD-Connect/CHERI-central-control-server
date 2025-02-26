#!/usr/bin/python3

# client script for a raspberry pi which controls
# a stepper motor which operates a syringe

from RpiMotorLib import RpiMotorLib
import RPi.GPIO as GPIO
import sys, time

import client_mod

#define GPIO pins
direction= 22 # Direction (DIR) GPIO Pin
step = 23 # Step GPIO Pin

# Declare a instance of class pass GPIO pins numbers and the motor type
mymotortest = RpiMotorLib.A4988Nema(direction, step, (-1,-1,-1), "DRV8825")

client_mod.device_name = 'Medical Demonstrator'
client_mod.iface_name = 'wlan0'


def update_func():
        return {}

update_func()
client_mod.update_freq = 20


def cmd_off(params):
        print("Got command: off")
        GPIO.cleanup()
        print(f"Exiting")
        client_mod.main_loop_exit()

def cmd_inject(params):
        try:
                n_steps = int(params['steps'])
        except (ValueError,TypeError):
                print("Got bad inject command")
                return
        print(f"Got command: inject {n_steps} steps")
        mymotortest.motor_go(False,"Full" ,n_steps,0.0001,False,0.1)
        print(f"inject completed")

def cmd_retract(params):
        try:
                n_steps = int(params['steps'])
        except (ValueError,TypeError):
                print("Got bad retract command")
                return
        print(f"Got command: retract {n_steps} steps")
        mymotortest.motor_go(True,"Full" ,n_steps,0.0001,False,0.1)
        print(f"retract completed")


client_mod.update_func = update_func
client_mod.commands['off'] = [{},
                              cmd_off]
client_mod.commands['inject'] = [{'steps':'int'},
                                    cmd_inject]
client_mod.commands['retract'] = [{'steps':'int'},
                                    cmd_retract]

client_mod.main_loop()






