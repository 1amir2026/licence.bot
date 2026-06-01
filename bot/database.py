from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()

engine = create_engine('sqlite:///licenses.db', echo=False)
Session = sessionmaker(bind=engine)

class License(Base):
    __tablename__ = 'licenses'
    id = Column(Integer, primary_key=True)
    key = Column(String(20), unique=True, nullable=False)
    used = Column(Boolean, default=False)
    user_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    used_at = Column(DateTime, nullable=True)

Base.metadata.create_all(engine)
