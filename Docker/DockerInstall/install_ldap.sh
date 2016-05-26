#!/usr/bin/env bash

# LDAP install

# echo "127.0.1.1 vagrant-ubuntu-trusty-64.OpenWifi.local vagrant-ubuntu-trusty-64" >> /etc/hosts

apt-get -y install slapd ldap-utils

# fix file permissions
chown -R openldap:openldap /var/lib/ldap
chown -R openldap:openldap /etc/ldap
#chown -R openldap:openldap ${CONTAINER_SERVICE_DIR}/slapd

LDAP_ADMIN_PASSWORD="ldap"
LDAP_DOMAIN="OpenWifi.local"
LDAP_ORGANISATION="OpenWifi"

    cat <<EOF | debconf-set-selections
slapd slapd/internal/generated_adminpw password ${LDAP_ADMIN_PASSWORD}
slapd slapd/internal/adminpw password ${LDAP_ADMIN_PASSWORD}
slapd slapd/password2 password ${LDAP_ADMIN_PASSWORD}
slapd slapd/password1 password ${LDAP_ADMIN_PASSWORD}
slapd slapd/dump_database_destdir string /var/backups/slapd-VERSION
slapd slapd/domain string ${LDAP_DOMAIN}
slapd shared/organization string ${LDAP_ORGANISATION}
slapd slapd/backend string HDB
slapd slapd/purge_database boolean true
slapd slapd/move_old_database boolean true
slapd slapd/allow_ldap_v2 boolean false
slapd slapd/no_configuration boolean false
slapd slapd/dump_database select when needed
EOF

dpkg-reconfigure -f noninteractive slapd

slapd -h "ldap://localhost ldapi:///" -u openldap -g openldap -F /etc/ldap/slap.d

ps aux

ldapadd -H "ldap://localhost" -x -D cn=admin,dc=OpenWifi,dc=local -w ldap -f /DockerInstall/add_content.ldif

#/etc/init.d/slapd restart

