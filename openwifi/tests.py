import unittest

from pyramid import testing
import json


#class TestMyView(unittest.TestCase):
#    def setUp(self):
#        self.config = testing.setUp()
#        from sqlalchemy import create_engine
#        engine = create_engine('sqlite://')
#        from .models import (
#            Base,
#            MyModel,
#            )
#        DBSession.configure(bind=engine)
#        Base.metadata.create_all(engine)
#        with transaction.manager:
#            model = MyModel(name='one', value=55)
#            DBSession.add(model)
#
#    def tearDown(self):
#        DBSession.remove()
#        testing.tearDown()
#
#    def test_it(self):
#        from .views import my_view
#        request = testing.DummyRequest()
#        info = my_view(request)
#        self.assertEqual(info['one'].name, 'one')
#        self.assertEqual(info['project'], 'openwifi')

from pyramid.paster import (
    get_appsettings,
    setup_logging,
    )
from paste.deploy.loadwsgi import appconfig

def sbetup():
    from pyramid.config import Configurator
    from sqlalchemy import engine_from_config
    import os

    ROOT_PATH = os.path.dirname(__file__)
    settings = appconfig('config:' + os.path.join(ROOT_PATH, 'test.ini'))
    engine = engine_from_config(settings, prefix='sqlalchemy.')

    print('Creating the tables on the test database %s' % engine)

    config = Configurator(settings=settings)


class JSONRPCTest(unittest.TestCase):
    def setUp(self):
        from openwifi import main
        from webtest import TestApp
        self.config = testing.setUp()
        from sqlalchemy import create_engine
        import os
        #engine = create_engine('sqlite://')
        from .models import (
                Base,
                DBSession,
                )
        #DBSession.configure(bind=engine)
        #Base.metadata.create_all(engine)
        ROOT_PATH = os.path.dirname(__file__)
        settings = appconfig('config:' + os.path.join(ROOT_PATH, 'test.ini'))
        print(settings)
        self.app = main({}, **settings)
        self.app = TestApp(self.app)

    def tearDown(self):
        testing.tearDown()

    def _callFUT(self, method, params, rpcid=5, version='2.0',
                 path='/api', content_type='application/json'):
        body = {}
        if rpcid is not None:
            body['id'] = rpcid
        if version is not None:
            body['jsonrpc'] = version
        if method is not None:
            body['method'] = method
        if params is not None:
            body['params'] = params
        resp = self.app.post(path, content_type=content_type,
                        params=json.dumps(body))
        if rpcid is not None:
            self.assertEqual(resp.status_int, 200)
            self.assertEqual(resp.content_type, 'application/json')
            result = json.loads(resp.body.decode())
            self.assertEqual(result['jsonrpc'], '2.0')
            self.assertEqual(result['id'], rpcid)
        else:
            self.assertEqual(resp.status_int, 204)
            result = resp.body
        return result

    def test_generate_uuid(self):
        assert self._callFUT('uuid_generate', ['123'])['result']['uuid'] == "0016262d334b58be85b7a7647d2c63fc", "Result is %s" % self._callFUT('uuid_generate', ['123']) 

    def test_hello(self):
        assert self._callFUT('hello', [])['result'] == 'openwifi'

class deviceDetectAndRegisterTest(unittest.TestCase):
    def setUp(self):
        import docker
        import os.path
        import os
        running_user_id = os.getuid()
        
        self.dockerClient = docker.from_env(version='auto')
        self.dockerClient.images.pull("openwifi/openwificore")
        self.dockerClient.images.pull("openwifi/ledecontainer")
        path = os.path.split(os.path.split(os.path.realpath(__file__))[0])[0]

        self.openwifi = self.dockerClient.containers.run("openwifi/openwificore", 
                volumes={path: {'bind': '/OpenWifi', 'mode': 'rw'}}, 
                ports={'6543/tcp': 6543}, environment={'OPENWIFI_UID':running_user_id},\
                      detach=True)

    def testRegister(self):
        import requests
        import time

        # wait until server is ready
        while True:
            try:
                r = requests.get('http://localhost:6543/nodes')
            except:
                time.sleep(2)
                continue

            break

        self.assertEqual(r.text, "[]")

        self.lede = self.dockerClient.containers.run("openwifi/ledecontainer", "/sbin/init", detach=True)
        while not self.lede.exec_run('ash -c "ps|grep \\"[o]penwifi\\""'):
            time.sleep(2)
        
        self.lede.exec_run('/etc/init.d/openwifi-boot-notifier restart')
        time.sleep(10)

        r = requests.get('http://localhost:6543/nodes')

        uuid = self.lede.exec_run('uci get openwifi.@device[0].uuid').decode('utf8').strip('\n')
        self.assertEqual(r.text, '["'+uuid+'"]')

    def tearDown(self):
        pass
        if self.lede:
            self.lede.kill()
            self.lede.remove()
        if self.openwifi:
            self.openwifi.kill()
            self.openwifi.remove()

class userModTest(unittest.TestCase):
    def setUp(self):
        from openwifi import main
        from webtest import TestApp
        self.config = testing.setUp()
        from sqlalchemy import create_engine
        import os

        from .models import (
                Base,
                DBSession,
                )

        ROOT_PATH = os.path.dirname(__file__)
        settings = appconfig('config:' + os.path.join(ROOT_PATH, 'test.ini'))
        settings['openwifi.useAuth'] = 'true'
        print(settings)
        self.app = main({}, **settings)
        self.app = TestApp(self.app)

    def tearDown(self):
        testing.tearDown()

    def testAddUser(self):
        from six.moves import http_cookiejar
        from webtest.app import CookiePolicy

        self.app.post_json('/login', {'login':'admin', 'password':'admin'})
        resp = self.app.get('/users')
        usersBefore = json.loads(resp.text)
        adminId = usersBefore['admin']
        admin_cookiejar = self.app.cookiejar


        resp = self.app.post_json('/users', {"login":"testuser", "password":"testpassword"})

        import transaction
        transaction.commit()

        newUserId = json.loads(resp.text)
        resp = self.app.get('/users')
        usersAfter = json.loads(resp.text)
        
        self.assertEqual(usersAfter, {'admin':adminId, 'testuser': newUserId})

        user_cookiejar =  http_cookiejar.CookieJar(policy=CookiePolicy())
        self.app.cookiejar = user_cookiejar

        self.app.post_json('/login', {'login':'testuser', 'password': 'testpassword'})

        # check that normal user cannot manage users
        self.app.get('/users', expect_errors=True)
        self.app.get('/users/'+adminId, expect_errors=True)
        self.app.delete('/users/'+adminId, expect_errors=True)
        self.app.post('/users/'+adminId, params='{"login":"bla", "password":"blubb"}', content_type='text/json', expect_errors=True)

        self.app.cookiejar = admin_cookiejar

        resp = self.app.delete('/users/'+newUserId)

        resp = self.app.get('/users')
        usersAfter = json.loads(resp.text)

        self.assertEqual(usersAfter, usersBefore)

class fine_grained_access_test(unittest.TestCase):
    def setUp(self):
        from openwifi import main
        from webtest import TestApp
        self.config = testing.setUp()
        from sqlalchemy import create_engine
        from openwifi.models import DBSession
        DBSession.close_all()

        import os

        from .models import (
                Base,
                DBSession,
                )

        ROOT_PATH = os.path.dirname(__file__)
        settings = appconfig('config:' + os.path.join(ROOT_PATH, 'test.ini'))
        settings['openwifi.useAuth'] = 'true'
        settings['openwifi.offline'] = 'true'
        print(settings)
        self.app = main({}, **settings)
        self.app = TestApp(self.app)

        self.app.post_json('/login', {'login':'admin', 'password':'admin'})
        resp = self.app.get('/users')
        self.admin_id = json.loads(resp.text)['admin']
        self.app.post_json('/access', {'access_all_nodes': True, 'userid': self.admin_id})

        example_config_path = os.path.join(ROOT_PATH, 'tests', 'exampleConfig.json')
        example_config = open(example_config_path).read()
        new_node_dict = {'name':'testnode',
                         'address':'localhost',
                         'distribution':'none',
                         'version':'none',
                         'login':'none',
                         'password':'none'}

        resp = self.app.post_json('/nodes', new_node_dict)
        print(resp)
        node_id = json.loads(resp.text)
        self.app.post_json('/nodes/'+node_id, {'configuration':example_config})
    
    def test(self):
        pass

    def tearDown(self):
        testing.tearDown()
