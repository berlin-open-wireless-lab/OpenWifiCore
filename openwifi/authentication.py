from openwifi.models import User, DBSession
from passlib.context import CryptContext
import json
user_pwd_context = CryptContext()

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
