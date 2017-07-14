FROM ubuntu:14.04

ARG USE_LDAP
ARG USE_AVAHI
ARG USE_DNSMASQ
ARG USE_NGINX

ADD ./DockerInstall /DockerInstall

RUN apt-get update

ENV LDAP_DOMAIN=OpenWifi.local
ENV LDAP_PASSWORD=ldap
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update -qq 
RUN if $USE_LDAP; then apt-get install -y slapd ldap-utils -qq; fi
RUN if $USE_LDAP; then rm -rf /etc/ldap/slapd.d && rm -rf /var/lib/ldap/* && mkdir /etc/ldap/slapd.d; fi
RUN if $USE_LDAP; then chmod +x /DockerInstall/run_ldap.sh /DockerInstall/install_ldap.sh; fi

RUN chmod 700 /DockerInstall/install_openwifi_relative.sh
RUN chmod 700 /DockerInstall/run_openwifi.sh /DockerInstall/install_openwifi.sh /DockerInstall/run_openwifi.sh  /DockerInstall/run_openwifi_jobserver.sh  /DockerInstall/run_openwifi_jobserver_beat.sh

RUN /DockerInstall/install_openwifi_relative.sh

RUN if $USE_AVAHI; then chmod 700 /DockerInstall/install_avahi.sh /DockerInstall/run_avahi.sh; fi
RUN if $USE_AVAHI; then /DockerInstall/install_avahi.sh; fi

RUN if $USE_NGINX; then chmod 700 /DockerInstall/install_nginx.sh; fi
RUN if $USE_NGINX; then /DockerInstall/install_nginx.sh; fi

EXPOSE 6543

# Supervisord
RUN apt-get install -y supervisor
RUN cp /DockerInstall/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
RUN cp /DockerInstall/supervisord.conf.master /etc/supervisor/supervisord.conf

RUN if ! $USE_LDAP; then sed -i '/ldap/s/^/#/g' /etc/supervisor/conf.d/supervisord.conf; fi
RUN if ! $USE_AVAHI; then sed -i '/avahi/s/^/#/g' /etc/supervisor/conf.d/supervisord.conf; fi
RUN if ! $USE_DNSMASQ; then sed -i '/dnsmasq/s/^/#/g' /etc/supervisor/conf.d/supervisord.conf; fi
RUN if ! $USE_NGINX; then sed -i '/nginx/s/^/#/g' /etc/supervisor/conf.d/supervisord.conf; fi

# Change port to 80 if using NGINX
RUN if $USE_NGINX; then sed -i 's/6543/80/g' /etc/avahi/services/openwifi.service; fi

# Dnsmasq
RUN if $USE_DNSMASQ; then apt-get install -y dnsmasq; fi
RUN if $USE_DNSMASQ; then cp /DockerInstall/dnsmasq.conf /etc/dnsmasq.conf; fi

CMD ["/usr/bin/supervisord"]
