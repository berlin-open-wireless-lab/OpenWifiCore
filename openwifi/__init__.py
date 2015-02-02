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
    config.add_route('confarchive', '/confarchive')
    config.add_route('openwrt_edit_config', '/openwrt_edit_config/{uuid}')

    config.include('pyramid_rpc.jsonrpc')
    config.add_jsonrpc_endpoint('api', '/api')

    config.scan()
    return config.make_wsgi_app()
