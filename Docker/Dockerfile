FROM ubuntu:14.04


ADD ./DockerInstall /DockerInstall

RUN groupadd -r openldap && useradd -r -g openldap openldap
RUN chmod 700 /DockerInstall/install_ldap.sh
RUN /DockerInstall/install_ldap.sh

#RUN chmod 700 /DockerInstall/install_openwifi.sh
#RUN /DockerInstall/install_openwifi.sh

CMD ["/bin/bash"]
