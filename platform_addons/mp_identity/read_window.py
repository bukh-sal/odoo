"""Finite native read serialization snapshots, never cross-operation authority.

Supported entries/writes and standalone field reads still use the full guard.
Only a validated finite recordset can reuse this private short-lived snapshot.
"""
import re
import threading
import time

from odoo.exceptions import AccessError
from .scopes import scope_carrier

KEY = "_mp_read_window"
MAX_AGE = 0.020
_READ = re.compile(r"\A\s*(SELECT|SHOW)\b", re.IGNORECASE)


class ReadWindow:
    def __init__(self, records):
        self.records = records.with_context(**{KEY: None})
        self.cursor = records.env.cr
        self.user = records.env.uid
        self.su = records.env.su
        self.model = records._name
        self.ids = frozenset(records._origin.ids)
        self.virtual_ids = frozenset(ident for ident in records._ids if not ident)
        self.thread = threading.get_ident()
        self.carrier = scope_carrier(records.env)
        self.active = False
        self.registered = False
        self.invalid = True
        self.deadline = 0.0
        self.scope = None
        self.policies = {}
        self.bound_env = None

    def start(self):
        current = threading.current_thread()
        if not hasattr(current, "query_hooks"):
            current.query_hooks = []
        current.query_hooks.append(self._query)
        self.registered = True
        self.active = True
        self._refresh()

    def close(self):
        self.active = False
        self.invalid = True
        self.bound_env = None
        self.policies.clear()
        if self.registered:
            threading.current_thread().query_hooks.remove(self._query)
            self.registered = False

    def _query(self, cursor, query, params, *unused):
        # Native profiler hook, before execution. Unknown/multiple statements
        # fail closed. This does not sandbox trusted SQL/functions/native code.
        if cursor is self.cursor and (not isinstance(query, str)
                or ";" in query or not _READ.match(query)):
            self.invalid = True
            self.policies.clear()

    def _refresh(self):
        self.invalid = True
        self.policies.clear()
        # Original environment has no read token: all subclass guards run.
        self.scope = self.records._mp_guard("read")
        self.deadline = time.monotonic() + MAX_AGE
        # Pending writes keep the ordinary fresh path. Never force unrelated
        # business data to flush merely to enable this optimization.
        self.invalid = bool(self.records.env._field_dirty)

    def scope_for(self, records):
        if (not self.active or threading.get_ident() != self.thread
                or records.env is not self.bound_env
                or records.env.cr is not self.cursor or records.env.uid != self.user
                or records.env.su != self.su or records._name != self.model):
            return None
        try:
            if scope_carrier(records.env) != self.carrier:
                return None
        except AccessError:
            return None
        origins = frozenset(records._origin.ids)
        if not origins <= self.ids:
            return None
        if records._ids and not origins and not frozenset(records._ids) <= self.virtual_ids:
            return None
        if records.env._field_dirty:
            self.invalid = True
            self.policies.clear()
            return None
        if self.invalid or time.monotonic() >= self.deadline:
            self._refresh()
        return None if self.invalid else self.scope


def active_window(records):
    window = records.env.context.get(KEY)
    return window if isinstance(window, ReadWindow) and window.scope_for(records) else None
