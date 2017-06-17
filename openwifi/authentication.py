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

    def unauthenticated_userid(self, request):
        result = self.cookie.identify(request)
        if result:
            return result['userid']

from cornice.resource import resource, view

@resource(collection_path='/users', path='/users/{USER_ID}')
class Users(object):

    def __init__(self, request):
        self.request = request

    @view(permission = 'viewUsers')
    def collection_get(self):
        users = DBSession.query(User)
        result = []
        for user in users:
            result.append({user.login : user.id})

        return result

    @view(permission = 'addUsers')
    def collection_post(self):
        data = json.loads(self.request.body.decode())

        if 'login' not in data or 'password' not in data:
            return False

        login = data['login']
        password = data['password']
        create_user(login, password)
        return True

    @view(permission = 'modUsers')
    def post(self):
        data = json.loads(self.request.body.decode())

        if 'login' not in data and 'password' not in data:
            return False

        user_id = self.request.matchdict['USER_ID']
        user = DBSession.query(User).get(user_id)

        if 'login' in data:
            user.login = data['login']
        
        if 'password' in data:
            change_password(user, data['password'])


