
from wtforms import Form, TextField, IntegerField

class AccessPointAddForm(Form):
    name = TextField('name')
    hardware = TextField('hardware')
    address = TextField('address')
    radios_2g = IntegerField('2ghz Radios')
    radios_5g = IntegerField('5ghz Radios')

class AccessPointEditForm(Form):
    name = TextField('name')
    hardware = TextField('hardware')
    address = TextField('address')
    sshkey = TextField('sshkey') # private key to access this ap
    sshhostkey = TextField('sshhostkey') # remote host key
