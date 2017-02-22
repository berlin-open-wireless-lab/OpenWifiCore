from pyramid.config import Configurator
from sqlalchemy import engine_from_config

import ldap3

from pyramid_ldap3 import (
    get_ldap_connector,
    groupfinder)

from pyramid.security import (
   Allow,
   Authenticated,
   remember,
   forget)

from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy

from .models import (
    DBSession,
    Base,
    )

from pkg_resources import iter_entry_points

class RootFactory(object):
    __acl__ = [(Allow, Authenticated, 'view')]
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
    config = Configurator(settings=settings, root_factory=RootFactory)

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


    config.include('pyramid_rpc.jsonrpc')
    config.add_jsonrpc_endpoint('api', '/api')

    config.include('cornice')

    config.scan()

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

