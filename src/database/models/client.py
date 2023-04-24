from marshmallow import Schema, fields, post_load
from sqlalchemy import types
from sqlalchemy.orm import relationship
from sqlalchemy.schema import Column
from sqlalchemy.sql import func

from database.connect import Base


class Client(Base):
    __tablename__ = "Client"

    id = Column(types.Integer, primary_key=True)
    name = Column(types.String(80), unique=True, nullable=False)
    items = relationship("Item", backref="Client")
    email = Column(types.String(80), unique=True, nullable=False)
    phone_number = Column(types.String(11), unique=True, nullable=False)
    last_updated = Column(types.DateTime(timezone=True), nullable=True)
    created_at = Column(types.DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Client {self.name}:{self.phone_number}, {self.email}>"


class ClientShema(Schema):  # type: ignore
    id = fields.Int()
    name = fields.Str()
    email = fields.Str()
    phone_number = fields.Str()
    last_updated = fields.DateTime()
    created_at = fields.DateTime()

    @post_load
    def make_object(self, data, **kwargs):
        return Client(**data)
