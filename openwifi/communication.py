from abc import ABCMeta, abstractmethod, abstractclassmethod, abstractproperty
from openwifi.netcli import jsonubus
import json
from openwifi.utils import diffChanged

class ClassProperty(abstractproperty):
    def __get__(self, cls, owner):
        return self.fget.__get__(None, owner)()

class OpenWifiCommunication(metaclass=ABCMeta):

    @ClassProperty
    @classmethod
    def string_identifier_list(self): pass

    @abstractclassmethod
    def get_config(self, device, DBSession): pass

    @abstractclassmethod
    def update_config(self, device, DBSession, config): pass

    @abstractclassmethod
    def update_status(self, device, redisDB): pass

    @abstractclassmethod
    def update_sshkeys(self, device, DBSession): pass

    @abstractclassmethod
    def config_differs_device(self, device, DBSession, config): pass

    @abstractclassmethod
    def exec_on_device(self, device, DBSession, cmd, prms): pass

from pyuci import Uci, Package, Config

class OpenWifiUbusCommunication(OpenWifiCommunication):
    @ClassProperty
    @classmethod
    def string_identifier_list(self):
        return ['JSONUBUS_HTTP', 'JSONUBUS_HTTPS', '']

    def get_config(device, DBSession):

        try:
            if device.configured:
                newConf = return_jsonconfig_from_device(device)

                newUci = Uci()
                newUci.load_tree(newConf)

                oldUci = Uci()
                oldUci.load_tree(device.configuration)

                diff = oldUci.diff(newUci)

                if diffChanged(diff):
                    device.append_diff(diff, DBSession, "download: ")
                    device.configuration = newConf
            else:
                device.configuration = return_jsonconfig_from_device(device)
                device.configured = True

            DBSession.commit()
            return True
        except Exception as thrownexpt:
            print(thrownexpt)
            device.configured = False
            DBSession.commit()
            return False

    def config_differs_device(device, DBSession, config):
        if config == None:
            return True

        new_configuration = Uci()
        new_configuration.load_tree(config)

        cur_configuration = Uci()
        cur_configuration.load_tree(return_jsonconfig_from_device(device))
        conf_diff = cur_configuration.diff(new_configuration)

        return diffChanged(conf_diff), conf_diff

    def update_config(device, DBSession, config=None):

        if config == None:
            config = device.configuration

        changed, conf_diff = OpenWifiUbusCommunication.config_differs_device(device, DBSession, config)

        from openwifi.jobserver.tasks import diff_update_config
        if changed:
            diff_update_config(conf_diff, device.uuid)
        
        if changed:
            device.append_diff(conf_diff, DBSession, "upload: ")
        DBSession.commit()
        DBSession.close()

    def update_status(device, redisDB):
        js = get_jsonubus_from_openwrt(device)
        try:
            networkstatus = js.callp('network.interface','dump')
        except OSError as error:
            redisDB.hset(str(device.uuid), 'status', "{message} ({errorno})".format(message=error.strerror, errorno=error.errno))
        except:
            redisDB.hset(str(device.uuid), 'status', "error receiving status...")
        else:
            redisDB.hset(str(device.uuid), 'status', "online")
            redisDB.hset(str(device.uuid), 'networkstatus', json.dumps(networkstatus['interface']))

    def update_sshkeys(device, DBSession):
        keys = ""
        for sshkey in openwrt.ssh_keys:
            keys = keys+'#'+sshkey.comment+'\n'
            keys = keys+sshkey.key+'\n'
        js = get_jsonubus_from_openwrt(openwrt)
        keyfile='/etc/dropbear/authorized_keys'
        js.call('file', 'write', path=keyfile, data=keys)
        js.call('file', 'exec',command='chmod', params=['600',keyfile])

    def exec_on_device(device, DBSession, cmd, prms):
        js = get_jsonubus_from_openwrt(device)
        ans = None
        try:
            ans = js.call('file', 'exec', command=cmd, params=prms)
        except:
            pass
        return ans

def return_jsonconfig_from_device(openwrt):
    js = get_jsonubus_from_openwrt(openwrt)
    device_configs = js.call('uci', 'configs')
    configuration="{"
    for cur_config in device_configs[1]['configs']:
        configuration+='"'+cur_config+'":'+json.dumps(js.call("uci","get",config=cur_config)[1])+","
    configuration = configuration[:-1]+"}"
    return configuration

def get_jsonubus_from_openwrt(openwrt):
    if openwrt.communication_protocol == "JSONUBUS_HTTPS":
        device_url = "https://"+openwrt.address+"/ubus"
    else:
        device_url = "http://"+openwrt.address+"/ubus"

    js = jsonubus.JsonUbus(url = device_url, \
                           user = openwrt.login, \
                           password = openwrt.password)
    return js
