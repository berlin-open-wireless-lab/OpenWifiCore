from openwifi.models import User, DBSession
from passlib.context import CryptContext
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

    user.hash = new_hash
    return True

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
