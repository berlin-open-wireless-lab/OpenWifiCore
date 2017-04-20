import uuid
import random
import string

UUID_NAMESPACE_OPENWRT = uuid.UUID("496e23eca4c5cf183f17fe364d45fe7b")

def generate_device_uuid(unique_identifier):
    return uuid.uuid5(UUID_NAMESPACE_OPENWRT, unique_identifier).hex

def generate_device_uuid_str(unique_identifier):
    return str(uuid.uuid5(UUID_NAMESPACE_OPENWRT, unique_identifier))

def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))
