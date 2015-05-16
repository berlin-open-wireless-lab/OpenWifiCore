from pyuci import Uci
from openwifi.jobserver.tasks import update_template
import unittest

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
class TestSetup(unittest.TestCase):
    def setUp(self):
        pass
    def testAddDelPackage(self):
        answer = update_template(emptyConfig,addPackage)
        assert(answer.packages['testPackage'].name=='testPackage')
        answer = update_template(answer.export_json(),delPackage)
        assert(answer.packages=={})
    # TODO: Add more tests
