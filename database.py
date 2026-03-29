from sqlalchemy import create_engine
from sqlalchemy.orm  import DeclarativeBase, sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./database.db"


engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)


session_local = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine
)


class Base(DeclarativeBase):
    pass


def get_db():
    with session_local() as db:
        yield db