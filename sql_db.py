import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import Config
from models import Base

# Use the DB URL from your config (SQLite locally, Cloud SQL in production)
DB_URL = Config.SQLALCHEMY_DATABASE_URI

engine = create_engine(DB_URL, echo=False, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

# Create tables if they don't exist
Base.metadata.create_all(engine)
