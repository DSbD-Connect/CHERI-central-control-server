# CHERI Central Control Server

This code demonstrates the use of an ARM Morello machine as a central control server in
a network of devices. The Morello machine provides a web interface via which the data
provided by the devices may be viewed, and via which the devices may be sent commands.

In order to send a command to a device, a user of the web interface is required to
authenticate with a username and password. The code which checks this password has
a buffer overflow bug which can be exploited to gain unauthorised access when not using
CHERI. When CHERI is enabled, the buffer overflow is detected by the hardware and no
access is granted. This demonstrates the value of CHERI in protecting against memory
access bugs.

This demonstrator requires an ARM Morello machine.

## Warning and License

This software was created for use in a technology demonstrator. It is neither
designed nor intended to be used for any other purpose. In particular, the
authors strongly advise against the use of this software for commercial
purposes, or in any situation where its reliability or security against attack
is important. The software was not designed to operate for more than
a short period of time sufficient for the purposes of demonstration, nor to
operate unsupervised by a person, and is not designed to be secure against
attack by hackers.

The above notice does not form part of the license under which this software
is released, and is for informational purposes only. See LICENSE for details
of how you may use this software, and for the disclaimer of warranties.

## High-level structure of the demonstrator

There are two parts to the code: the code which runs on the central control server,
and the code that is run on the clients. The basic structure of the demonstrator is
a network connecting a central control server to one or more devices. The devices
listen for commands from the server, and upon receiving a command perform the
corresponding action. The devices may also report back data to the central server.
The central server is in turn controlled by a user via a web interface, which allows
the user to view any data from devices and to trigger the sending of commands to the
devices.

The client code needs to be adapted to the particular device it is running on. Each
device needs to run a python script which implements the functionality of the commands
which the device is capable of performing, as well as the functionality of sending any
data to the central server. This "client script" works by loading a module client_mod
(which provides all the functionality for actually communicating with the central server),
defining what commands it offers and what data it reports back to the server, defining
handler functions to perform these commands and assemble data for sending to the server,
registering all of these definitions with client_mod, and then entering client_mod's main
loop. Several example client scripts for different kinds of devices are provided.

## Setting up the demonstrator

In order to use the demonstrator, you need an ARM Morello machine running
[Morello Linux](https://www.morello-project.org/) with [Docker](https://www.docker.com/)
installed, and one or more devices to act as clients controlled by the central server.
These devices need to be capable of running a python script. We found that single-board
computers (e.g. Raspberry Pis) worked well in this role.

To prepare the server, simply put the contents of the `server` directory into a directory
on the Morello machine, and then (as root) run `run_server.sh` with appropriate arguments
(see below). The server can be stopped
with `Ctl+C`. Note that the only reason the code need to be run as root is to allow listening
on port 80 for HTTP. By changing the docker port mapping in `docker_container.sh` to use a
host port higher than 1024, non-root use could be enabled.

`run_server.sh` has one mandatory argument, `interface name` and one optional argument,
`autorefresh seconds`. The syntax is `run_server.sh <interface name> [<autorefresh seconds>]`.
`interface name` is the name of the network interface to be used by the demonstrator for
network communications. `autorefresh seconds` controls the auto-refresh interval of the main
page of the web interface. Having this auto-refresh allows updates from clients to be shown
automatically. By default, this auto-refresh is turned off (and so it is necessary to
manually refresh the web interface page to see any updates).

For each client device, it is necessary (as mentioned above) to create a python script to
run on the device which will provide the functionality of the client's commands. See the
previous section for more on this. Once these scripts have been created, they simply need to
be started on each device. Note that by default, the client_mod module's main loop handles
the establishment of communication with the server automatically via IP multi-casting.


## Using the demonstrator

Once the demonstrator is running, it can be used to show the ability of CHERI to block
exploitation of memory access vulnerabilities. The server presents a web interface on
port 80 (standard HTTP) which can be accessed with any web browser. The images below
show the web interface with a single client device representing a remotely operated medical
injection pump.

Index Page             |  Authentication Page
:-------------------------:|:-------------------------:
![](/images/index.png)  |  ![](/images/auth.png)


The available commands and data from known client devices will be displayed on the main
page of the interface, as shown in the image on the left. By entering values (if necessary)
and pressing a "submit" button, a user can request to issue a command to a client device.
Doing so takes the user to an authorisation page, where they must enter a password to send the
command. The default password is `abc123`.

However, the C code which processes the submitted password contains a (deliberate) buffer
overflow vulnerability. The code copies whatever password is entered into a small fixed-length
buffer without any checking of length. If the C code has been compiled with the clang compiler,
then the memory directly after this buffer contains a boolean variable which records whether
authentication was successful.

If CHERI protections are not enabled, then a malicious user can send out a command by entering
any 10 character string in the password box. This will overflow the buffer (note that the buffer
has been made artificially short to allow ease of demonstration) and overwrite the boolean
variable, making the program think that authentication was successful. However, if CHERI is
enabled, then the processor will detect the illegal memory access and kill the password-checking
program before the illicit command can be sent.

Both CHERI and non-CHERI versions of the password-checking program are present in the demonstrator,
and one can choose which to use via the links at the top of the main page of the web interface (the
default main page, `index.php`, uses the non-CHERI version. The corresponding page for the CHERI version
is `index_cheri.php`. When a user attempts to exploit the buffer overflow in the non-CHERI version,
the command will be sent, while in the CHERI version the command will not be sent. A log of the
attempts to send commands is kept in the file `command_log`, which can be accessed via the links at the
top of the page. This log is useful to show clearly the difference which CHERI makes.


## Internal details

The following diagram shows the structure of the demonstrator in detail. The set-up shown here has
one client device, which consists of a Raspberry Pi controlling a syringe pump, representing a
remotely-controlled medical device.

![Architecture](images/medical_demonstrator.svg)

The control server consists of two processes. The first runs a custom server, written in python, which
handles communication with clients and dynamically creates the php/html files for the web interface.
The second process is an Apache web server running in a Docker container, which is used to serve the
documents created by the python process.













