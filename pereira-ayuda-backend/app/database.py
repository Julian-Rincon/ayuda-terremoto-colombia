import os

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Por defecto usa SQLite (cero configuración, ideal para levantar HOY).
# Para producción real, define DATABASE_URL=postgresql://... en el entorno.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./pereira_ayuda.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
