#!/usr/bin/env bash

# install avahi
apt-get -y install avahi-daemon
cp /DockerInstall/openwifi.service /etc/avahi/services/openwifi.service
/etc/init.d/avahi-daemon restart

# use dnsmasq as dhcp server
apt-get -y dnsmasq
echo "interface=eth1" >> /etc/dnsmasq.conf
echo "bind-interfaces" >> /etc/dnsmasq.conf
echo "dhcp-range=192.168.50.100,192.168.50.254,12h" >> /etc/dnsmasq.conf
/etc/init.d/dnsmasq restart
