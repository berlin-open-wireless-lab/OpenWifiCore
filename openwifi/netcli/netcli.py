#!/usr/bin/env python3

from pprint import pprint
from jsonubus import JsonUbus
import readline
import logging
import sys
import argparse

LOG = logging.getLogger('netcli')

def convert_to_dict(argumentlist):
    """ convert a list into a dict
        e.g. ['help=me', 'foo'='bar'] => {'help': 'me', 'foo':'bar'}
    """
    def gen_dict(keyval):
        pos = keyval.find('=')
        if pos == -1:
            raise RuntimeError("Invalid argument {}".format(keyval))
        return {keyval[:pos]:keyval[pos+1:]}
    converted = {}
    for i in [gen_dict(part) for part in argumentlist if len(part) > 0]:
        converted.update(i)
    return converted

class CliApp(object):
    def __init__(self):
        self.__prompt = "netcli#>"
        self.__command = {}
        self.__commands = []
        self.__completer = []
        self.register_command('help', self)
        self.register_command('?', self)
        self.register_command('verbose', self)
        readline.parse_and_bind("tab: complete")
        readline.set_completer(self.completer)

    def error(self, message):
        print(message)

    @property
    def prompt(self):
        return self.__prompt

    @prompt.setter
    def set_prompt(self, prompt):
        self.__prompt = prompt

    def input_loop(self):
        # ctrl D + exit
        line = ''
        while line != 'exit':
            try:
                line = input(self.prompt)
            except EOFError:
                # otherwise console will be on the same line
                print()
                sys.exit(0)
            except KeyboardInterrupt:
                print()
                sys.exit(0)

            self.dispatcher(line)

    def completer(self, text, state):
        # first complete commands
        # second delegate completer
        if state == 0:
            if type(text) == str:
                split = readline.get_line_buffer().split(' ')
                if len(split) <= 1:
                    self.__completer = [s + " " for s in self.__commands if s.startswith(split[0])]
                else:
                    if split[0] in self.__command:
                        self.__completer = self.__command[split[0]].complete(split[1:])
                    else:
                        return None
            else:
                self.__completer = self.__commands
        try:
            return self.__completer[state]
        except IndexError:
            return None

    def dispatcher(self, line):
        split = line.split(' ')
        cmd = split[0]
        argument = split[1:]
        if cmd in self.__command:
            self.__command[cmd].dispatch(cmd, argument)
        else:
            self.error("No such command. See help or ?")

    def register_command(self, name, cmdclass):
        # TODO: move this into class var of SubCommand
        self.__command[name] = cmdclass
        self.__commands.append(name)

    def dispatch(self, cmd, arg):
        """ self implemented commands """
        if cmd == "help" or cmd == "?":
            self.help()
        elif cmd == "verbose":
            self.verbose()

    def help(self):
        print("available commands : %s" % self.__commands)

    def verbose(self):
        logging.basicConfig()

class Cli(CliApp):
    def __init__(self, url, user, password):
        super().__init__()
        self.__url = url
        self.__user = user
        self.__password = password
        self.__ubus = JsonUbus(url, user, password)
        self.__ubus.list()
        self.register_command('ubus', Ubus(self.__ubus))

class SubCommand(object):
    # todo class variables
    def complete(self, text):
        """ returns an array of possible extensions
            text is "cmd f"
            return ["cmd foo", "cmd fun", "cmd far"]
        """
        pass

    def dispatch(self, cmd, arguments):
        """ arguements is []
        """
        pass

class Ubus(SubCommand):
    """ An interface to ubus """
    _commands = ['call', 'list']

    def __init__(self, ubus):
        self.__ubus = ubus
        self.__paths = {}

    def update_paths(self):
        paths = self.__ubus.list()
        for path in paths:
            self.__paths.update(self.__ubus.list(path))

    def dispatch(self, cmd, arguments):
        # func obj <opt args depends on func type>
        argp = argparse.ArgumentParser(prog="ubus", description='Call ubus functions')
        argp.add_argument('func', nargs=1, type=str, help='list or call', choices=self._commands)
        argp.add_argument('path', nargs='?', type=str, help='ubus path')
        argp.add_argument('method', nargs='?', type=str, help='object function')
        self.update_paths()
        parsed, leftover = argp.parse_known_args(arguments)
        if parsed.func[0] == "call":
            if not parsed.path:
                print('Path is missing')
            elif parsed.path not in self.__paths:
                print('Unknown path %s' % parsed.path)
            elif not parsed.method:
                print('No method given!')
            else:
                pprint(self.__ubus.callp(parsed.path, parsed.method, **convert_to_dict(leftover)))
        elif parsed.func[0] == 'list':
            if parsed.path:
                print(self.__ubus.list(parsed.path))
            else:
                print(self.__ubus.list())
        else:
            return 'Unknown ubus method {}'.format(parsed.func)

    def complete(self, split):
        if not self.__paths:
            self.update_paths()

        if len(split) == 1: # call or list
            return [s + " " for s in self._commands if s.startswith(split[0])]
        elif len(split) > 1 and not split[0] in self._commands:
            return
        elif len(split) == 2: # e.g network or network.interface.lan
            return [s + " " for s in self.__paths if s.startswith(split[1])]
        elif len(split) > 2 and split[0] == 'list': # list only takes max 1 argument
            return
        elif len(split) == 3: # e.g. func of network -> status
            if split[1] in self.__paths:
                return [s + " " for s in self.__paths[split[1]] if s.startswith(split[2])]
            return
        elif len(split) > 3: # arguments of the func e.g. name=foooa
            arg = split[-1]
            if arg.find('=') == -1:
                # we extend the argument name
                return [s + "=" for s in self.__paths[split[1]][split[2]] if s.startswith(split[-1])]
            return

class Uci(SubCommand):
    pass

if __name__ == '__main__':
    Cli(url='http://192.168.122.2:80/ubus', user='root', password='yipyip').input_loop()
