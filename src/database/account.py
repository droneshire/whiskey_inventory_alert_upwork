from sqlalchemy import types
from sqlalchemy.schema import Column
from sqlalchemy.sql import func

from bots.database.connect import Base


class Account(Base):
    __tablename__ = "accounts"

    id = Column(types.Integer, primary_key=True)
    imvu_id = Column(types.Integer, unique=True, nullable=False)
    email = Column(types.String(80), unique=True, nullable=False)
    password = Column(types.String(100), nullable=False)
    last_follow = Column(types.Integer, nullable=True)
    followings = Column(types.Integer, nullable=False)
    country = Column(types.String(100), nullable=True)
    adult = Column(types.Boolean(), nullable=True)
    follow_time = Column(types.DateTime(timezone=True), nullable=True)
