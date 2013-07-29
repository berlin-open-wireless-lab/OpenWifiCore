from sqlalchemy import (
    Column,
    Integer,
    Text,
    ForeignKey,
    Table,
    )

from sqlalchemy.ext.declarative import declarative_base

from sqlalchemy.orm import (
    backref,
    relationship,
    scoped_session,
    sessionmaker,
    )

from zope.sqlalchemy import ZopeTransactionExtension

DBSession = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
Base = declarative_base()

essid_association_table = Table('essid_association', Base.metadata,
        Column('radio_id', Integer, ForeignKey('radio.id')),
        Column('essid_id', Integer, ForeignKey('essid.id')))

class AccessPoint(Base):
    __tablename__ = 'accesspoint'
    id = Column(Integer, primary_key=True)
    name = Column(Text, unique=True)
    host = Column(Text) # ip or host
    sshkey = Column(Text) # private key to access this ap
    sshhostkey = Column(Text) # remote host key
    hardware = Column(Text)
    radio = relationship("Radio", backref='accesspoint')

    def __init__(self, name, hardware):
        self.name = name
        self.hardware = hardware

class Radio(Base):
    __tablename__ = 'radio'
    id = Column(Integer, primary_key=True)
    ap_id = Column(Integer, ForeignKey('accesspoint.id'))
    hardware = Column(Text)
    band = Column(Integer) # 2 => 2ghz, 5 => 5ghz
    channel = Column(Integer)
    essid = relationship("Essid", secondary=essid_association_table)
    txpower = Column(Integer)

class Essid(Base):
    __tablename__ = 'essid'
    id = Column(Integer, primary_key=True)
    essid = Column(Text)
    bssid = Column(Text)

