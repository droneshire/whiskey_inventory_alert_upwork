from sqlalchemy import ForeignKey, types
from sqlalchemy.schema import Column, Table

from database.connect import Base


ItemAssociationTable = Table(
    "association",
    Base.metadata,
    Column("client_id", types.String, ForeignKey("Client.id")),
    Column("item_id", types.String, ForeignKey("Item.id")),
)
