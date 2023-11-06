from marshmallow import Schema, fields, post_load
from sqlalchemy import ForeignKey, UniqueConstraint, types
from sqlalchemy.orm import relationship
from sqlalchemy.schema import Column
from sqlalchemy.sql import func

from database.connect import Base
from database.models.item_association import ItemAssociationTable


class PhoneNumber(Base):
    __tablename__ = "PhoneNumber"

    id = Column(types.Integer, primary_key=True)
    client_id = Column(types.String(80), ForeignKey("Client.id"))
    client = relationship("Client", back_populates="phone_numbers")
    number = Column(types.String(11), nullable=False)

    __table_args__ = (UniqueConstraint("client_id", "number", name="_client_phone_uc"),)


class PhoneNumberSchema(Schema):  # type: ignore
    id = fields.Int()
    number = fields.Str()

    @post_load
    def make_object(self, data, **kwargs):
        return PhoneNumber(**data)


class TrackingItem(Base):
    __tablename__ = "TrackingItem"

    id = Column(types.Integer, primary_key=True)
    client_id = Column(types.String(80), ForeignKey("Client.id"))
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
    update_on_new_data = Column(types.Boolean, default=True)
    enable_new_data_sms_alert = Column(types.Boolean, default=True)
    enable_new_data_email_alert = Column(types.Boolean, default=True)
    alert_time_range_start = Column(types.Integer, nullable=True)
    alert_time_range_end = Column(types.Integer, nullable=True)
    alert_time_zone = Column(types.String(80), nullable=True)
    alert_range_enabled = Column(types.Boolean, default=False)
    phone_numbers = relationship("PhoneNumber", back_populates="client")
    phone_alerts = Column(types.Boolean, default=True)
    threshold_inventory = Column(types.Integer, nullable=True, default=1)
    last_updated = Column(types.DateTime(timezone=True), nullable=True)
    updates_sent = Column(types.Integer, nullable=True, default=0)
    plan = Column(types.String(80), nullable=True)
    next_billing_date = Column(types.DateTime(timezone=True), nullable=True)
    next_billing_amount = Column(types.Float, default=0.0)
    has_paid = Column(types.Boolean, default=False)
    min_hours_since_out_of_stock = Column(types.Integer, default=0)
    created_at = Column(types.DateTime(timezone=True), server_default=func.now())
    items = relationship("Item", secondary=ItemAssociationTable, backref="Client")
    tracked_items = relationship("TrackingItem", backref="Client")

    def __repr__(self):
        return f"<Client {self.name}:{self.phone_numbers}, {self.email}>"


class ClientSchema(Schema):  # type: ignore
    id = fields.Str()
    email = fields.Str()
    email_alerts = fields.Boolean()
    update_on_new_data = fields.Boolean()
    enable_new_data_sms_alert = fields.Boolean()
    enable_new_data_email_alert = fields.Boolean()
    alert_time_range_start = fields.Int()
    alert_time_range_end = fields.Int()
    alert_time_zone = fields.Str()
    alert_range_enabled = fields.Boolean()
    phone_numbers = fields.List(fields.Nested("PhoneNumberSchema"))
    phone_alerts = fields.Boolean()
    threshold_inventory = fields.Int()
    last_updated = fields.DateTime()
    updates_sent = fields.Int()
    plan = fields.Str()
    next_billing_date = fields.DateTime()
    next_billing_amount = fields.Float()
    has_paid = fields.Boolean()
    min_hours_since_out_of_stock = fields.Int()
    created_at = fields.DateTime()
    items = fields.List(fields.Nested("ItemSchema"))
    tracked_items = fields.List(fields.Nested("TrackingItemSchema"))

    @post_load
    def make_object(self, data, **kwargs):
        return Client(**data)
