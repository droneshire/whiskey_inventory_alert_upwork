from marshmallow import fields
from sqlalchemy import ForeignKey
from sqlalchemy.schema import Column, Table

from database.connect import Base

item_client_association_table = Table(
    "item_client_association",
    Base.metadata,
    Column("item_id", fields.Integer, ForeignKey("Item.id"), primary_key=True),
    Column("client_id", fields.String(80), ForeignKey("Client.id"), primary_key=True),
)
