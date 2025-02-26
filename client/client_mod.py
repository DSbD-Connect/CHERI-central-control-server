#!/usr/bin/python3

import time, threading, socket, fcntl, struct, uuid

#------------------------------------------------------#
device_name = None

# if server_reg_ip is not None, then multicast server discovery is bypassed and registration
# requests are sent directly to the given address
#
# if iface_name is not None, the client attempts to resolve iface_name to an ip address
# and uses this ip address for all local sockets (including multicast, if relevant)
#
# if both server_reg_ip and iface_name are None, the client sends multicast server
# discovery messages without setting a source ip address to use
server_reg_ip = None
iface_name = None

int_field_names = []
float_field_names = []
bool_field_names = []
str_field_names = []

update_freq = 60
update_func = None

show_messages_received = True

commands = {}
# keys are command names
# entry for cmd-name is [X,Y]
# where X is dictionary of param names to types (as strings)
# and Y is command handler, which should accept a single argument
# the single argument is a dictionary of param name to param value

#------------------------------------------------------#

_goodbyes_sent = 0

_exit_main_loop = False
def main_loop_exit():
        global _exit_main_loop
        _exit_main_loop = True

_MCAST_GRP = '239.255.73.81'
_MCAST_PORT = 5025
_PROTO_PORT = 5026

_REGSTATE_DONTCARE = 0        # not registered, don't care if we know server ip (eg for shutdown)
_REGSTATE_SERVER_UNKNOWN = 1  # not registered, don't know server ip
_REGSTATE_SERVER_KNOWN = 2    # not registered, do know server ip
_REGSTATE_REGISTERED = 3      # registered

def main_loop():
        global _stop_updates_thread, _goodbyes_sent

        if None in [device_name, update_func]:
                print('ERROR: device_name, update_func must be provided')
                return

        connection_id = str(uuid.uuid1())
        reg_request = f"REG|{device_name}|{connection_id}|fields"
        for name_list,field_type in [[int_field_names,'int'],[float_field_names,'float'],[str_field_names,'str'],[bool_field_names,'bool']]:
                for field_name in name_list:
                        reg_request = reg_request + f':{field_name}={field_type}'
        for command_name in commands:
                params = commands[command_name][0]
                reg_request = reg_request + f'|{command_name}'
                for param_name,param_type in params.items():
                        reg_request = reg_request + f':{param_name}={param_type}'
        reg_request_bytes = reg_request.encode('utf-8')

        local_ip_addr = None
        if iface_name != None:
                local_ip_addr = iface_name_to_ip(iface_name)
                if (local_ip_addr == None) or (local_ip_addr.count('.') != 3): # yuck!
                        print(f"could not resolve interface name {iface_name} to an ip address")
                        quit()
                print(f"resolved iface name {iface_name} to {local_ip_addr}")
        
        if server_reg_ip == None:
                sock_out_mcast = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
                if local_ip_addr != None:
                        sock_out_mcast.setsockopt(socket.SOL_IP,socket.IP_MULTICAST_IF,socket.inet_aton(local_ip_addr))

        sock_in = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if local_ip_addr == None:
                sock_in.bind(("",_PROTO_PORT))
        else:
                sock_in.bind((local_ip_addr,_PROTO_PORT))
        sock_in.settimeout(7)

        sock_out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if local_ip_addr != None:
                sock_out.bind((local_ip_addr,0))

        base_regstate = _REGSTATE_SERVER_UNKNOWN if (server_reg_ip == None) else _REGSTATE_SERVER_KNOWN
        regstate = base_regstate
        server_ip = server_reg_ip   #RHS is None if there is no fixed server ip to register at

        updates_thread = None
        updates_thread_cond = threading.Condition()
        fields_lock = threading.Lock()
        
        while True:
                if _exit_main_loop or (regstate != _REGSTATE_REGISTERED): 
                        if (updates_thread != None) and updates_thread.is_alive():
                                _stop_updates_thread = True
                                updates_thread_cond.acquire()
                                updates_thread_cond.notify()
                                updates_thread_cond.release()
                                updates_thread.join()
                                updates_thread = None

                if _exit_main_loop:
                        if regstate != _REGSTATE_REGISTERED:
                                break
                        if _goodbyes_sent == 3:
                                regstate = _REGSTATE_DONTCARE
                                continue
                        goodbye_request_bytes = f"GOODBYE|{device_name}|{connection_id}".encode('utf-8')
                        sock_out.sendto(goodbye_request_bytes,(server_ip,_PROTO_PORT))
                        _goodbyes_sent += 1
                else:
                        if regstate == _REGSTATE_SERVER_UNKNOWN:
                                findserver_request_bytes = f"FINDSERVER|{device_name}|---".encode('utf-8')
                                sock_out_mcast.sendto(findserver_request_bytes,(_MCAST_GRP,_MCAST_PORT))
                        if regstate == _REGSTATE_SERVER_KNOWN:
                                sock_out.sendto(reg_request_bytes,(server_ip,_PROTO_PORT))

                try:
                        data,addr = sock_in.recvfrom(1024)
                except socket.timeout:
                        continue
                msg = data.decode('utf-8')
                if show_messages_received:
                        print(f"{addr[0]} sent /{msg}/")

                msg_bits = msg.split('|')
                method = msg_bits[0]
                sender_name = msg_bits[1]
                sent_connection_id = msg_bits[2]
                method_body = msg_bits[3:]

                if method == 'REGHERE':
                        regstate = _REGSTATE_SERVER_KNOWN
                        server_ip = addr[0]
                        continue
                if (addr[0] != server_ip) or (sent_connection_id != connection_id):
                        print("  -> message has bad server_ip or connection_id, ignoring message")
                        continue
                if method == 'HELLO':
                        regstate = _REGSTATE_REGISTERED
                        updates_thread = threading.Thread(target=_updates_thread_main,
                                                          args=(server_ip,connection_id,updates_thread_cond,fields_lock,sock_out))
                        updates_thread.start()
                if regstate != _REGSTATE_REGISTERED:
                        print("  -> not registered with server, ignoring message")
                        continue
                if method == 'COMMAND':
                        command_name = method_body[0]
                        if not command_name in commands:
                                print(f"ERROR: {sender_name} at {addr[0]} sent unknown command /{command_name}/")
                                continue
                        command_param_values = {}
                        command_param_types = commands[command_name][0]
                        all_good = True
                        type_conversion_funcs = {'int': (lambda x: int(x) if x != '' else None),
                                                 'float': (lambda x: float(x) if x != '' else None),
                                                 'str':str,
                                                 'bool':bool}
                        for body_bit in method_body[1:]:
                                try:
                                        param_name,param_value_str = body_bit.split('=')
                                        param_type_str = command_param_types[param_name]
                                        command_param_values[param_name] = (type_conversion_funcs[param_type_str])(param_value_str)
                                except :
                                        print(f"ERROR: {sender_name} at {addr[0]} send bad command parameter value /{body_bit}/")
                                        all_good = False
                        if not all_good:
                                continue
                        for param_name in command_param_types:
                                if not param_name in command_param_values:
                                        command_param_values[param_name] = None
                        fields_lock.acquire()
                        (commands[command_name][1])(command_param_values)
                        fields_lock.release()
                if method in ['PROD','COMMAND']:
                        updates_thread_cond.acquire()
                        updates_thread_cond.notify()
                        updates_thread_cond.release()
                if method == 'GOODBYE':
                        regstate = base_regstate
                if method == 'ERR':
                        pass

_stop_updates_thread = False
def _updates_thread_main(server_ip, connection_id, cond, fields_lock, sock_out):
        global _stop_updates_thread
        
        while True:
                if _stop_updates_thread:
                        _stop_updates_thread = False
                        break

                fields_lock.acquire()
                update_dict = update_func()
                fields_lock.release()

                update_request = f"UPDATE|{device_name}|{connection_id}"        
                for name_list,field_type in [[int_field_names,int],[float_field_names,float],[str_field_names,str],[bool_field_names,bool]]:
                        for field_name in name_list:
                                if not isinstance(update_dict[field_name],field_type):
                                        print("Error: value {update_dict[field_name]} is not of type {field_type}")
                                        continue
                                update_request = update_request + (f'|{field_name}=') + str(update_dict[field_name])
                update_request_bytes = update_request.encode('utf-8')
                sock_out.sendto(update_request_bytes,(server_ip,_PROTO_PORT))

                cond.acquire()
                cond.wait(update_freq)
                cond.release()

def iface_name_to_ip(iface_name):
        tmp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # we need to make a struct ifreq to hand to the ioctl, see netdevice(7)
        # note that only the first 15 characters of iface_name are used
        ifreq_in = struct.pack('256s', iface_name.encode('utf-8')[:15])

        # 0x8915 is SIOCGIFADDR
        try:
                ifreq_out = fcntl.ioctl(tmp_sock.fileno(),0x8915,ifreq_in)
        except:
                return None
                
        tmp_sock.close()
        return socket.inet_ntoa(ifreq_out[20:24])



