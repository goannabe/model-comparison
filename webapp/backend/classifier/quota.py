"""Hourly credit budgets for the public demo.

Two budgets, both resetting at the top of every UTC hour:
  * per client (visitor, identified by IP) - what the UI shows as "credits"
  * global (all visitors combined) - the hard ceiling on compute, so changing
    IP addresses can't run up the hosting bill

State is in process memory guarded by a lock. That is only correct while a
single server process handles all requests (gunicorn --workers 1 with
threads, Cloud Run max-instances 1); a restart clears the counters.
"""

import threading
import time

from django.conf import settings

WINDOW_SECONDS = 3600


class QuotaExceeded(Exception):
    def __init__(self, scope, cost, status):
        self.scope = scope  # "client" or "global"
        self.cost = cost
        self.status = status
        super().__init__(f"{scope} quota exceeded")


class HourlyQuota:
    def __init__(self, per_client_limit, global_limit, clock=time.time):
        self.per_client_limit = per_client_limit
        self.global_limit = global_limit
        self._clock = clock
        self._lock = threading.Lock()
        self._window_start = None
        self._client_used = {}
        self._global_used = 0

    def _current_window(self):
        now = self._clock()
        return now, int(now // WINDOW_SECONDS) * WINDOW_SECONDS

    def _roll(self):
        """Start a fresh window if the hour has changed. Caller holds the lock."""
        now, window_start = self._current_window()
        if window_start != self._window_start:
            self._window_start = window_start
            self._client_used = {}
            self._global_used = 0
        return now

    def _status(self, client_id, now):
        used = self._client_used.get(client_id, 0)
        reset_at = self._window_start + WINDOW_SECONDS
        return {
            "enabled": True,
            "limit": self.per_client_limit,
            "used": used,
            "remaining": max(0, self.per_client_limit - used),
            "global_limit": self.global_limit,
            "global_remaining": max(0, self.global_limit - self._global_used),
            "reset_at": reset_at,
            "reset_in_seconds": max(0, int(reset_at - now)),
        }

    def status(self, client_id):
        with self._lock:
            now = self._roll()
            return self._status(client_id, now)

    def charge(self, client_id, cost):
        """Atomically spend `cost` credits from both budgets, or raise
        QuotaExceeded without spending anything."""
        with self._lock:
            now = self._roll()
            used = self._client_used.get(client_id, 0)
            if used + cost > self.per_client_limit:
                raise QuotaExceeded("client", cost, self._status(client_id, now))
            if self._global_used + cost > self.global_limit:
                raise QuotaExceeded("global", cost, self._status(client_id, now))
            self._client_used[client_id] = used + cost
            self._global_used += cost
            return self._status(client_id, now)

    def refund(self, client_id, cost):
        """Give credits back, e.g. when the request failed after charging."""
        with self._lock:
            self._roll()
            if client_id in self._client_used:
                self._client_used[client_id] = max(0, self._client_used[client_id] - cost)
            self._global_used = max(0, self._global_used - cost)

    def reset(self, scope="all", client_id=None):
        """scope: "all" (every client + global), "global" (shared budget only),
        or "client" (one client's budget, `client_id` required)."""
        with self._lock:
            self._roll()
            if scope == "client":
                self._client_used.pop(client_id, None)
            elif scope == "global":
                self._global_used = 0
            else:
                self._client_used = {}
                self._global_used = 0


class _DisabledQuota:
    """Used when QUOTA_ENABLED is off (local development): never limits."""

    def status(self, client_id):
        return {"enabled": False}

    def charge(self, client_id, cost):
        return self.status(client_id)

    def refund(self, client_id, cost):
        pass

    def reset(self, scope="all", client_id=None):
        pass


_quota = None
_quota_lock = threading.Lock()


def get_quota():
    global _quota
    with _quota_lock:
        if _quota is None:
            if settings.QUOTA_ENABLED:
                _quota = HourlyQuota(settings.QUOTA_PER_CLIENT_PER_HOUR, settings.QUOTA_GLOBAL_PER_HOUR)
            else:
                _quota = _DisabledQuota()
        return _quota


def reset_quota_singleton():
    """Tests only: rebuild the quota from current settings on next use."""
    global _quota
    with _quota_lock:
        _quota = None


def client_id_for(request):
    """Visitor identity for the per-client budget.

    Behind Cloud Run's front end the real client IP is the LAST entry of
    X-Forwarded-For (anything before it can be set by the client itself, so
    trusting the first entry would let anyone dodge the limit by faking it).
    Without a proxy, fall back to the socket address.
    """
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def cost_for(action, families):
    """Total credits for running `action` once on models of these families."""
    table = settings.QUOTA_COSTS[action]
    return sum(table[family] for family in families)
