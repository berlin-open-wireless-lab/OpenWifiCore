#!/usr/bin/env python3

import json
import jsonrpclib
import logging
from datetime import datetime
from datetime import timedelta
from enum import Enum

class MessageStatus(Enum):
    UBUS_STATUS_OK = 0
    UBUS_STATUS_INVALID_COMMAND = 1
    UBUS_STATUS_INVALID_ARGUMENT = 2
    UBUS_STATUS_METHOD_NOT_FOUND = 3
    UBUS_STATUS_NOT_FOUND = 4
    UBUS_STATUS_NO_DATA = 5
    UBUS_STATUS_PERMISSION_DENIED = 6
    UBUS_STATUS_TIMEOUT = 7
    UBUS_STATUS_NOT_SUPPORTED = 8

class NotAuthenticatedError(RuntimeError):
    pass

class Ubus(object):
    def list(self, path):
        raise NotImplementedError

    def call(self, path, func, **kwargs):
        raise NotImplementedError

    def subscribe(self, path):
        raise NotImplementedError

class JsonUbus(Ubus):
    def __init__(self, url, user, password):
        self.url = url
        self._server = jsonrpclib.ServerProxy(self.url)
        self.__session = None
        self.__user = user
        self.__password = password
        self.__timeout = timedelta(seconds=1)
        self.__expires = None
        self.__lastcalled = datetime.now()
        self.__lastused = datetime(year=1970, month=1, day=1)
        self.logger = logging.getLogger('jsonubus')

    def session(self):
        if self.__session == None:
            ret = self._server.call("00000000000000000000000000000000", "session", "login", {"username": self.__user, "password": self.__password})
            if ret[0] != 0:
                raise NotAuthenticatedError("Could not authenticate against ubus")
            self.__session = ret[1]['ubus_rpc_session']
            self.__timeout = timedelta(seconds=ret[1]['timeout'])
            self.__expires = ret[1]['expires']
            self.__lastused = datetime.now()
            self.logger.info('Connected with {}'.format(self.url))
        return self.__session

    def list(self, *args):
        """ list() - returns all available paths
            list('system', 'network') -> {'system': {}, 'network': {}}
                returning dict only contains valid objects
        """
        if len(args):
            return self._server.list(*args)
        else:
            return self._server.list()

    def _handle_session_timeout(self):
        self.logger.debug("Handle Session Timeout: {} + {} < {}".format(
            self.__lastused, self.__timeout, datetime.now()))
        if (self.__lastused + self.__timeout) < datetime.now():
            self.__session = None

    def call(self, ubus_path, ubus_method, **kwargs):
        """ calls ubus method ubus_method and returns a list.
            Returning list contains at lease one element the return value or
            if success also a response
        """
        self._handle_session_timeout()
        self.__lastused = datetime.now()
        self.logger.debug("call {} {} {} {}".format(self.session(), ubus_path, ubus_method, kwargs))
        return self._server.call(self.session(), ubus_path, ubus_method, kwargs)

    def callp(self, ubus_path, ubus_method, **kwargs):
        """ returns a human printable ubus response """
        response = self.call(ubus_path, ubus_method, **kwargs)
        if response[0] != 0:
            return "Fail {}".format(MessageStatus(response[0]))
        else:
            if len(response) > 1:
                return response[1]

if __name__ == '__main__':
    js = JsonUbus(url="http://192.168.122.2/ubus", user='root', password='yipyip')
    print(js.call('uci', 'configs'))
    print(js.call('uci', 'get', config='network'))
    #print(js.list("system", "network"))
