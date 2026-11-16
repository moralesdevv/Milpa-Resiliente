"""Límite de tasa en proceso por clave (IP o usuario), ventana deslizante.

Sin dependencias nuevas (Redis descartado, README §7). Limitación conocida y documentada: el
estado vive en el proceso; con varias réplicas el límite efectivo se multiplica (ADR-013).
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from api.errors import RateLimited


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_s: float = 60.0, max_keys: int = 50_000) -> None:
        self.limit = limit
        self.window_s = window_s
        self.max_keys = max_keys
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, *, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        with self._lock:
            if len(self._hits) > self.max_keys:  # tope de memoria ante barridos de claves
                self._evict(now)
            q = self._hits[key]
            while q and now - q[0] >= self.window_s:
                q.popleft()
            if len(q) >= self.limit:
                retry = max(1, int(self.window_s - (now - q[0])) + 1)
                raise RateLimited(
                    "Se superó el límite de solicitudes", headers={"Retry-After": str(retry)}
                )
            q.append(now)

    def _evict(self, now: float) -> None:
        for k in [k for k, q in self._hits.items() if not q or now - q[-1] >= self.window_s]:
            del self._hits[k]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
