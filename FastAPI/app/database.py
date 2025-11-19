from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

# Create engine with connection pooling configuration
engine = create_engine(
    settings.DATABASE_URL,
    # Connection pool settings
    pool_size=20,           # Max permanent connections (default: 5)
    max_overflow=10,        # Max temporary connections beyond pool_size (default: 10)
    pool_recycle=3600,      # Recycle connections after 1 hour (prevents stale connections)
    pool_pre_ping=True,     # Test connections before using (catches broken connections)
    # Connection args for PostgreSQL
    connect_args={
        "connect_timeout": 10,  # Connection timeout in seconds
    },
    # Enable connection pool logging for debugging (set to False in production)
    echo_pool=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()