from .models import (
    DBSession,
    OpenWrt
    )

from cornice import Service

listNodes = Service(name='nodes',
                    path='/list_nodes',
                    description='Get list of Nodes')

@listNodes.get()
def get_info(request):
    """ Return List of registered Nodes
    """
    nodes = DBSession.query(OpenWrt)
    nodeUUIDs = []
    for node in nodes:
        nodeUUIDs.append(str(node.uuid))

    return nodeUUIDs
