from marshmallow import Schema, fields, post_load
from sqlalchemy import types
from sqlalchemy.orm import relationship
from sqlalchemy.schema import Column
from sqlalchemy.sql import func

from database.connect import Base


class Client(Base):
    __tablename__ = "Client"

    id = Column(types.String(80), primary_key=True, nullable=False)
    items = relationship("Item", backref="Client")
    email = Column(types.String(80), nullable=False)
    email_alerts = Column(types.Boolean, default=True)
    alert_time_range_start = Column(types.Integer, nullable=True)
    alert_time_range_end = Column(types.Integer, nullable=True)
    alert_time_zone = Column(types.String(80), nullable=True)
    alert_range_enabled = Column(types.Boolean, default=False)
    phone_number = Column(types.String(11), nullable=False)
    phone_alerts = Column(types.Boolean, default=True)
    threshold_inventory = Column(types.Integer, nullable=True, default=1)
    last_updated = Column(types.DateTime(timezone=True), nullable=True)
    updates_sent = Column(types.Integer, nullable=True, default=0)
    created_at = Column(types.DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Client {self.name}:{self.phone_number}, {self.email}>"


class ClientSchema(Schema):  # type: ignore
    id = fields.Str()
    items = fields.List(fields.Nested("ItemSchema"))
    email = fields.Str()
    email_alerts = fields.Boolean()
    alert_time_range_start = fields.Int()
    alert_time_range_end = fields.Int()
    alert_time_zone = fields.Str()
    alert_range_enabled = fields.Boolean()
    phone_number = fields.Str()
    phone_alerts = fields.Boolean()
    threshold_inventory = fields.Int()
    last_updated = fields.DateTime()
    updates_sent = fields.Int()
    created_at = fields.DateTime()

    @post_load
    def make_object(self, data, **kwargs):
        return Client(**data)
