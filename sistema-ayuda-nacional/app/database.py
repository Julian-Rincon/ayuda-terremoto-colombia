import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sistema_ayuda_nacional.db")

# Algunos proveedores (Render incluido, heredado de la convención de Heroku)
# todavía entregan el connection string con el esquema viejo "postgres://".
# SQLAlchemy 1.4+ ya no lo acepta — lo normalizamos acá para que
# DATABASE_URL funcione tal cual venga, sin que quien despliega tenga que
# editarlo a mano.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# SQLite necesita este flag porque por defecto solo permite usar la conexión
# desde el hilo que la creó; con Postgres (server real, sin ese límite) no
# aplica.
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
