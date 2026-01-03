import logging
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import declarative_base, relationship
import enum

logger = logging.getLogger(__name__)

Base = declarative_base()


class Sphere(enum.Enum):
    CENTER = "center"
    SOUL = "soul"
    BODY = "body"
    BUSINESS = "business"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    
    # Onboarding state
    is_onboarding = Column(Boolean, default=True)
    onboarding_step = Column(Integer, default=0)
    onboarding_answers = Column(Text, default="")  # JSON string of answers
    
    # Psychotype result
    psychotype = Column(Text, nullable=True)
    
    # Recommended curators (from AI analysis)
    recommended_business = Column(String(50), nullable=True)
    recommended_soul = Column(String(50), nullable=True)
    recommended_body = Column(String(50), nullable=True)
    recommended_center = Column(String(50), nullable=True)
    
    # Selected curators
    selected_business = Column(String(50), nullable=True)
    selected_soul = Column(String(50), nullable=True)
    selected_body = Column(String(50), nullable=True)
    selected_center = Column(String(50), nullable=True)
    
    # Thread IDs for sphere detection
    chat_id = Column(Integer, nullable=True)
    thread_soul = Column(Integer, nullable=True)
    thread_body = Column(Integer, nullable=True)
    thread_business = Column(Integer, nullable=True)
    thread_center = Column(Integer, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    messages = relationship("Message", back_populates="user", cascade="all, delete-orphan")
    summarizations = relationship("Summarization", back_populates="user", cascade="all, delete-orphan")

    def has_all_curators_selected(self) -> bool:
        """Check if user has selected all required curators."""
        return all([
            self.selected_business,
            self.selected_soul,
            self.selected_body,
            self.selected_center
        ])

    def get_curator_for_sphere(self, sphere: str) -> str:
        """Get selected curator for a given sphere."""
        mapping = {
            "business": self.selected_business,
            "soul": self.selected_soul,
            "body": self.selected_body,
            "center": self.selected_center
        }
        return mapping.get(sphere)

    def __repr__(self):
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, username={self.username})>"


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    sphere = Column(String(20), nullable=False)  # center, soul, body, business
    role = Column(String(20), nullable=False)  # user or assistant
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    user = relationship("User", back_populates="messages")

    def __repr__(self):
        return f"<Message(id={self.id}, sphere={self.sphere}, role={self.role})>"


class Summarization(Base):
    __tablename__ = "summarizations"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    sphere = Column(String(20), nullable=False)  # soul, body, business
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    user = relationship("User", back_populates="summarizations")

    def __repr__(self):
        return f"<Summarization(id={self.id}, sphere={self.sphere})>"


