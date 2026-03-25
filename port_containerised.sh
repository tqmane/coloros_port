#!/bin/bash
source functions.sh
blue "Checking if Distrobox exists"
distrobox > /dev/null
if [ $? -eq 0 ];then 
  blue "Distrobox exists on your system"
else
  blue "Unable to find Distrobox. Please install Distrobox in order to run the port script under a container."
  exit 1
fi
blue "Checking if container exists"
distrobox-list | grep "coloros_port_container" > /dev/null
if [ $? -eq 0 ];then
  blue "Container exists"
else
  blue "Container does not exist. Creating..."
  distrobox assemble create --file distrobox.ini
fi
distrobox enter coloros_port_container -- sudo ./port.sh "$1" "$2" "$3" "$4"
