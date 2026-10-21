"""A bounded, process-safe prediction budget for one API instance."""

import math
import sqlite3
import time
from contextlib import closing

LIMITS = ((60, 30), (3600, 300))


def retry_after(path):
    now = time.time()
    # Open per request: Gunicorn forks and recycles its workers after each upload.
    with closing(sqlite3.connect(path, timeout=1)) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS budgets "
            "(period INTEGER PRIMARY KEY, expires INTEGER, used INTEGER)"
        )
        waits = []
        for period, limit in LIMITS:
            expires = (int(now) // period + 1) * period
            connection.execute(
                "INSERT INTO budgets VALUES (?, ?, 0) "
                "ON CONFLICT(period) DO UPDATE SET expires=excluded.expires, used=0 "
                "WHERE budgets.expires <= ?",
                (period, expires, now),
            )
            used = connection.execute(
                "SELECT used FROM budgets WHERE period=?", (period,)
            ).fetchone()[0]
            if used >= limit:
                waits.append(math.ceil(expires - now))
        if waits:
            return max(waits)
        connection.execute("UPDATE budgets SET used=used+1")
    return 0
