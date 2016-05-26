#!/usr/bin/env bash
# Icinga2 Install

wget -O - http://packages.icinga.org/icinga.key | apt-key add -
echo 'deb http://packages.icinga.org/ubuntu icinga-trusty main' > /etc/apt/sources.list.d/icinga-main-trusty.list

apt-get update
apt-get -y install icinga2
debconf-set-selections <<< 'mysql-server mysql-server/root_password password mysql'
debconf-set-selections <<< 'mysql-server mysql-server/root_password_again password mysql'
apt-get -y install mysql-server mysql-client 

debconf-set-selections <<< 'icinga2-ido-mysql icinga2-ido-mysql/enable boolean false'
debconf-set-selections <<< 'dbconfig-common dbconfig-common/dbconfig-install boolean false'
debconf-set-selections <<< 'icinga2-ido-mysql icinga2-ido-mysql/dbconfig-install boolean false'
debconf-set-selections <<< 'dbconfig-common dbconfig-common/upgrade-backup boolean false'
debconf-set-selections <<< 'dbconfig-common dbconfig-common/dbconfig-remove boolean false'
debconf-set-selections <<< 'dbconfig-common dbconfig-common/dbconfig-upgrade boolean false'
debconf-set-selections <<< "icinga2-ido-mysql icinga2-ido-mysql/password-confirm password icinga"
debconf-set-selections <<< "icinga2-ido-mysql icinga2-ido-mysql/app-password-confirm password icinga"
debconf-set-selections <<< "icinga2-ido-mysql icinga2-ido-mysql/mysql/admin-pass password mysql"
debconf-set-selections <<< "icinga2-ido-mysql icinga2-ido-mysql/mysql/app-pass password icinga"
apt-get -y install icinga2-ido-mysql
apt-get -y install icingaweb2

cp -rv /DockerInstall/icinga/* /

mysql -uroot -pmysql -e "CREATE DATABASE IF NOT EXISTS icinga ; GRANT ALL ON icinga.* TO icinga@localhost IDENTIFIED BY 'icinga';"
mysql -uicinga -picinga icinga < /usr/share/icinga2-ido-mysql/schema/mysql.sql
mysql -uroot -pmysql -e "CREATE DATABASE IF NOT EXISTS icingaweb2 ; GRANT ALL ON icingaweb2.* TO icingaweb2@localhost IDENTIFIED BY 'icingaweb2';"
mysql -uicingaweb2 -picingaweb2 icingaweb2 < /usr/share/icingaweb2/etc/schema/mysql.schema.sql
mysql -uicingaweb2 -picingaweb2 icingaweb2 -e "INSERT INTO icingaweb_user (name, active, password_hash) VALUES ('icingaadmin', 1, '\$1\$iQSrnmO9\$T3NVTu0zBkfuim4lWNRmH.');"

/etc/init.d/mysql restart

#setup apache mod_wsgi

apt-get -y install libapache2-mod-wsgi-py3 

cp /DockerInstall/openwifi.conf /etc/apache2/conf-available
cd /etc/apache2/conf-enabled
ln -s ../conf-available/openwifi.conf

#rights to the database
chgrp www-data /home/openwifi
chmod 770 /home/openwifi
chgrp www-data /home/openwifi/Controller
chmod 770 /home/openwifi/Controller
chgrp www-data /home/openwifi/Controller/openwifi.sqlite
chmod 660 /home/openwifi/Controller/openwifi.sqlite

# install index site

cp /home/openwifi/Controller/openwifi/static/index.html /var/www/html
cp /home/openwifi/Controller/openwifi/static/sites.json /var/www/html
mkdir /var/www/html/js
mkdir /var/www/html/css
cp /home/openwifi/Controller/openwifi/static/css/bootstrap.min.css /var/www/html/css
cp /home/openwifi/Controller/openwifi/static/css/base_layout.css /var/www/html/css
cp /home/openwifi/Controller/openwifi/static/js/jquery.js /var/www/html/js
cp /home/openwifi/Controller/openwifi/static/js/bootstrap.min.js /var/www/html/js
chgrp -R www-data /var/www/html
chown -R www-data /var/www/html

#cp /DockerInstall/mpm_prefork.conf /etc/apache2/mods-available/
service apache2 restart

