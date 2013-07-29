
from wtforms import Form, TextField, IntegerField

class AccessPointAddForm(Form):
    name = TextField('name')
    hardware = TextField('hardware')
    address = TextField('address')
    radios_2g = IntegerField('2ghz Radios')
    radios_5g = IntegerField('5ghz Radios')
