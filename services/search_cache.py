"""SearchCache - LRU-Cache fuer Volltext-Suchergebnisse.

Phase 6: B6 hatte festgestellt, dass der `_content_search_cache` in
`BookStudio` unbeschraenkt waechst. Heute lebt das Cache-Management
in `invalidate_content_search_cache` (clear-on-mutation) und
impliziten `dict[key] = value`-Writes. Diese Implementierung:

- Setzt eine konfigurierbare Maximal-Groesse (LRU, default 256).
- Stellt `get`, `put`, `invalidate`, `clear` als Methoden bereit.
- Laesst den Studio-Code in-place kompatibel (dict-artige
  `__getitem__`/`__setitem__`-Operatoren fuer lesende Pfade).
- Trackt Hit/Miss-Statistiken (fuer spaetere Diagnostik).

Diese Klasse ist **kein Service** im strengen Sinne, sondern ein
Daten-Container mit Methoden. Sie wird ueber das Studio
instanziiert, nicht im Service-Container gehalten.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Any


# Default-Groesse: 256 Eintraege. B6-Doku nennt keinen konkreten
# Wert; 256 deckt 256 MD-Dateien Volltext-Pfad ab.
DEFAULT_MAX_SIZE = 256


class SearchCache:
    """LRU-Cache fuer Pfad -> Inhalt-Lookups (Volltext-Suche).

    Attributes:
        max_size: Maximale Anzahl Eintraege. Bei Ueberschreitung wird
            der aelteste Eintrag (LRU) entfernt.
    """

    def __init__(self, max_size: int = DEFAULT_MAX_SIZE):
        if max_size <= 0:
            raise ValueError("max_size muss > 0 sein")
        self._max_size = max_size
        self._data: "OrderedDict[str, str]" = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    # --- Public API -----------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
                self._hits += 1
                return self._data[key]
            self._misses += 1
            return default

    def put(self, key: str, value: Any) -> None:
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
                self._data[key] = value
                return
            self._data[key] = value
            while len(self._data) > self._max_size:
                self._data.popitem(last=False)

    def invalidate(self, key: str) -> bool:
        """Loescht einen einzelnen Eintrag. Returns True wenn vorhanden.

        B-Fix (Code-Review 2026-07-03): `self._data.pop(key, None) is not
        None` lieferte faelschlich `False`, wenn der gecachte Wert selbst
        `None` war (ein legitimer Cache-Treffer) - der Eintrag wurde zwar
        entfernt, aber als "nicht vorhanden gewesen" gemeldet.
        """
        with self._lock:
            if key not in self._data:
                return False
            del self._data[key]
            return True

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._hits = 0
            self._misses = 0

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)

    def __contains__(self, key: str) -> bool:
        # B-Fix (Code-Review 2026-07-03): `in`-Checks aktualisierten die
        # LRU-Reihenfolge zuvor nicht, obwohl sie einen echten Zugriff
        # darstellen. Ein Eintrag, der nur ueber `in` abgefragt wurde,
        # konnte dadurch trotz aktiver Nutzung als "least recently used"
        # verdraengt werden.
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
                return True
            return False

    # --- dict-Kompat (fuer Studio-Migration) -----------------------------

    def __getitem__(self, key: str) -> Any:
        value = self.get(key, default=_SENTINEL)
        if value is _SENTINEL:
            raise KeyError(key)
        return value

    def __setitem__(self, key: str, value: Any) -> None:
        self.put(key, value)

    # --- Diagnostik -----------------------------------------------------

    @property
    def max_size(self) -> int:
        return self._max_size

    def stats(self) -> dict:
        with self._lock:
            return {
                "size": len(self._data),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
            }


_SENTINEL = object()


__all__ = ["DEFAULT_MAX_SIZE", "SearchCache"]
