from marshmallow import Schema, fields, post_load
from sqlalchemy import types, ForeignKey
from sqlalchemy.schema import Column
from sqlalchemy.sql import func

from database.connect import Base


class Item(Base):
    __tablename__ = "Item"

    id = Column(types.Integer, primary_key=True)
    client_id = Column(types.String, ForeignKey("Client.id"))
    nc_code = Column(types.String(80), unique=True, nullable=False)
    brand_name = Column(types.String(80), unique=True, nullable=False)
    total_available = Column(types.Integer, nullable=False)
    size = Column(types.String(100), nullable=False)
    cases_per_pallet = Column(types.Integer, nullable=False)
    supplier = Column(types.String(100), nullable=True)
    supplier_allotment = Column(types.Integer, nullable=False)
    broker_name = Column(types.String(100), nullable=True)
    create_time = Column(types.DateTime(timezone=True), nullable=True)

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
    create_time = fields.DateTime()

    @post_load
    def make_object(self, data, **kwargs):
        return Item(**data)
