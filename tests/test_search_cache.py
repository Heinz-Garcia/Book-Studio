"""Tests fuer Phase 6 / SearchCache.

Deckt:
- Initialisierung, max_size Validierung
- put/get mit LRU-Eviction
- dict-Kompat (__getitem__, __setitem__, __contains__, __len__)
- invalidate (einzeln) und clear (alle)
- Hit/Miss-Statistiken
- Thread-Safety (rudimentaer)
"""

from __future__ import annotations

import threading

import pytest

from services.search_cache import DEFAULT_MAX_SIZE, SearchCache


# --- Initialisierung --------------------------------------------------------


def test_default_max_size_constant():
    assert DEFAULT_MAX_SIZE > 0


def test_init_with_default_size():
    c = SearchCache()
    assert c.max_size == DEFAULT_MAX_SIZE
    assert len(c) == 0


def test_init_with_custom_size():
    c = SearchCache(max_size=5)
    assert c.max_size == 5


def test_init_rejects_zero():
    with pytest.raises(ValueError):
        SearchCache(max_size=0)


def test_init_rejects_negative():
    with pytest.raises(ValueError):
        SearchCache(max_size=-1)


# --- put / get -------------------------------------------------------------


def test_put_and_get():
    c = SearchCache(max_size=3)
    c.put("a", "1")
    assert c.get("a") == "1"
    assert c.get("missing") is None
    assert c.get("missing", default="d") == "d"


def test_get_returns_default():
    c = SearchCache()
    assert c.get("x") is None
    assert c.get("x", default="fallback") == "fallback"


def test_put_updates_existing_key():
    c = SearchCache(max_size=3)
    c.put("a", "1")
    c.put("a", "2")
    assert c.get("a") == "2"
    assert len(c) == 1


def test_lru_eviction():
    c = SearchCache(max_size=3)
    c.put("a", "1")
    c.put("b", "2")
    c.put("c", "3")
    c.put("d", "4")  # aelterer Eintrag wird evicted
    assert "a" not in c
    assert c.get("b") == "2"
    assert c.get("c") == "3"
    assert c.get("d") == "4"
    assert len(c) == 3


def test_lru_get_promotes_to_most_recent():
    """Ein get macht den Eintrag zum MRU; er wird nicht evicted."""
    c = SearchCache(max_size=3)
    c.put("a", "1")
    c.put("b", "2")
    c.put("c", "3")
    # 'a' ist jetzt LRU, aber get() macht es zum MRU.
    assert c.get("a") == "1"
    c.put("d", "4")  # 'b' ist jetzt LRU und wird evicted.
    assert "a" in c
    assert "b" not in c
    assert "c" in c
    assert "d" in c


# --- dict-Kompat ------------------------------------------------------------


def test_getitem_and_setitem():
    c = SearchCache(max_size=3)
    c["k"] = "v"
    assert c["k"] == "v"


def test_getitem_raises_keyerror_for_missing():
    c = SearchCache()
    with pytest.raises(KeyError):
        _ = c["missing"]


def test_contains():
    c = SearchCache(max_size=3)
    c.put("a", "1")
    assert "a" in c
    assert "b" not in c


def test_len_reflects_size():
    c = SearchCache(max_size=3)
    assert len(c) == 0
    c.put("a", "1")
    assert len(c) == 1
    c.put("b", "2")
    assert len(c) == 2
    c.put("a", "11")  # update, kein neuer Eintrag
    assert len(c) == 2


# --- invalidate / clear ----------------------------------------------------


def test_invalidate_existing_key():
    c = SearchCache()
    c.put("a", "1")
    assert c.invalidate("a") is True
    assert "a" not in c


def test_invalidate_missing_key_returns_false():
    c = SearchCache()
    assert c.invalidate("nope") is False


def test_invalidate_returns_true_when_cached_value_is_none():
    """B-Fix (Code-Review 2026-07-03): ein gecachter `None`-Wert ist ein
    legitimer Treffer - `invalidate` durfte hierfuer nicht `False`
    zurueckgeben, nur weil der WERT `None` war."""
    c = SearchCache()
    c.put("a", None)
    assert "a" in c
    assert c.invalidate("a") is True
    assert "a" not in c


def test_contains_promotes_lru_like_get():
    """B-Fix (Code-Review 2026-07-03): `in`-Checks muessen die
    LRU-Reihenfolge genau wie `get()` aktualisieren, sonst wird ein
    aktiv abgefragter Eintrag trotzdem als LRU verdraengt."""
    c = SearchCache(max_size=3)
    c.put("a", "1")
    c.put("b", "2")
    c.put("c", "3")
    # 'a' ist jetzt LRU, aber ein `in`-Check macht es zum MRU.
    assert "a" in c
    c.put("d", "4")  # 'b' ist jetzt LRU und wird evicted.
    assert "a" in c
    assert "b" not in c
    assert "c" in c
    assert "d" in c


def test_clear_resets_state():
    c = SearchCache(max_size=2)
    c.put("a", "1")
    c.put("b", "2")
    c.get("a")  # hit
    c.get("missing")  # miss
    c.clear()
    assert len(c) == 0
    stats = c.stats()
    assert stats["hits"] == 0
    assert stats["misses"] == 0


# --- Diagnostik / Stats ----------------------------------------------------


def test_stats_track_hits_and_misses():
    c = SearchCache()
    c.put("a", "1")
    c.get("a")  # hit
    c.get("a")  # hit
    c.get("b")  # miss
    stats = c.stats()
    assert stats["hits"] == 2
    assert stats["misses"] == 1
    assert stats["size"] == 1
    assert stats["max_size"] == DEFAULT_MAX_SIZE


# --- Thread-Safety (rudimentaer) -------------------------------------------


def test_concurrent_puts_dont_exceed_max_size():
    """10 Threads x 100 puts in einen Cache der Groesse 50 -> max 50."""
    c = SearchCache(max_size=50)
    errors = []

    def worker(start):
        try:
            for i in range(start, start + 100):
                c.put(f"k{i}", i)
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i * 100,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert len(c) <= 50
