from marshmallow import Schema, fields, post_load
from sqlalchemy import ForeignKey, types
from sqlalchemy.schema import Column
from sqlalchemy.sql import func

from database.connect import Base


class Item(Base):
    __tablename__ = "Item"

    id = Column(types.Integer, primary_key=True)
    client_id = Column(types.String, ForeignKey("Client.id"))
    nc_code = Column(types.String(80), unique=True, nullable=False)
    brand_name = Column(types.String(80), nullable=True)
    total_available = Column(types.Integer, nullable=True)
    size = Column(types.String(100), nullable=True)
    cases_per_pallet = Column(types.Integer, nullable=True)
    supplier = Column(types.String(100), nullable=True)
    supplier_allotment = Column(types.Integer, nullable=True)
    broker_name = Column(types.String(100), nullable=True)
    is_tracking = Column(types.Boolean, default=True)
    created_at = Column(types.DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Item {self.nc_code}:{self.brand_name}, {self.total_available}>"


class ItemSchema(Schema):  # type: ignore
    id = fields.Int()
    client_id = fields.Str()
    nc_code = fields.Str()
    brand_name = fields.Str()
    total_available = fields.Int()
    size = fields.Str()
    cases_per_pallet = fields.Int()
    supplier = fields.Str()
    supplier_allotment = fields.Int()
    broker_name = fields.Str()
    is_tracking = fields.Boolean()
    created_at = fields.DateTime()

    @post_load
    def make_object(self, data, **kwargs):
        return Item(**data)
