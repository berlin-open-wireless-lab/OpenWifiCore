FROM ubuntu:14.04

ADD ./DockerInstall /DockerInstall

RUN apt-get update

ENV LDAP_DOMAIN=OpenWifi.local
ENV LDAP_PASSWORD=ldap
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update -qq && apt-get install -y slapd ldap-utils -qq
RUN rm -rf /etc/ldap/slapd.d && rm -rf /var/lib/ldap/* && mkdir /etc/ldap/slapd.d
RUN chmod +x /DockerInstall/run_ldap.sh /DockerInstall/install_ldap.sh

RUN chmod 700 /DockerInstall/install_openwifi_relative.sh
RUN chmod 700 /DockerInstall/run_openwifi.sh
RUN /DockerInstall/install_openwifi_relative.sh

EXPOSE 6543


# Supervisord
RUN apt-get install -y supervisor
RUN cp /DockerInstall/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

CMD ["/usr/bin/supervisord"]
