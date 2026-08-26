import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base

# Por defecto los tests corren contra SQLite en memoria (rápido, sin
# dependencias). Si se exporta DATABASE_URL apuntando a un Postgres real
# (ej. `DATABASE_URL=postgresql://postgres:test@localhost:5433/ayuda_test`),
# los tests corren contra ese motor en su lugar — así se puede validar la
# migración SQLite -> Postgres con la suite completa, sin mockear nada.
TEST_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///:memory:")


def build_test_engine():
    """Crea un engine de pruebas aislado (nunca reutiliza el `engine` de
    app.database) para el motor indicado por TEST_DATABASE_URL."""
    if TEST_DATABASE_URL.startswith("sqlite"):
        # StaticPool: una sola conexión compartida para que la base en
        # memoria sobreviva entre sesiones dentro del mismo test (si no,
        # cada checkout del pool abriría una base en memoria distinta).
        return create_engine(
            TEST_DATABASE_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    return create_engine(TEST_DATABASE_URL)


def reset_schema(engine):
    """Deja el motor de pruebas con el esquema limpio y vacío. Necesario
    incluso en Postgres real (persistente entre tests, a diferencia del
    SQLite en memoria que se descarta solo al cerrar el engine) para que un
    test nunca vea datos sembrados por el anterior."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


@pytest.fixture()
def db_session():
    engine = build_test_engine()
    reset_schema(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
