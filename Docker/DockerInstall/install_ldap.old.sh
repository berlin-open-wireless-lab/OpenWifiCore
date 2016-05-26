#!/usr/bin/env bash

# LDAP install

echo "127.0.1.1 $HOSTNAME.OpenWifi.local $HOSTNAME" >> /etc/hosts

LDAP_ADMIN_PASSWORD="ldap"
LDAP_DOMAIN="OpenWifi.local"
LDAP_ORGANISATION="OpenWifi"


#apt-get -y install slapd ldap-utils

debconf-set-selections <<< 'lapd slapd/internal/generated_adminpw password ${LDAP_ADMIN_PASSWORD}'
debconf-set-selections <<< 'lapd slapd/internal/adminpw password ${LDAP_ADMIN_PASSWORD}'
debconf-set-selections <<< 'lapd slapd/password2 password ${LDAP_ADMIN_PASSWORD}'
debconf-set-selections <<< 'lapd slapd/password1 password ${LDAP_ADMIN_PASSWORD}'
debconf-set-selections <<< 'lapd slapd/dump_database_destdir string /var/backups/slapd-VERSION'
debconf-set-selections <<< 'lapd slapd/domain string ${LDAP_DOMAIN}'
debconf-set-selections <<< 'lapd shared/organization string ${LDAP_ORGANISATION}'
debconf-set-selections <<< 'lapd slapd/backend string HDB'
debconf-set-selections <<< 'lapd slapd/purge_database boolean true'
debconf-set-selections <<< 'lapd slapd/move_old_database boolean true'
debconf-set-selections <<< 'lapd slapd/allow_ldap_v2 boolean false'
debconf-set-selections <<< 'lapd slapd/no_configuration boolean false'
debconf-set-selections <<< 'lapd slapd/dump_database select when needed'

dpkg-reconfigure -f noninteractive slapd

# fix file permissions
chown -R openldap:openldap /var/lib/ldap
chown -R openldap:openldap /etc/ldap
#chown -R openldap:openldap ${CONTAINER_SERVICE_DIR}/slapd

slapd -h "ldap://localhost ldapi:///" -u openldap -g openldap

ldapadd -H "ldap://localhost" -x -D cn=admin,dc=OpenWifi,dc=local -w ldap -f /DockerInstall/add_content.ldif

#/etc/init.d/slapd restart

