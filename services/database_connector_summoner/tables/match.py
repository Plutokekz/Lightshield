"""Tables related to Match Data."""
from sqlalchemy import Column, Integer, String, Enum, BigInteger
from . import Base
from .enums import Server


class Match(Base):  # pylint: disable=R0903
    """Match-V4: Match-Details Table."""
    __tablename__ = 'match'

    matchId = Column(BigInteger, primary_key=True)
    queue = Column(Integer)
    gameDuration = Column(Integer)
    server = Column(Enum(Server), primary_key=True)
    gameCreation = Column(BigInteger)
    seasonId = Column(Integer)
    gameVersion = Column(String(20))
    mapId = Column(Integer)
    gameMode = Column(String(15))
