from cornice.resource import resource, view
from openwifi.models import DBSession, Service

@resource(collection_path='/service', path='/service/{ID}', permission='view')
class service_api:

    def __init__(self, request):
        self.request = request
        self.arguments = ['queries', 'name', 'capability_script']

    def collection_get(self):
        services = DBSession.query(Service)
        response = {}

        for service in services:
            service_data = {}
            service_data['queries'] = service.get_queries()
            service_data['name'] = service.name
            service_data['capability_script'] = service.capability_script

            response[service.id] = service_data

        return response

    @view(validators=('validate_all_arguments',))
    def collection_post(self):
        post_data = self.request.json_body

        name = post_data['name']
        queries = post_data['queries']
        capability_script = post_data['capability_script']

        new_service = Service(name, queries, capability_script)
        DBSession.add(new_service)

    @view(validators=('validate_request','validate_any_arguments'))
    def post(self):
        post_data = self.request.json_body

        if 'name' in post_data:
            self.service.name = post_data['name']
        if 'queries' in post_data:
            self.service.set_queries(post_data['queries'])
        if 'capability_script' in post_data:
            self.service.capability_script = post_data['capability_script']

    def validate_all_arguments(self, request, **kw):
        if not all(i in request.json_body for i in self.arguments):
            request.errors.add('querystring','query','missing arguments')

    def validate_any_arguments(self, request, **kw):
        if not any(i in request.json_body for i in self.arguments):
            request.errors.add('querystring','query','missing arguments')

    def validate_request(self, request, **kw):
        id = self.request.matchdict['ID']
        service = DBSession.query(Service).get(id)

        if not service:
            request.errors.add('url', 'id', 'No service for id '+id)
        else:
            self.service = service

