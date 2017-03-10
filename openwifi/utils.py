
import uuid

UUID_NAMESPACE_OPENWRT = uuid.UUID("496e23eca4c5cf183f17fe364d45fe7b")

def generate_device_uuid(unique_identifier):
    return uuid.uuid5(UUID_NAMESPACE_OPENWRT, unique_identifier).hex

def generate_device_uuid_str(unique_identifier):
    return str(uuid.uuid5(UUID_NAMESPACE_OPENWRT, unique_identifier))
