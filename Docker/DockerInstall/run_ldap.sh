#!/bin/bash

set -e

if [ ! -f /etc/ldap/slapd.d/cn=config.ldif ]; then
  /DockerInstall/install_ldap.sh
fi

#exec /usr/sbin/slapd -F /etc/ldap/slapd.d -h "ldapi:/// ldap:/// ldaps:///" -d stats
mkdir -p /var/run/slapd
touch /var/run/slapd/slapd.pid
exec /usr/sbin/slapd -F /etc/ldap/slapd.d -h "ldap:/// ldaps:///" -d stats

