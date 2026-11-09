"""Persistent, adaptive ranking of download servers, per source.

The scraper layer exposes a hardcoded `SERVER_PRIORITY` per source as a static
tiebreaker. That order is systematically wrong: on latanime it ranks servers
that only return HTML landing pages ABOVE the two that actually serve video.
This module learns which ``(fuente, servidor)`` pairs really deliver and uses
that learned success rate to reorder the candidates.

Design constraints:

- All DB access lives HERE, never in ``scrapers/``; the scrapers stay pure and
  testable and know nothing about the stats table.
- The ranking is deterministic: no LLM, no external service, no randomness. The
  same inputs always produce the same order.
- Both helpers degrade gracefully. If the stats table is empty or unavailable,
  ``rank()`` returns the candidates unchanged, so behaviour falls back to
  today's static ``SERVER_PRIORITY`` order.
"""

import logging
import time

from django.db import OperationalError, close_old_connections
from django.db.models import F
from django.utils import timezone

logger = logging.getLogger(__name__)

# Laplace-style prior for an unseen pair. `(0 + 1) / (0 + 0 + 2) == 0.5`, so a
# pair with no history sits exactly in the middle and can neither outrank a
# proven-good server (> 0.5) nor be buried below a proven-bad one (< 0.5).
# The +2 denominator also makes division by zero impossible.
DEFAULT_SCORE = 0.5

# SQLite serializes writers, and this app runs up to 50 download workers in one
# process on SQLite. A concurrent write can therefore return "database is
# locked" without waiting. `record()` must not raise into the download path, so
# instead of dropping the sample it retries a few times with a tiny backoff.
_LOCK_RETRIES = 4
_LOCK_BACKOFF_SECONDS = 0.05


def _score(exitos: int, fallos: int) -> float:
    """Smoothed success rate — never 0/0, never an over-confident 1.0 or 0.0."""
    return (exitos + 1) / (exitos + fallos + 2)


def rank(fuente: str, candidatos: list[dict]) -> list[dict]:
    """Reorder `candidatos` (scraper dicts) by learned reliability.

    Order is, in priority:

    1. resolved first — a candidate with `resolved: True` is a verified direct
       media link and must never lose to an unresolved landing/embed,
    2. within each group, higher learned score first,
    3. ties broken by the candidate's existing order (the source's static
       `SERVER_PRIORITY`).

    A missing `resolved` key defaults to False (unverified), matching the
    producers. Returns the input list unchanged if there is no stats data or the
    stats table is unavailable.

    The source's stats are fetched in ONE query into a dict, so the number of
    queries does not grow with the number of candidates (no N+1).
    """
    if not candidatos:
        return candidatos

    try:
        # Background worker threads hold long-lived, thread-local connections:
        # reap the stale ones before touching the DB (Django's canonical pattern
        # for DB access outside a request cycle).
        close_old_connections()
        from .models import ServerStat
        scores = {
            row['servidor']: _score(row['exitos'], row['fallos'])
            for row in ServerStat.objects.filter(fuente=fuente).values(
                'servidor', 'exitos', 'fallos',
            )
        }
    except Exception as e:  # table missing, DB down, ... -> keep static order
        logger.warning(f"server_stats.rank: sin estadisticas para {fuente!r}: {e}")
        return candidatos

    if not scores:
        return candidatos

    # Stable sort over (resolved, -score, original_index): the index is the
    # explicit tiebreaker so the scraper's existing order is preserved exactly
    # for equal scores.
    indexed = list(enumerate(candidatos))
    indexed.sort(key=lambda pair: (
        not pair[1].get('resolved', False),
        -scores.get(pair[1].get('server', ''), DEFAULT_SCORE),
        pair[0],
    ))
    return [candidato for _, candidato in indexed]


def record(fuente: str, servidor: str, ok: bool) -> None:
    """Record one real attempt outcome for a ``(fuente, servidor)`` pair.

    Must NEVER raise into the download path: any DB error is logged and
    swallowed, because a stats failure can never be allowed to break a download
    that would otherwise succeed.
    """
    if not fuente or not servidor:
        return

    campo = 'exitos' if ok else 'fallos'
    for intento in range(_LOCK_RETRIES + 1):
        try:
            close_old_connections()
            from .models import ServerStat
            # Ensure the row exists. `get_or_create` only opens a transaction on
            # the create path; on the hot path (row already exists) it is a bare
            # SELECT. `update_or_create` would instead hold a read lock across a
            # SELECT+UPDATE inside `atomic()`, and upgrading that read lock to a
            # write returns SQLite's "database is locked" IMMEDIATELY (the lock
            # upgrade bypasses the busy timeout). The create race is still safe:
            # the unique constraint makes one of two concurrent creates fail and
            # `get_or_create` retries the lookup.
            ServerStat.objects.get_or_create(fuente=fuente, servidor=servidor)
            # The read-modify-write happens inside a single UPDATE via F(), so
            # two concurrent workers incrementing the same pair cannot lose an
            # update (unlike loading the row and saving a stale value back).
            # This is a direct write, so the busy handler serializes it properly.
            ServerStat.objects.filter(fuente=fuente, servidor=servidor).update(
                **{campo: F(campo) + 1},
                ultima_vez=timezone.now(),
            )
            return
        except OperationalError as e:
            # SQLite serializes writers: a concurrent writer can bump into a
            # lock. Retry with a short backoff instead of dropping the sample;
            # this stays well below the download path's tolerance.
            if 'locked' in str(e).lower() and intento < _LOCK_RETRIES:
                time.sleep(_LOCK_BACKOFF_SECONDS * (intento + 1))
                continue
            logger.warning(
                f"server_stats.record fallo para {fuente!r}/{servidor!r} ({ok=}): {e}"
            )
            return
        except Exception as e:
            logger.warning(
                f"server_stats.record fallo para {fuente!r}/{servidor!r} ({ok=}): {e}"
            )
            return
