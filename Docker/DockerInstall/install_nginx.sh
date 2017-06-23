#!/bin/bash
apt-key add /DockerInstall/nginx_signing.key
echo "deb http://nginx.org/packages/ubuntu/ trusty nginx" >> /etc/apt/sources.list
echo "deb-src http://nginx.org/packages/ubuntu/ trusty nginx" >> /etc/apt/sources.list

apt-get update
apt-get install -y nginx

cp -r /DockerInstall/certs /etc/nginx/
cp /DockerInstall/openwifi.conf /etc/nginx/conf.d
cp /DockerInstall/openwifi_http.conf /etc/nginx/conf.d
rm /etc/nginx/conf.d/default.conf

sed -i 's/development_listen_global/development/g' /DockerInstall/run_openwifi.sh
