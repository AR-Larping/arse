from typing import Optional, List
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String
from pydantic import BaseModel, ConfigDict

Base = declarative_base()

class Player(Base):
    __tablename__ = "player"
    
    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String, nullable=True)
    
    # Relationships could be added here
    # games: List["Game"] = Relationship(back_populates="player")

# Add more models as needed, for example:
# class Game(SQLModel, table=True):
#     id: Optional[int] = Field(default=None, primary_key=True)
#     name: str
#     player_id: Optional[int] = Field(default=None, foreign_key="player.id")
#     player: Optional[Player] = Relationship(back_populates="games")

class PlayerRead(BaseModel):
    id: int
    name: str
    email: str | None = None
    
    model_config = ConfigDict(from_attributes=True) 