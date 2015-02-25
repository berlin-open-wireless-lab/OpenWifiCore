from openwifi.jobserver.uci import Uci
import unittest


class TestSetup(unittest.TestCase):
    def setUp(self):
        self.confstring = open('example_config').read()
        self.confa = Uci()
        self.confb = Uci()
        self.confa.load_tree(self.confstring)
        self.confb.load_tree(self.confstring)

    def test_sameconfig(self):
        result = self.confa.diff(self.confb)
        assert result['newpackages'] == []
        assert result['newconfigs'] == []
        assert result['oldpackages'] == []
        assert result['oldconfigs'] == []
        assert result['newOptions'] == {}
        assert result['oldOptions'] == {}
        assert result['chaOptions'] == {}

    def test_missing_package_in_oldconf(self):
        removed_key = list(self.confa.packages.keys())[0]
        self.confa.packages.pop(removed_key)
        result = self.confa.diff(self.confb)
        assert result['newpackages'] == [removed_key]
        assert result['newconfigs'] == []
        assert result['oldpackages'] == []
        assert result['oldconfigs'] == []
        assert result['newOptions'] == {}
        assert result['oldOptions'] == {}
        assert result['chaOptions'] == {}

    def test_missing_package_in_newconf(self):
        removed_key = list(self.confa.packages.keys())[0]
        self.confb.packages.pop(removed_key)
        result = self.confa.diff(self.confb)
        assert result['newpackages'] == []
        assert result['newconfigs'] == []
        assert result['oldpackages'] == [removed_key]
        assert result['oldconfigs'] == []
        assert result['newOptions'] == {}
        assert result['oldOptions'] == {}
        assert result['chaOptions'] == {}

    def test_missing_config_in_oldconf(self):
        removed_key = list(self.confa.packages.keys())[0]
        removed_conf = list(self.confa.packages[removed_key].keys())[0]
        self.confa.packages[removed_key].pop(removed_conf)
        result = self.confa.diff(self.confb)
        assert result['newpackages'] == []
        assert result['newconfigs'] == [(removed_key, removed_conf)]
        assert result['oldpackages'] == []
        assert result['oldconfigs'] == []
        assert result['newOptions'] == {}
        assert result['oldOptions'] == {}
        assert result['chaOptions'] == {}

    def test_missing_config_in_newconf(self):
        removed_key = list(self.confa.packages.keys())[0]
        removed_conf = list(self.confa.packages[removed_key].keys())[0]
        self.confb.packages[removed_key].pop(removed_conf)
        result = self.confa.diff(self.confb)
        assert result['newpackages'] == []
        assert result['newconfigs'] == []
        assert result['oldpackages'] == []
        assert result['oldconfigs'] == [(removed_key, removed_conf)]
        assert result['newOptions'] == {}
        assert result['oldOptions'] == {}
        assert result['chaOptions'] == {}

    def test_missing_option_in_oldconf(self):
        removed_key = list(self.confa.packages.keys())[0]
        removed_conf = list(self.confa.packages[removed_key].keys())[0]
        removed_option = \
            list(self.confa.packages[removed_key][removed_conf].keys.keys())[0]
        removed_option_dict = dict()
        removed_option_dict[(removed_key, removed_conf, removed_option)] = \
            self.confa.packages[removed_key][removed_conf].keys.pop(removed_option)
        result = self.confa.diff(self.confb)
        assert result['newpackages'] == []
        assert result['newconfigs'] == []
        assert result['oldpackages'] == []
        assert result['oldconfigs'] == []
        assert result['oldOptions'] == {}
        print(result['chaOptions'])
        assert result['chaOptions'] == {}
        print(result['oldOptions'])
        print(removed_option_dict)
        assert result['newOptions'] == removed_option_dict

    def test_missing_option_in_newconf(self):
        removed_key = list(self.confa.packages.keys())[0]
        removed_conf = list(self.confa.packages[removed_key].keys())[0]
        removed_option = \
            list(self.confa.packages[removed_key][removed_conf].keys.keys())[0]
        removed_option_dict = dict()
        removed_option_dict[(removed_key, removed_conf, removed_option)] = \
                self.confb.packages[removed_key][removed_conf].keys.pop(removed_option)
        result = self.confa.diff(self.confb)
        assert result['newpackages'] == []
        assert result['newconfigs'] == []
        assert result['oldpackages'] == []
        assert result['oldconfigs'] == []
        assert result['newOptions'] == {}
        print(result['chaOptions'])
        assert result['chaOptions'] == {}
        print(result['oldOptions'])
        print(removed_option_dict)
        assert result['oldOptions'] == removed_option_dict

    def test_changed_option_in_newconf(self):
        removed_key = list(self.confa.packages.keys())[0]
        removed_conf = list(self.confa.packages[removed_key].keys())[0]
        removed_option = \
            list(self.confa.packages[removed_key][removed_conf].keys.keys())[0]
        removed_option_dict = dict()
        removed_option_dict[(removed_key, removed_conf, removed_option)] = \
            (self.confa.packages[removed_key][removed_conf].keys.get(removed_option),\
            str(self.confa.packages[removed_key][removed_conf].keys.get(removed_option))\
            + 'changed')
        self.confb.packages[removed_key][removed_conf].keys[removed_option] = \
            str(self.confa.packages[removed_key][removed_conf].keys.get(removed_option))\
            + 'changed'
        result = self.confa.diff(self.confb)
        assert result['newpackages'] == []
        assert result['newconfigs'] == []
        assert result['oldpackages'] == []
        assert result['oldconfigs'] == []
        assert result['newOptions'] == {}
        assert result['oldOptions'] == {}
        print(self.confa.packages[removed_key][removed_conf].keys[removed_option])
        print(self.confb.packages[removed_key][removed_conf].keys[removed_option])
        print(self.confa.packages[removed_key][removed_conf].export_dict(forjson=True))
        print(self.confb.packages[removed_key][removed_conf].export_dict(forjson=True))
        print(result['chaOptions'])
        print(removed_option_dict)
        assert result['chaOptions'] == removed_option_dict
