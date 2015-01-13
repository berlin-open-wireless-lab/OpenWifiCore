""" uci parsing """

import logging
import re
import json


class UciError(RuntimeError):
    pass

class UciWrongTypeError(UciError):
    pass

class UciNotFoundError(UciError):
    pass

class UciParseError(UciError):
    pass

class Config(object):
    def __init__(self, uci_type, name, anon):
        self.uci_type = uci_type
        self.name = name
        self.anon = anon
        # options are key -> str(value)
        # lists are key -> [value x, value y]
        self.keys = {}

    def add_list(self, key, value):
        if key in self.keys:
            self.keys[key].append(value)
        else:
            self.keys[key] = [value]

    def remove_list_pos(self, key, pos):
        try:
            if not isinstance(self.keys[key], list):
                raise UciWrongTypeError
            del self.keys[key][pos]
        except(ValueError, KeyError):
            return

    def remove_list_value(self, key, value):
        try:
            self.keys[key].remove(value)
        except(ValueError, KeyError):
            return

    def set_option(self, key, value):
        if key in self.keys:
            if isinstance(self.keys[key], list):
                raise UciWrongTypeError()
        self.keys[key] = value

    def remove_option(self, key):
        if key in self.keys:
            del self.keys[key]

    def export_uci(self):
        export = []
        if not self.anon:
            export.append("config '%s' '%s'\n" % (self.uci_type, self.name))
        else:
            export.append("config '%s'\n" % (self.uci_type))
        for opt_list in self.keys:
            if isinstance(self.keys[opt_list], list):
                export.extend([("\tlist '%s' '%s'\n" % (opt_list, element)) for element in self.keys[opt_list]])
            else:
                export.append("\toption '%s' '%s'\n" % (opt_list, self.keys[opt_list]))
        export.append('\n')
        return ''.join(export)

    def export_dict(self, forjson = False):
        export = {}
        if forjson:
            export['.name']  = self.name
            export['.type']  = self.uci_type
            export['.anonymous'] = self.anon
            for i,j in self.keys.items():
                export[i] = j
            pass
        else:
            export['section'] = self.name
            export['type']    = self.uci_type
            export['values']  = self.keys
        return export

    def __repr__(self):
        return "Config[%s:%s] %s" % (self.uci_type, self.name, repr(self.keys))

class Package(list):
    def __init__(self, name):
        super().__init__()
        self.name = name

    def add_config(self, config):
        self.append(config)

class Uci(object):
    logger = logging.getLogger('uci')
    def __init__(self):
        self.packages = {}

    def add_package(self, package_name):
        if package_name not in self.packages:
            self.packages[package_name] = Package(package_name)
        return self.packages[package_name]

    def add_config(self, package_name, config):
        if not isinstance(config, Config):
            return RuntimeError()
        if package_name not in self.packages:
            self.packages[package_name] = Package()
        self.packages[package_name].append(config)

    def del_config(self, config):
        pass

    def del_path(self, path):
        pass

    def export_uci_tree(self):
        export = []
        for package, content in self.packages.items():
            export.append("package '%s'\n" % package)
            export.append("\n")
            export.extend([config.export_uci() for config in content])
        return "".join(export)

    def diff(self, old, new):
        new_packages    = []
        new_configs     = []
        old_packages    = []
        old_configs     = []
        changed_keys    = {}
        # to be implemented

    def load_tree(self, export_tree_string):
        cur_package = None
        config = None

        export_tree = json.loads(export_tree_string)

        for package in export_tree.keys():
            cur_package = self.add_package(package)
            for config in export_tree[package]['values']:
                config = export_tree[package]['values'][config]
                anon = config.pop(".anonymous")
                cur_config = Config(config.pop('.type'), config.pop('.name'),anon=='true')
                cur_package.append(cur_config)
                for key in config.keys():
                    cur_config.set_option(key,config[key])
                       # if isinstance(config[key], list):
                       #     cur_config.add_list(key,config[key])
                       # else:
                       #     cur_config.set_option(key,config[key])
    def export_json(self):
        export={}
        for packagename, package in self.packages.items():
            export[packagename] = {}
            export[packagename]['values'] = {}
            for config in package:
                export[packagename]['values'][config.name] =\
                    config.export_dict(forjson=True)
        return json.dumps(export)


class UciConfig(object):
    """ Class for configurations - like network... """
    pass

if __name__ == '__main__':
    uci_export = open('uci_export')
    alles = uci_export.read(1000000)
    logging.basicConfig()
    ucilog = logging.getLogger('uci')
    ucilog.setLevel(logging.DEBUG)
    uci = Uci()
    uci.load_tree(alles)
    print(uci.export_tree())
