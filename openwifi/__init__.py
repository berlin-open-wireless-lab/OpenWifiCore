from pyramid.config import Configurator
from sqlalchemy import engine_from_config

from pyramid.security import (
   Allow,
   Authenticated,
   Everyone,
   remember,
   forget)

from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy

from .models import (
    DBSession,
    Base,
    User
    )

from openwifi.authentication import user_pwd_context, create_user
import os, os.path

from pkg_resources import iter_entry_points

class RootFactory(object):
    def __init__(self, request):
        from openwifi.authentication import auth_not_used
        if auth_not_used(request):
            self.__acl__ = [(Allow, Everyone, ('view', 'node_access', 'node_add'))]
        else:
            self.__acl__ = [(Allow, Authenticated, 'view')]
            self.__acl__.append((Allow, 'group:admin', 'addUsers'))
            self.__acl__.append((Allow, 'group:admin', 'viewUsers'))
            self.__acl__.append((Allow, 'group:admin', 'modUsers'))
            self.__acl__.append((Allow, 'group:admin', 'modUsers'))
            self.__acl__.append((Allow, 'group:admin', 'control_access'))
            self.__acl__.append((Allow, 'group:client_side', 'node_add'))
            self.__acl__.append((Allow, 'group:admin', 'node_add'))

class node_context(RootFactory):
    def __init__(self, request):
        super().__init__(request)

        uuid = None

        if 'UUID' in request.matchdict:
            uuid = request.matchdict['UUID']
        elif 'uuid' in request.matchdict:
            uuid = request.matchdict['uuid']

        if uuid:
            self.__acl__.append((Allow, 'node:'+uuid, 'node_access'))

        from openwifi.authentication import auth_not_used as auth_not_used
        if auth_not_used(request):
            self.__acl__.append((Allow, Everyone, 'node_access'))
            self.__acl__.append((Allow, Everyone, ''))

class AllowEverybody(object):
    __acl__ = [(Allow, Everyone, ('view', 'node_access', 'node_add'))]
    def __init__(self, request):
        pass

def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    configure_global_views(settings)

    registerOnDeviceRegisterFunctions(settings)

    engine = engine_from_config(settings, 'sqlalchemy.')
    DBSession.configure(bind=engine)
    Base.metadata.bind = engine

    if settings['openwifi.useLDAP'] == 'true':
        config = Configurator(settings=settings, root_factory=RootFactory)
        setupLDAP(config, settings)
    if settings['openwifi.useAuth'] == 'true':
        config = Configurator(settings=settings, root_factory=RootFactory)
        init_auth(config, settings)
    else:
        config = Configurator(settings=settings, root_factory=AllowEverybody)
        setupAuth(config)

    config.include('pyramid_rpc.jsonrpc')
    config.add_jsonrpc_endpoint('api', '/api')
    config.add_route('execStatus', '/exec/{UUID}', factory='openwifi.node_context')
    config.add_route('login', '/login')
    config.add_route('logout', '/logout')
    config.add_route('home', '/')

    config.include('cornice')

    config.scan()

    registerDatabaseListeners(settings)

    # Add plugin Views
    for entry_point in iter_entry_points(group='OpenWifi.plugin', name="addPluginRoutes"):
        entry_function = entry_point.load()
        entry_function(config)
        config.scan(entry_point.module_name)

    return config.make_wsgi_app()

def configure_global_views(settings):
    # Set global views as [view_callable, display_name]
    settings["OpenWifi.globalViews"]=[]
    # add Global Plugin Views
    for entry_point in iter_entry_points(group='OpenWifi.plugin', name="globalPluginViews"):
        globalPluginViews = entry_point.load()
        for view in globalPluginViews:
            settings["OpenWifi.globalViews"].append(view)
            print("append view: ", view)

    #always have logout as the last entry
    settings["OpenWifi.globalViews"].append(['logout','Logout'])

def registerOnDeviceRegisterFunctions(settings):
    settings['OpenWifi.onDeviceRegister'] = []

    for entry_point in iter_entry_points(group='OpenWifi.plugin', name="onDeviceRegister"):
        devRegFunction = entry_point.load()
        settings["OpenWifi.onDeviceRegister"].append(devRegFunction)

def setupAuth(config):
    # REPLACE WITH YOUR OWN SECRET!
    config.set_authentication_policy(
        AuthTktAuthenticationPolicy(
            'seekr1t'))
    config.set_authorization_policy(
    ACLAuthorizationPolicy())

def setupLDAP(config, settings):
    import ldap3

    from pyramid_ldap3 import (
        get_ldap_connector,
        groupfinder)

    # REPLACE WITH YOUR OWN SECRET!
    config.set_authentication_policy(
        AuthTktAuthenticationPolicy(
            'seekr1t', callback=groupfinder))
    config.set_authorization_policy(
    ACLAuthorizationPolicy())

    config.ldap_setup(
        'ldap://localhost',
        bind='cn=admin,dc=OpenWifi,dc=local',
        passwd='ldap')

    config.ldap_set_login_query(
        base_dn='ou=Users,dc=OpenWifi,dc=local',
        filter_tmpl='(uid=%(login)s)',
        #filter_tmpl='(sAMAccountName=%(login)s)',
        scope=ldap3.SEARCH_SCOPE_SINGLE_LEVEL)

    config.ldap_set_groups_query(
        base_dn='CN=Users,DC=OpenWifi,DC=local',
        filter_tmpl='(&(objectCategory=Groups)(member=%(userdn)s))',
        scope=ldap3.SEARCH_SCOPE_WHOLE_SUBTREE,
        cache_period=600)

def registerDatabaseListeners(settings):
    from sqlalchemy import event
    from openwifi.models import OpenWrt
    
    if 'openwifi.offline' not in settings or \
       settings['openwifi.offline'] != 'true':
        @event.listens_for(OpenWrt.configuration, 'set')
        def listenConf(target, value, oldvalue, initiator):
            from openwifi.dbHelper import updateMasterConfig
            updateMasterConfig(target, value)

            from openwifi.jobserver.tasks import update_config
            update_config.delay(target.uuid)
    else:
        @event.listens_for(OpenWrt.configuration, 'set')
        def listenConf(target, value, oldvalue, initiator):
            from openwifi.dbHelper import updateMasterConfig
            updateMasterConfig(target, value)

def init_auth(config, settings):
    user_pwd_context.load_path(os.path.dirname(__file__) + os.sep + ".." + os.sep + "crypt.ini")

    # if no user in database create admin:admin with admin priv
    if not DBSession.query(User).first():
        print('create admin:admin user')
        user = create_user('admin', 'admin')
        user.is_admin = True
        import transaction
        transaction.commit()

    from openwifi.authentication import OpenWifiAuthPolicy

    config.set_authentication_policy(OpenWifiAuthPolicy(settings))
    config.set_authorization_policy(ACLAuthorizationPolicy())
