from openwifi.models import User, DBSession, NodeAccess, ApiKey, OpenWrt
from passlib.context import CryptContext

import json
user_pwd_context = CryptContext()

def auth_not_used(request):
    settings = request.registry.settings
    return settings['openwifi.useLDAP'] == 'false' and \
           settings['openwifi.useAuth'] == 'false'

def get_nodes(request):
    try:
        if request.user:
            return get_nodes_of_user_or_api_key(request.user)

        if request.apikey:
            return get_nodes_of_user_or_api_key(request.apikey)
    except AttributeError:
        pass

    if auth_not_used(request):
       return DBSession.query(OpenWrt)

    # if nothing else was found -> expect no nodes
    return []

def get_nodes_of_user_or_api_key(user_apikey):
    nodes = []
    for access in user_apikey.access:
        nodes.extend(access.nodes)

        if access.access_all_nodes:
            return DBSession.query(OpenWrt)

    return nodes

def get_node_by_request(request):

    if 'UUID' in request.matchdict:
        uuid = request.matchdict['UUID']

    if 'uuid' in request.matchdict:
        uuid = request.matchdict['uuid']

    if uuid:
        return DBSession.query(OpenWrt).get(uuid)

def get_user_by_id(id):
    try:
        return DBSession.query(User).get(id)
    except:
        return None

def get_user_by_login(login):
    try:
        return DBSession.query(User).filter(User.login == login).first()
    except:
        return None

def get_apikey_by_id(id):
    try:
        return DBSession.query(ApiKey).get(id)
    except:
        return None

def get_apikey_by_key(key):
    try:
        return DBSession.query(ApiKey).filter(ApiKey.key == key).first()
    except:
        return None

def get_access_by_id(aid):
    try:
        return DBSession.query(NodeAccess).get(aid)
    except:
        return None

def create_user(login, password):
    hash = user_pwd_context.hash(password)
    new_user = User(login, hash)
    DBSession.add(new_user)
    return new_user

def check_password(login, password):
    user = DBSession.query(User).filter(User.login == login).first()
    if not user:
        return False

    valid_password, new_hash = user_pwd_context.verify_and_update(password, user.hash)

    if not valid_password:
        return False

    if new_hash:
        user.hash = new_hash
    return True

def change_password(user, password):
    hash = user_pwd_context.hash(password)
    user.hash = hash

from pyramid.authentication import AuthTktCookieHelper, CallbackAuthenticationPolicy
from pyramid.security import Everyone, Authenticated
from pyramid.settings import asbool

def asint(s):
    try:
        b = int(s)
    except:
        b = None
    return b

class OpenWifiAuthPolicy(CallbackAuthenticationPolicy):
    def __init__(self, settings):
        self.cookie = AuthTktCookieHelper(
            settings.get('auth.secret'),
            cookie_name = settings.get('auth.token') or 'auth_tkt',
            secure = asbool(settings.get('auth.secure')),
            timeout = asint(settings.get('auth.timeout')),
            reissue_time = asint(settings.get('auth.reissue_time')),
            max_age = asint(settings.get('auth.max_age')),
        )

    def remember(self, request, userid, **kw):
        return self.cookie.remember(request, userid, **kw)

    def forget(self, request):
        return self.cookie.forget(request)

    # callback to verify login
    def callback(self, userid, request):
        from openwifi.models import DBSession, User, ApiKey
        groups = []

        request.user = None
        request.apikey = None

        if userid.startswith('apikey:'):
            apikey_key = userid[7:]
            apikey = DBSession.query(ApiKey).filter(ApiKey.key == apikey_key).first()
            groups.append('group:apikey')
            if not apikey:
                return None

            request.apikey = apikey

        if userid.startswith('user:'):
            user_login=userid[5:]
            user = DBSession.query(User).filter(User.login == user_login).first()
            groups.append('group:users')

            if not user:
                return None

            request.user = user

            if user.is_admin:
                groups.append('group:admin')

        if userid == 'group:client_side':
            groups.append('group:client_side')

        from openwifi import node_context
        if type(request.context) == node_context:
            nodes = get_nodes(request)
            for node in nodes:
                groups.append('node:'+str(node.uuid))

        return groups

    def unauthenticated_userid(self, request):
        # check for api key
        if 'key' in request.GET:
            return 'apikey:' + request.GET['key']

        # check for client side certificate
        if all(key in request.headers for key in ["X-Forwarded-Proto", "Verified"]):
            if request.headers["X-Forwarded-Proto"] == "https" and \
                    request.headers["Verified"] == "SUCCESS":
                return 'group:client_side'

        # check for cookie for login
        result = self.cookie.identify(request)
        if result:
            return 'user:' + result['userid']

from cornice.resource import resource, view

@resource(collection_path='/users', path='/users/{USER_ID}')
class Users(object):

    def __init__(self, request):
        self.request = request

    @view(permission = 'viewUsers')
    def collection_get(self):
        users = DBSession.query(User)
        result = {}
        for user in users:
            result[user.login] = user.id

        return result

    @view(permission = 'addUsers')
    def collection_post(self):
        data = self.request.json_body

        if 'login' not in data or 'password' not in data:
            return False

        login = data['login']
        password = data['password']
        user = create_user(login, password)
        return user.id

    @view(permission = 'modUsers')
    def post(self):
        data = self.request.json_body

        if not any(key in data for key in ['login', 'password', 'admin']):
            return False

        user_id = self.request.matchdict['USER_ID']
        user = DBSession.query(User).get(user_id)

        if 'login' in data:
            user.login = data['login']
        
        if 'password' in data:
            change_password(user, data['password'])

        if 'admin' in data:
            user.is_admin = data['admin']

    @view(permission = 'viewUsers')
    def get(self):
        user_id = self.request.matchdict['USER_ID']
        user = DBSession.query(User).get(user_id)
        return {'login': user.login, 'admin': user.is_admin}

    @view(permission = 'addUsers')
    def delete(self):
        user_id = self.request.matchdict['USER_ID']
        if user_id == self.request.user.id:
            return "user cannot delete itself"

        user = DBSession.query(User).get(user_id)
        DBSession.delete(user)

@resource(collection_path='/access', path='/access/{ACCESS_ID}', permission='control_access')
class Control_Access:

    def __init__(self, request):
        self.request = request

    def get(self):
        aid = self.request.matchdict['ACCESS_ID']
        ac = DBSession.query(NodeAccess).get(aid)
        return self.access_to_dict(ac)

    def delete(self):
        aid = self.request.matchdict['ACCESS_ID']
        ac = DBSession.query(NodeAccess).get(aid)

        DBSession.delete(ac)
        return True

    def post(self):
        aid = self.request.matchdict['ACCESS_ID']
        access = get_access_by_id(aid)
        post_data = self.request.json_body
        
        if 'data' in post_data:
            access.data = post_data['data']
        if 'userid' in post_data:
            access.user = get_user_by_id(post_data['userid'])
        if 'apikeyid' in post_data:
            access.apikey = get_apikey_by_id(post_data['apikeyid'])
        if 'access_all_nodes' in post_data:
            access.access_all_nodes = post_data['access_all_nodes']

        return True

    def collection_get(self):
        access = DBSession.query(NodeAccess)
        result = {}
        for ac in access:
            ac_dict = self.access_to_dict(ac)
            result[ac.id] = ac_dict
        return result

    def access_to_dict(self, ac):
        ac_dict = {}
        ac_dict['data'] = ac.data
        ac_dict['all_nodes'] = ac.access_all_nodes
        ac_dict['nodes'] = list(map(lambda n: str(n.uuid), ac.nodes))
        ac_dict['users'] = list(map(lambda u: {str(u.id): u.login}, ac.user))
        ac_dict['apikeys'] = list(map(lambda a: {str(a.id): a.key}, ac.apikey))
        
        return ac_dict

    def collection_post(self):
        post_data = self.request.json_body
        data = ""
        user = None
        apikey = None
        
        if 'data' in post_data:
            data = post_data['data']
        if 'userid' in post_data:
            user = get_user_by_id(post_data['userid'])
        if 'apikeyid' in post_data:
            apikey = get_apikey_by_id(post_data['apikeyid'])

        new_node_access = NodeAccess(data, user=user, apikey=apikey)

        if 'access_all_nodes' in post_data:
            new_node_access.access_all_nodes = post_data['access_all_nodes']

        DBSession.add(new_node_access)
        return True

from cornice import Service

access_add_user_by_id = Service(name='access_add_user_by_id',
                                path='/access/{ACCESS_ID}/user/{UID}',
                                description="add a user to a node access by id",
                                permission='control_access')
@access_add_user_by_id.post()
def access_add_user_by_id_post(request):
    aid = request.matchdict['ACCESS_ID']
    uid = request.matchdict['UID']
    
    access = get_access_by_id(aid)
    user = get_user_by_id(uid)

    if not access or not user:
        return False

    access.user.append(user)
    return True

access_add_apikey_by_id = Service(name='access_add_apikey_by_id',
                                  path='/access/{ACCESS_ID}/apikey/{APIKEY_ID}',
                                  description="add an apikey to a node access by id",
                                  permission='control_access')
@access_add_apikey_by_id.post()
def access_add_apikey_by_id_post(request):
    aid = request.matchdict['ACCESS_ID']
    api_id = request.matchdict['APIKEY_ID']
    
    access = get_access_by_id(aid)
    apikey = get_access_by_id(api_id)

    if not access or not apikey:
        return False

    access.apikey.append(apikey)
    return True

access_add_node_by_uuid = Service(name='access_add_node_by_uuid',
                                path='/access/{ACCESS_ID}/node/{UUID}',
                                description="add a node to a node access by id",
                                permission='control_access')
@access_add_node_by_uuid.post()
def access_add_node_by_uuid_post(request):
    aid = request.matchdict['ACCESS_ID']
    
    access = get_access_by_id(aid)
    node = get_node_by_request(request)

    if not access or not node:
        return False

    access.nodes.append(node)
    return True
