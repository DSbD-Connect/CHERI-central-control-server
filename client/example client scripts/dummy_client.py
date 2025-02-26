#!/usr/bin/python3

# A dummy "client script" to show how to create
# a script for a client network device to be
# controlled by the central server

import socket, time, random, sys, os, threading
import client_mod

usage_string = f"Usage: {sys.argv[0]} [if_name=<if_name>] [server_ip=<server_ip>]"

if len(sys.argv) > 3:
        print(usage_string)
        quit()
for arg in sys.argv[1:]:
        try:
                optname,optval = arg.split('=')
        except ValueError:
                print(usage_string)
                quit()
        if not optname in ['if_name','server_ip']:
                print(usage_string)
                quit()
        if optname == 'if_name':
                client_mod.iface_name = optval
        if optname == 'server_ip':
                client_mod.server_reg_ip = optval

client_mod.device_name = 'test device'

temp_vals = [15,16,17,18]
setting_vals = ['sleep','monitor']

client_mod.int_field_names = ['temp']
client_mod.str_field_names = ['setting']

def update_func():
        temp = random.choice(temp_vals)
        setting = random.choice(setting_vals)
        return {'temp':temp,'setting':setting}

update_func()
client_mod.update_freq = 70

def cmd_off(params):
        print(f"Got off command")
        client_mod.main_loop_exit()

def cmd_change_setting(params):
        new_setting = params['setting']
        print(f"Got setting command, with arg /{new_setting}/")
        if new_setting != None:
                setting = new_setting

def cmd_do_a_thing(params):
        print('Got "do a thing", with parameter dict: ')
        print(params)
        

client_mod.update_func = update_func
client_mod.commands['off'] = [{},
                              cmd_off]
client_mod.commands['change setting'] = [{'setting':'str'},
                                         cmd_change_setting]
client_mod.commands['do a thing'] = [{'active':'bool','optname':'str','level':'int'},
                                     cmd_do_a_thing]

client_mod.main_loop()


