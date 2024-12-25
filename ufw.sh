#!/bin/bash

sudo ufw default deny incoming
sudo ufw default deny outgoing
sudo ufw allow in on eth0 from 192.168.100.0/24 to any port 443 proto tcp
sudo ufw allow out on eth0 to 192.168.100.0/24 port 443 proto tcp
sudo ufw allow in on eth0 from 192.168.105.0/24 to any port 22 proto tcp
sudo ufw allow out on eth0 to 192.168.105.0/24 port 22 proto tcp
