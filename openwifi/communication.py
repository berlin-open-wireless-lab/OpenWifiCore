from abc import ABCMeta, abstractmethod

class OpenWifiCommunication(metaclass=ABCMeta):

    @property
    @abstractmethod
    def string_identifier_list(self): pass

    @abstractmethod
    def get_config(self, device): pass

    @abstractmethod
    def update_config(self, device): pass

    @abstractmethod
    def update_status(self, device): pass

    @abstractmethod
    def update_sshkeys(self, device): pass

    @abstractmethod
    def exec_on_device(self, device, cmd, prms): pass
