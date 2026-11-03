"""Read the native registration setting without its worker-local config cache."""
from CTFd.cache import cache
from CTFd.constants.setup import DEFAULTS
from CTFd.models import Configs, db
from CTFd.utils import _get_config

KEY = "registration_visibility"


def visibility():
    row = db.session.execute(Configs.__table__.select().where(Configs.key == KEY).order_by(Configs.id)).first()
    return row.value if row and row.value else DEFAULTS[KEY]


def status():
    # Native MLC/private modes do not offer local public self-registration.
    return {"enabled": visibility() == "public"}


def invalidate():
    cache.delete_memoized(_get_config, KEY)
