from dataclasses import dataclass

from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db
from .storage_service import StorageConfigurationError, get_storage_backend


@dataclass(frozen=True)
class RuntimeHealth:
    database: bool
    queue: bool
    storage: bool

    @property
    def ready(self):
        return self.database and self.queue and self.storage

    def as_dict(self):
        return {
            "database": "ok" if self.database else "error",
            "queue": "ok" if self.queue else "error",
            "storage": "ok" if self.storage else "error",
        }


def check_runtime_dependencies(app_config):
    return RuntimeHealth(
        database=_check_database(),
        queue=_check_queue(app_config),
        storage=_check_storage_configuration(app_config),
    )


def _check_database():
    try:
        db.session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        db.session.rollback()
        return False
    return True


def _check_queue(app_config):
    client = None
    try:
        client = Redis.from_url(
            app_config["REDIS_URL"],
            socket_connect_timeout=3,
            socket_timeout=3,
        )
        return bool(client.ping())
    except (RedisError, OSError, ValueError):
        return False
    finally:
        if client is not None:
            client.close()


def _check_storage_configuration(app_config):
    try:
        get_storage_backend(app_config)
    except (StorageConfigurationError, ValueError):
        return False
    return True
