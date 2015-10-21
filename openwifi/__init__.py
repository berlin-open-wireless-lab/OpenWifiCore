from pyramid.config import Configurator
from sqlalchemy import engine_from_config

from .models import (
    DBSession,
    Base,
    )


def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    engine = engine_from_config(settings, 'sqlalchemy.')
    DBSession.configure(bind=engine)
    Base.metadata.bind = engine
    config = Configurator(settings=settings)
    config.add_static_view('static', 'static', cache_max_age=3600)
    config.add_route('home', '/')

    config.add_route('openwrt_list', '/openwrt')
    config.add_route('openwrt_detail', '/openwrt/{uuid}')
    config.add_route('openwrt_action', '/openwrt/{uuid}/{action}')
    config.add_route('openwrt_add', '/openwrt_add')
    config.add_route('openwrt_edit_config', '/openwrt_edit_config/{uuid}')

    config.add_route('templates', '/templates')
    config.add_route('templates_add', '/templates_add')
    config.add_route('templates_assign', '/templates_assign/{id}')
    config.add_route('templates_edit', '/templates_edit/{id}')
    config.add_route('templates_delete', '/templates_delete/{id}')
    config.add_route('templates_action', '/templates/{id}/{action}')

    config.add_route('confarchive', '/confarchive')
    config.add_route('archive_edit_config', '/archive_edit_config/{id}')
    config.add_route('archive_apply_config', '/archive_apply_config/{id}')

    config.add_route('sshkeys', '/sshkeys')
    config.add_route('sshkeys_add', '/sshkeys_add')
    config.add_route('sshkeys_assign', '/sshkeys_assign/{id}')
    config.add_route('sshkeys_action', '/sshkeys/{id}/{action}')

    config.add_route('luci', '/luci')
    config.add_route('ubus', '/ubus/{command}')

    config.include('pyramid_rpc.jsonrpc')
    config.add_jsonrpc_endpoint('api', '/api')

    config.scan()
    return config.make_wsgi_app()
