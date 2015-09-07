from pyuci import Uci
from openwifi.jobserver.tasks import update_template
import unittest
import pprint
import json

# config JSON Strings
emptyConfig='{}'

# template JSON Strings
addPackage="""
            {
               "metaconf" : {
                    "change" : {
                                    "add":   ["testPackage"],
                                    "del":   []
                               },
                    "packages" : []
               }
            }
           """
delPackage="""
            {
               "metaconf" : {
                    "change" : {
                                    "add":   [],
                                    "del":   ["testPackage"]
                               },
                    "packages" : []
               }
            }
           """


generateConfig="""
{
    "metaconf": {
        "packages": [
            {
                "config": [
                    {
                        "matchcount": "",
                        "matchvalue": "SecondConfig",
                        "type": "config",
                        "ucitype": "SecondConfigType",
                        "next": "",
                        "matchtype": "name",
                        "change": {
                            "add": [
                                [
                                    "2nd Config 1st Option",
                                    "2nd Config 1st Option Value"
                                ]
                            ],
                            "del": []
                        }
                    },
                    {
                        "matchcount": "",
                        "matchvalue": "TestConfig",
                        "type": "config",
                        "ucitype": "TestConfigType",
                        "next": "",
                        "matchtype": "name",
                        "change": {
                            "add": [
                                [
                                    "2nd Option",
                                    "Option Value 2"
                                ],
                                [
                                    "1st Option",
                                    "Option Value 1"
                                ]
                            ],
                            "del": []
                        }
                    }
                ],
                "matchvalue": "TestPackage",
                "type": "package",
                "change": {
                    "add": [
                        [
                            "SecondConfig",
                            "SecondConfigType",
                            "always"
                        ],
                        [
                            "TestConfig",
                            "TestConfigType",
                            "always"
                        ]
                    ],
                    "del": []
                }
            }
        ],
        "change": {
            "add": [
                "TestPackage"
            ],
            "del": []
        }
    }
}
"""

class TestSetup(unittest.TestCase):
    def setUp(self):
        pass
    def testAddDelPackage(self):
        answer = update_template(emptyConfig,addPackage)
        assert(answer.packages['testPackage'].name=='testPackage')
        answer = update_template(answer.export_json(),delPackage)
        assert(answer.packages=={})
    def testGenereateConfig(self):
        expected_answer = '{"TestPackage": {"values": {"SecondConfig": {"2nd Config 1st Option": "2nd Config 1st Option Value", ".anonymous": false, ".name": "SecondConfig", ".type": "SecondConfigType"}, "TestConfig": {"1st Option": "Option Value 1", ".anonymous": false, ".name": "TestConfig", "2nd Option": "Option Value 2", ".type": "TestConfigType"}}}}'
        answer = update_template(emptyConfig,generateConfig)
        assert(json.loads(answer.export_json())==json.loads(expected_answer))
    # TODO: Add more tests
