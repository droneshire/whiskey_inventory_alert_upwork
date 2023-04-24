import contextlib
import typing as T

from sqlalchemy import create_engine
from sqlalchemy.engine.base import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.orm.scoping import ScopedSession

engine = None
thread_safe_session_factory = None

Base = declarative_base()


def init_engine(uri, **kwargs) -> Engine:
    global engine
    if engine is None:
        engine = create_engine(uri, **kwargs)
    return engine


def init_session_factory() -> ScopedSession:
    """Initialize the thread_safe_session_factory."""
    global engine, thread_safe_session_factory
    if engine is None:
        raise ValueError(
            "Initialize engine by calling init_engine before calling init_session_factory!"
        )
    if thread_safe_session_factory is None:
        thread_safe_session_factory = scoped_session(sessionmaker(bind=engine))
    return thread_safe_session_factory


@contextlib.contextmanager
def ManagedSession():
    """Get a session object whose lifecycle, commits and flush are managed for you.
    Expected to be used as follows:
    ```
    with ManagedSession() as session:            # multiple db_operations are done within one session.
        db_operations.select(session, **kwargs)  # db_operations is expected not to worry about session handling.
        db_operations.insert(session, **kwargs)  # after the with statement, the session commits to the database.
    ```
    """
    global thread_safe_session_factory
    if thread_safe_session_factory is None:
        raise ValueError("Call init_session_factory before using ManagedSession!")
    session = thread_safe_session_factory()
    try:
        yield session
        session.commit()
        session.flush()
    except Exception:
        session.rollback()
        # When an exception occurs, handle session session cleaning,
        # but raise the Exception afterwards so that user can handle it.
        raise
    finally:
        # source:
        # https://stackoverflow.com/questions/21078696/why-is-my-scoped-session-raising-an-attributeerror-session-object-has-no-attr
        thread_safe_session_factory.remove()
