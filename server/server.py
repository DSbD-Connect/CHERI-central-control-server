#!/usr/bin/python3

import socket, os, fcntl, time, threading, datetime, subprocess, struct, sys, signal
import urllib.parse

MCAST_GRP = '239.255.73.81' 
MCAST_PORT = 5025
PROTO_PORT = 5026
server_name = 'pc_server'
my_ip = None

device_timeout_secs = 120
device_prod_secs = 60

devices = []
devices_lock = threading.Lock()
page_lock = threading.Lock()

html_short_rule = '<hr style="width:20%;text-align:left;margin-left:0">'

param_type_dict = {'str':'type="text"','bool':'type="checkbox"','int':'type="number" step="1"','float':'type="number" step="0.01"'}
allowed_param_types = list(param_type_dict.keys())

def findserver_thread_main():
        sock_in_mcast = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock_in_mcast.bind((MCAST_GRP, MCAST_PORT))
        sock_in_mcast.setsockopt(socket.SOL_IP, socket.IP_ADD_MEMBERSHIP, 
                         socket.inet_aton(MCAST_GRP) + socket.inet_aton(my_ip)) 

        sock_out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        while True:
                data, addr = sock_in_mcast.recvfrom(1024)
                msg = data.decode('utf-8')
                print(f"{addr[0]} sent (multicast) /{msg}/")
                if msg.startswith("FINDSERVER|"):
                        reply = f"REGHERE|{server_name}|---"
                else:
                        reply = f"ERR|{server_name}|illegal request, expecting FINDSERVER|{msg}"
                sock_out.sendto(reply.encode('utf-8'),(addr[0],PROTO_PORT))

def server_commands_thread_cheri_main():
        server_commands_thread_real(True)

def server_commands_thread_nocheri_main():
        server_commands_thread_real(False)

cmd_log_path = 'html/command_log'
def cmd_log_print(msg,do_print=True):
        if do_print:
                print(msg)
        fh = open(cmd_log_path,'a')
        fh.write(msg+'\n')
        fh.flush()
        fh.close()

def server_commands_thread_real(use_cheri):
        if use_cheri:
                localsock_path = 'html/localsocket_cheri.socket'
                command_handler = './command_handler_cheri'
                name = 'CHERI'
        else:
                localsock_path = 'html/localsocket_nocheri.socket'
                command_handler = './command_handler_nocheri'
                name = 'NO CHERI'
        
        if os.path.exists(localsock_path):
                os.remove(localsock_path)
        fh = open(cmd_log_path,'w')
        fh.close()
        
        localsock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        localsock.bind(localsock_path)
        os.chmod(localsock_path,0o777)
        while True:
                localsock.listen(1)
                conn, addr = localsock.accept()
                command = conn.recv(1024)
                command = command.decode('utf-8')
                cmd_log_print(f"[{name}] Got POST command /{command}/")
                args = [command_handler,urllib.parse.unquote_plus(command),server_name]
                retcode = subprocess.call(args)
                if retcode in [0,1]:
                        pass
                elif retcode < 0:
                        signame = signal.Signals(-retcode).name
                        cmd_log_print(f"Command handler was terminated with signal {signame}")
                else:
                        cmd_log_print(f"Command handler exited with code {retcode}")
                cmd_log_print('',do_print=False)
                        

def device_updates_thread_main():
        sock_out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock_in = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock_in.bind(("", PROTO_PORT))

        while True:
                data,addr = sock_in.recvfrom(1024)
                msg = data.decode('utf-8')
                print(f"{addr[0]} sent /{msg}/")
                bits = msg.split('|')
                try:
                        method,device_name,connection_id = bits[0:3]
                        body_bits = bits[3:]
                except ValueError:
                        reply = f"ERR|{server_name}|---|too few fields in request|{msg}"
                        sock_out.sendto(reply.encode('utf-8'),(addr[0],PROTO_PORT))
                        continue
                if not method in ['UPDATE','GOODBYE','REG']:
                        reply = f"ERR|{server_name}|---|unknown method|{msg}"
                        sock_out.sendto(reply.encode('utf-8'),(addr[0],PROTO_PORT))
                        continue

                if method == 'REG':
                        if msg.startswith("REG|"):
                                if add_device(msg[4:],addr[0]):
                                        reply = f"HELLO|{server_name}|{connection_id}"
                                else:
                                        reply = f"ERR|{server_name}|{connection_id}|bad registration request|{msg}"
                        else:
                                reply = f"ERR|{server_name}|{connection_id}|illegal request, expecting REG|{msg}"
                        sock_out.sendto(reply.encode('utf-8'),(addr[0],PROTO_PORT))
                        continue   
                devices_lock.acquire()
                this_device = None
                for dev in devices:
                        if (dev['name'] == device_name) and (dev['connection_id'] == connection_id):
                                this_device = dev
                                break
                if this_device == None:
                        sock_out.sendto(f"REGHERE|{server_name}|{connection_id}".encode('utf-8'),(addr[0],PROTO_PORT))
                        devices_lock.release()
                        continue
                if method == 'UPDATE':
                        this_device['last_message']=datetime.datetime.now()
                        for bit in body_bits:
                                try:
                                        field_name,field_value = bit.split('=')
                                        if not field_name in this_device['fields']:
                                                raise Exception('bad 1')
                                        record = this_device['fields'][field_name]
                                        if not check_update_value(field_value,record[0]):
                                                raise Exception('bad 2')
                                        record[1]=field_value
                                except Exception as e:
                                        sock_out.sendto(f"ERR|{server_name}|{connection_id}|bad update request|{bit}|{e.args[0]}".encode('utf-8'),(addr[0],PROTO_PORT))
                                        break
                if method == 'GOODBYE':
                        sock_out.sendto(f"GOODBYE|{server_name}|{connection_id}".encode('utf-8'),(addr[0],PROTO_PORT))
                        devices.remove(this_device)
                devices_lock.release()
                create_page()


def check_update_value(val_expr, val_type):
        if val_type == 'str':
                return True
        elif val_type == 'bool':
                return True if val_expr in ['True','False'] else False
        elif val_type == 'int':
                try:
                        x = int(val_expr)
                except:
                        return False
                return True
        elif val_type == 'float':
                try:
                        x = float(val_expr)
                except:
                        return False
                return True
        raise Exception('Bad type string')


def timer_thread_main():
        sock_out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        global devices
        while True:
                time.sleep(10)
                changes = False
                devices_lock.acquire()
                time_now = datetime.datetime.now()
                kept_devices = []
                for dev in devices:
                        unseen_time = time_now-dev['last_message']
                        if unseen_time > datetime.timedelta(seconds=device_timeout_secs):
                                changes=True
                                continue
                        if unseen_time > datetime.timedelta(seconds=device_prod_secs):
                                sock_out.sendto(f"PROD|{server_name}|{dev['connection_id']}".encode('utf-8'),(dev['ip'],PROTO_PORT))
                        kept_devices.append(dev)
                devices = kept_devices
                devices_lock.release()
                if changes:
                        create_page()
                

def add_device(subs_req,ip_addr):
        subs_bits = subs_req.split('|')
        if len(subs_bits) < 2:
                return False
        new_device = {'name':subs_bits[0],
                      'ip':ip_addr,
                      'connection_id':subs_bits[1],
                      'last_message':datetime.datetime.now(),
                      'fields':{},
                      'commands':{}}
        for subs_bit in subs_bits[2:]:
                bits = subs_bit.split(':')
                name = bits[0]
                params = {}
                for param_spec in bits[1:]:
                        try:
                                param_name,param_type = param_spec.split('=')
                        except ValueError:
                                return False
                        if not param_type in allowed_param_types:
                                return False
                        params[param_name]=param_type
                if name == 'fields':
                        for param_name,param_type in params.items():
                                new_device['fields'][param_name] = [param_type,None]
                else:
                        new_device['commands'][name]=params
        devices_lock.acquire()
        old_device_at_this_ip = None
        for d in devices:
                if d['ip'] == ip_addr:
                        old_device_at_this_ip = d
                        break
        if old_device_at_this_ip != None:
                devices.remove(old_device_at_this_ip)
        devices.append(new_device)
        devices_lock.release()
        create_page()
        return True

def create_form(form_id, name, inputs):
        form_top =  f'<form method="post" action="authenticate.php">\n<b>{name}</b>\n'+\
                '<input type="submit" value="submit"/>\n'+\
                f'<input type="hidden" name="form-name" value="{form_id}">\n'+\
                '<input type="hidden" name="ischeri" value="<?php echo $ischeri; ?>">\n'+\
                '<br/><br/>'
        form_bot = '</form>'
        input_html_chunks = []
        for input_name,input_type in inputs.items():
                form_input_type = param_type_dict[input_type]
                html_chunk = f'<label for="{form_id}|{input_name}">{input_name}:</label>\n' +\
                        f'<input id="{form_id}|{input_name}" name="{input_name}" {form_input_type}/><br/>'
                input_html_chunks.append(html_chunk)
        return form_top+'\n'+('\n'.join(input_html_chunks))+('' if input_html_chunks == [] else '\n')+form_bot
 
def device_to_html(device):
        name = device['name']
        ip_addr = str(device['ip'])
        html_top = f'<h2 style="width:fit-content;background-color:#ccffff;padding:5px;margin-top:10px;">&nbsp;{name}&nbsp;</h2>\n<p><b>IP:</b> {ip_addr}</p>'
        all_f_html = ""
        for f in device['fields']:
                f_type,f_val = device['fields'][f]
                f_val_str = str(f_val)
                f_html = f"<p><b>{f}:</b> {f_val_str}</p>"
                all_f_html = all_f_html + '\n' + f_html
        all_c_html = ""
        for c in device['commands']:
                c_html = create_form(f"{name}|{ip_addr}|{device['connection_id']}|{c}",c,device['commands'][c])
                all_c_html = all_c_html +'\n\n'+c_html
        html = '<div style="width:fit-content;border-width:1px;border-style:solid;border-color:black;padding-top:0px;padding-left:10px;padding-right:10px;">\n'
        html += '\n'.join([html_top,html_short_rule,all_f_html,html_short_rule,all_c_html]) +'</div>\n\n'
        return html

def create_page():
        devices_lock.acquire()
        mid_bits = [device_to_html(device) for device in devices]
        devices_lock.release()
        page_mid = '\n\n<hr/>\n'.join(mid_bits)
        
        page_lock.acquire()
        fh = open('html/index.php','w')
        fh.write(page_top_nocheri+page_mid+page_bot)
        fh.flush()
        fh.close()
        fh = open('html/index_cheri.php','w')
        fh.write(page_top_cheri+page_mid+page_bot)
        fh.flush()
        fh.close()
        page_lock.release()

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

autorefresh = None
usage_string = f"Usage: {sys.argv[0]} <interface_name> [<autorefresh seconds>|off]"
if  not len(sys.argv) in [2,3]:
        print(usage_string)
        quit()
if len(sys.argv) == 3:
        optval = sys.argv[2]
        if optval != 'off':
                try:
                        autorefresh = int(optval)
                except ValueError:
                        print(usage_string)
                        quit()
                if autorefresh <= 0:
                        print(usage_string)
                        quit()
my_ip = iface_name_to_ip(sys.argv[1])
if (my_ip == None) or (my_ip.count('.') != 3): # yuck!
        print(f"{sys.argv[1]} could not be resolved to an ip address")
        quit()
else:
        print(f"resolved iface name {sys.argv[1]} to {my_ip}")
        
fh = open('php_script','r')
php_script = fh.read()
fh.close()
php_script_cheri = php_script.replace('###ISCHERI###','cheri')
php_script_nocheri = php_script.replace('###ISCHERI###','nocheri')

img_list = ['oerc_logo','dsbd_logo','cyberhive_logo']
img_code = ""
first_img = True
for img_name in img_list:
        if first_img:
                l_padd = 0
                first_img = False
        else:
                l_padd=30
        img_code = img_code + f'<img src="{img_name}" style="padding-left:{l_padd}px"/>'
if autorefresh != None:
        autorefresh_tag = f'<meta http-equiv="refresh" content="{autorefresh}">'
else:
        autorefresh_tag = ""
page_top_cheri = '<html><head>'+autorefresh_tag+'</head><body>\n\n'+img_code+'\n\n'+php_script_cheri+"\n\n"+\
        '<br/><br/><a href="index.php">Go to non-CHERI interface</a>&nbsp;&nbsp;&nbsp;<a href="command_log">View command log</a>'+\
        '&nbsp;&nbsp;&nbsp;<a href="index_cheri.php">Refresh page</a><br/><br/>\n\n'
page_top_nocheri = '<html><head>'+autorefresh_tag+'</head><body>\n\n'+img_code+'\n\n'+php_script_nocheri+"\n\n"+\
        '<br/><br/><a href="index_cheri.php">Go to CHERI interface</a>&nbsp;&nbsp;&nbsp;<a href="command_log">View command log</a>'+\
        '&nbsp;&nbsp;&nbsp;<a href="index.php">Refresh page</a><br/><br/>\n\n'
page_bot = "\n\n</body></html>"

fh = open('html/index.php','w')
fh.write(page_top_nocheri+page_bot)
fh.close()
fh = open('html/index_cheri.php','w')
fh.write(page_top_cheri+page_bot)
fh.close()
    
thread_main_funcs = [ findserver_thread_main,
                      server_commands_thread_cheri_main,
                      server_commands_thread_nocheri_main,
                      device_updates_thread_main,
                      timer_thread_main ]
for func in thread_main_funcs:
        threading.Thread(target=func).start()

