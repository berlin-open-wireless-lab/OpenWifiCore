import sys

from astroid import MANAGER, scoped_nodes
from astroid.builder import AstroidBuilder
from sqlalchemy.orm import Session


def register(_linter):
    pass

def transform(cls):
    if cls.name == 'scoped_session':
        builder = AstroidBuilder(MANAGER)
        module_node = builder.module_build(sys.modules[Session.__module__])
        session_cls_node = [
            c for c in module_node.get_children()
            if getattr(c, "type", None) == "class" and c.name == Session.__name__
        ][0]

        for prop in Session.public_methods:
            cls.locals[prop] = [
                c for c in session_cls_node.get_children() 
                if getattr(c, "type", None) == "method" and c.name == prop
            ]

MANAGER.register_transform(scoped_nodes.Class, transform)
