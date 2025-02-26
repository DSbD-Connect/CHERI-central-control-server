#!/bin/bash

if [ "$#" -gt 2 ]; then
    echo "Usage: $0 <interface name> [<autorefresh seconds>|off]"
    exit
fi

./compile_command_handler.sh
./docker_container.sh
./server.py $1 $2

