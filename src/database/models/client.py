from marshmallow import Schema, fields, post_load
from sqlalchemy import ForeignKey, types
from sqlalchemy.orm import relationship
from sqlalchemy.schema import Column
from sqlalchemy.sql import func

from database.connect import Base
from database.models.item_association import ItemAssociationTable


class TrackingItem(Base):
    __tablename__ = "TrackingItem"

    id = Column(types.Integer, primary_key=True)
    client_id = Column(types.String, ForeignKey("Client.id"))
    nc_code = Column(types.String(80), nullable=False)


class TrackingItemSchema(Schema):  # type: ignore
    id = fields.Int()
    nc_code = fields.Str()

    @post_load
    def make_object(self, data, **kwargs):
        return TrackingItem(**data)


class Client(Base):
    __tablename__ = "Client"

    id = Column(types.String(80), primary_key=True, nullable=False)
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
    plan = Column(types.String(80), nullable=True)
    next_billing_date = Column(types.DateTime(timezone=True), nullable=True)
    next_billing_amount = Column(types.Float, default=0.0)
    has_paid = Column(types.Boolean, default=False)
    created_at = Column(types.DateTime(timezone=True), server_default=func.now())
    items = relationship("Item", secondary=ItemAssociationTable, backref="Client")
    tracked_items = relationship("TrackingItem", backref="Client")

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
    plan = fields.Str()
    next_billing_date = fields.DateTime()
    next_billing_amount = fields.Float()
    has_paid = fields.Boolean()
    created_at = fields.DateTime()

    @post_load
    def make_object(self, data, **kwargs):
        return Client(**data)
