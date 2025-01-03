import contextlib
import os
import typing as T

from sqlalchemy import create_engine
from sqlalchemy.engine.base import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.orm.scoping import ScopedSession
from sqlalchemy_utils import database_exists

from util.file_util import make_sure_path_exists

ENGINE: T.Dict[str, Engine] = {}
THREAD_SAFE_SESSION_FACTORY: T.Dict[str, ScopedSession] = {}

Base = declarative_base(name="Base")


def get_table_name(base_name: str, verbose: bool = False) -> str:
    if verbose:
        print(f"base_name: {base_name}")
    return base_name


def init_engine(uri: str, db: str, **kwargs: T.Any) -> Engine:
    global ENGINE  # pylint: disable=global-variable-not-assigned
    if db not in ENGINE:
        ENGINE[db] = create_engine(uri, **kwargs)
    return ENGINE[db]


def clear_db() -> None:
    global ENGINE  # pylint: disable=global-statement
    global THREAD_SAFE_SESSION_FACTORY  # pylint: disable=global-statement
    ENGINE = {}
    THREAD_SAFE_SESSION_FACTORY = {}


def close_engine(db: str) -> None:
    global ENGINE  # pylint: disable=global-statement, global-variable-not-assigned
    global THREAD_SAFE_SESSION_FACTORY  # pylint: disable=global-statement, global-variable-not-assigned
    if db in ENGINE:
        ENGINE[db].dispose()
        del ENGINE[db]
    if db in THREAD_SAFE_SESSION_FACTORY:
        del THREAD_SAFE_SESSION_FACTORY[db]


def _init_session_factory(db: str) -> ScopedSession:
    """Initialize the THREAD_SAFE_SESSION_FACTORY."""
    global ENGINE, THREAD_SAFE_SESSION_FACTORY  # pylint: disable=global-variable-not-assigned
    if db not in ENGINE:
        raise ValueError(
            "Initialize ENGINE by calling init_engine before calling _init_session_factory!"
        )
    if db not in THREAD_SAFE_SESSION_FACTORY:
        session_factory = sessionmaker(bind=ENGINE[db])
        THREAD_SAFE_SESSION_FACTORY[db] = scoped_session(session_factory)
    return THREAD_SAFE_SESSION_FACTORY[db]


def is_session_factory_initialized() -> bool:
    return bool(THREAD_SAFE_SESSION_FACTORY)


@contextlib.contextmanager
def ManagedSession(  # pylint: disable=invalid-name
    db: T.Optional[str] = None,
) -> T.Iterator[ScopedSession]:
    """Get a session object whose lifecycle, commits and flush are managed for you.
    Expected to be used as follows:
    ```
    # multiple db_operations are done within one session.
    with ManagedSession() as session:
        # db_operations is expected not to worry about session handling.
        db_operations.select(session, **kwargs)
        # after the with statement, the session commits to the database.
        db_operations.insert(session, **kwargs)
    ```
    """
    global THREAD_SAFE_SESSION_FACTORY  # pylint: disable=global-variable-not-assigned
    if db is None:
        # assume we're just using the default db
        db = list(THREAD_SAFE_SESSION_FACTORY.keys())[0]

    if db not in THREAD_SAFE_SESSION_FACTORY:
        raise ValueError(f"Call _init_session_factory for {db} before using ManagedSession!")

    session = THREAD_SAFE_SESSION_FACTORY[db]()

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
        # https://stackoverflow.com/questions/
        # 21078696/why-is-my-scoped-session-raising-an-attributeerror-session-object-has-no-attr
        THREAD_SAFE_SESSION_FACTORY[db].remove()


def is_database_initialized(db: str) -> bool:
    """Check if the database is initialized."""
    global THREAD_SAFE_SESSION_FACTORY  # pylint: disable=global-variable-not-assigned
    return db in THREAD_SAFE_SESSION_FACTORY


def remove_database(log_dir: str, db_name: str) -> None:
    db_file = os.path.join(log_dir, "database", db_name)
    if os.path.isfile(db_file):
        print(f"Deleting existing database!")
        os.remove(db_file)


def init_database(log_dir: str, db_name: str, force: bool = False) -> None:
    db_file = os.path.join(log_dir, "database", db_name)
    db_uri = "sqlite:///" + db_file

    print(f"Initializing database {db_name} at {db_uri}")

    make_sure_path_exists(os.path.dirname(db_file))

    engine = init_engine(db_uri, db_name)

    if database_exists(engine.url):
        print("Found existing database")

        if force:
            print("Forcing database initialization")
            Base.metadata.drop_all(bind=engine)
    else:
        print("Creating new database!")

    try:
        Base.metadata.create_all(bind=engine)

        _init_session_factory(db_name)
    except KeyboardInterrupt as exc:
        raise KeyboardInterrupt from exc
    except OperationalError as exc:
        print(f"Failed to initialize database: {exc}")
        print("Continuing without db connection...")
