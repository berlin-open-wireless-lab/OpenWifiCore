#!/bin/bash
apt-key add /DockerInstall/nginx_signing.key
echo "deb http://nginx.org/packages/ubuntu/ trusty nginx" >> /etc/apt/sources.list
echo "deb-src http://nginx.org/packages/ubuntu/ trusty nginx" >> /etc/apt/sources.list

apt-get update
apt-get install -y nginx

cp -r /DockerInstall/certs /etc/nginx/
cp /DockerInstall/openwifi.conf /etc/nginx/sites-available/
cp /DockerInstall/openwifi_http.conf /etc/nginx/sites-available/
cd /etc/nginx/sites-enabled
rm *
cd ../conf.d
mv default.conf ../sites-available
ln -s /etc/nginx/sites-available/openwifi.conf
ln -s /etc/nginx/sites-available/openwifi_http.conf

sed -i 's/development_listen_global/development/g' /DockerInstall/run_openwifi.sh
