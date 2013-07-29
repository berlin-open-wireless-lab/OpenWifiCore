from pyramid_layout.layout import layout_config

@layout_config(name='base', template='openwifi:templates/base_layout.jinja2')
class BaseLayout(object):
    page_title = 'openWifi'

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.home_url = request.application_url
