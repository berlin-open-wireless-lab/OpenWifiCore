""" Main file for OpenWifiCore """

import os
import os.path
from pkg_resources import iter_entry_points

from sqlalchemy import engine_from_config

from pyramid.config import Configurator
from pyramid.security import (
    Allow,
    Authenticated,
    Everyone,
    remember,
    forget)
from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy

from openwifi.authentication import (
    user_pwd_context,
    create_user,
    RootFactory,
    node_context,
    AllowEverybody
    )

from .models import (
    DBSession,
    Base,
    User
    )

def main(_global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    add_global_views(settings)

    add_on_device_register_actions(settings)

    engine = engine_from_config(settings, 'sqlalchemy.')
    DBSession.configure(bind=engine)
    Base.metadata.bind = engine

    if settings['openwifi.useLDAP'] == 'true':
        config = Configurator(settings=settings, root_factory=RootFactory)
        setup_ldap(config, settings)
    if settings['openwifi.useAuth'] == 'true':
        config = Configurator(settings=settings, root_factory=RootFactory)
        init_auth(config, settings)
    else:
        config = Configurator(settings=settings, root_factory=AllowEverybody)
        setup_auth(config, settings)

    config.include('pyramid_rpc.jsonrpc')
    config.add_jsonrpc_endpoint('api', '/api')
    config.add_route('execStatus', '/exec/{UUID}', factory='openwifi.node_context')
    config.add_route('login', '/login')
    config.add_route('logout', '/logout')
    config.add_route('home', '/')

    config.include('cornice')

    config.scan()

    register_database_listeners(settings)

    # Add plugin Views
    for entry_point in iter_entry_points(group='OpenWifi.plugin', name="addPluginRoutes"):
        entry_function = entry_point.load()
        entry_function(config)
        config.scan(entry_point.module_name)

    return config.make_wsgi_app()

def add_global_views(settings):
    """ add global views (used in the upper menu) """
    # Set global views as [view_callable, display_name]
    settings["OpenWifi.globalViews"] = []
    # add Global Plugin Views
    for entry_point in iter_entry_points(group='OpenWifi.plugin', name="globalPluginViews"):
        global_plugin_views = entry_point.load()
        for view in global_plugin_views:
            settings["OpenWifi.globalViews"].append(view)
            print("append view: ", view)

    #always have logout as the last entry if using auth
    from openwifi.authentication import auth_used_in_settings
    if auth_used_in_settings(settings):
        settings["OpenWifi.globalViews"].append(['logout', 'Logout'])

def add_on_device_register_actions(settings):
    """ add on device register functions by plugins """
    settings['OpenWifi.onDeviceRegister'] = []

    for entry_point in iter_entry_points(group='OpenWifi.plugin', name="onDeviceRegister"):
        on_device_register_function = entry_point.load()
        settings["OpenWifi.onDeviceRegister"].append(on_device_register_function)

def setup_auth(config, settings):
    """ configure authentication """
    secret = settings['auth.secret']
    config.set_authentication_policy(
        AuthTktAuthenticationPolicy(
            secret))
    config.set_authorization_policy(
        ACLAuthorizationPolicy())

def setup_ldap(config, settings):
    """ configure ldap authentication """
    import ldap3

    from pyramid_ldap3 import groupfinder

    secret = settings['auth.secret']
    config.set_authentication_policy(
        AuthTktAuthenticationPolicy(
            secret, callback=groupfinder))
    config.set_authorization_policy(
        ACLAuthorizationPolicy())

    config.ldap_setup(
        'ldap://localhost',
        bind='cn=admin,dc=OpenWifi,dc=local',
        passwd='ldap')

    config.ldap_set_login_query(
        base_dn='ou=Users,dc=OpenWifi,dc=local',
        filter_tmpl='(uid=%(login)s)',
        scope=ldap3.SEARCH_SCOPE_SINGLE_LEVEL)

    config.ldap_set_groups_query(
        base_dn='CN=Users,DC=OpenWifi,DC=local',
        filter_tmpl='(&(objectCategory=Groups)(member=%(userdn)s))',
        scope=ldap3.SEARCH_SCOPE_WHOLE_SUBTREE,
        cache_period=600)

def listen_conf(target, value, _oldvalue, _initiator):
    """ update master config on config change """
    from openwifi.dbHelper import updateMasterConfig
    updateMasterConfig(target, value)

def listen_conf_and_update(target, value, oldvalue, initiator):
    """ update master config and config on node """
    listen_conf(target, value, oldvalue, initiator)

    from openwifi.jobserver.tasks import update_config
    update_config.delay(target.uuid, value)

def register_database_listeners(settings):
    """ register listeners for changes to configuration """
    from sqlalchemy import event
    from openwifi.models import OpenWrt


    try:
        event.remove(OpenWrt.configuration, 'set', listen_conf)
    except:
        pass
    try:
        event.remove(OpenWrt.configuration, 'set', listen_conf_and_update)
    except:
        pass

    if 'openwifi.offline' not in settings or \
       settings['openwifi.offline'] != 'true':
        event.listen(OpenWrt.configuration, 'set', listen_conf_and_update)
    else:
        event.listen(OpenWrt.configuration, 'set', listen_conf)

def init_auth(config, settings):
    """ load password hash settings and generate default users if no users available """
    user_pwd_context.load_path(os.path.dirname(__file__) + os.sep + ".." + os.sep + "crypt.ini")

    # if no user in database create admin:admin with admin priv
    if not DBSession.query(User).first():
        user = create_user('admin', 'admin')
        user.is_admin = True
        from openwifi.models import NodeAccess
        new_access = NodeAccess('[{"type":"pathstring", "access":"rw", "string":".*"}]', user=user)
        new_access.access_all_nodes = True
        DBSession.add(new_access)
        import transaction
        transaction.commit()

    from openwifi.authentication import OpenWifiAuthPolicy

    config.set_authentication_policy(OpenWifiAuthPolicy(settings))
    config.set_authorization_policy(ACLAuthorizationPolicy())
