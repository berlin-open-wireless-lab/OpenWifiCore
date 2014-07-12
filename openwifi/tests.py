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
