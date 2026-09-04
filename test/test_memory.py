#!/usr/bin/env python3
"""
Unit tests for ThreadMemory (in-memory per-thread conversation store).

Pure logic — needs no Slack/JIRA/Gemini credentials. Runs standalone
(`python test/test_memory.py`) or under pytest.
"""

import os
import sys

# Make the repo root importable when run as a plain script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory import ThreadMemory


def test_add_and_history_preserves_order():
    mem = ThreadMemory()
    key = "C1:1.1"
    mem.add(key, "user", "hello")
    mem.add(key, "assistant", "hi there")
    mem.add(key, "user", "how are you")

    history = mem.history(key)
    assert [t["role"] for t in history] == ["user", "assistant", "user"]
    assert [t["text"] for t in history] == ["hello", "hi there", "how are you"]


def test_history_unknown_key_is_empty():
    mem = ThreadMemory()
    assert mem.history("nope") == []
    assert mem.has("nope") is False


def test_history_returns_a_copy():
    mem = ThreadMemory()
    mem.add("C1:1", "user", "a")
    h = mem.history("C1:1")
    h.append({"role": "user", "text": "mutated"})
    # Internal state must not be affected by mutating the returned list.
    assert len(mem.history("C1:1")) == 1


def test_per_thread_turn_cap_drops_oldest():
    mem = ThreadMemory(max_turns_per_thread=3)
    key = "C1:1"
    for i in range(5):
        mem.add(key, "user", f"msg{i}")

    history = mem.history(key)
    assert len(history) == 3
    # Oldest (msg0, msg1) dropped; newest kept in order.
    assert [t["text"] for t in history] == ["msg2", "msg3", "msg4"]


def test_lru_eviction_of_oldest_thread():
    mem = ThreadMemory(max_threads=2)
    mem.add("A", "user", "a")
    mem.add("B", "user", "b")
    mem.add("C", "user", "c")  # exceeds cap → evict least-recently-used (A)

    assert mem.has("A") is False
    assert mem.has("B") is True
    assert mem.has("C") is True


def test_access_refreshes_lru_recency():
    mem = ThreadMemory(max_threads=2)
    mem.add("A", "user", "a")
    mem.add("B", "user", "b")
    # Touch A so it becomes most-recently-used.
    mem.history("A")
    mem.add("C", "user", "c")  # should now evict B, not A

    assert mem.has("A") is True
    assert mem.has("B") is False
    assert mem.has("C") is True


def test_seed_sets_turns_when_empty():
    mem = ThreadMemory()
    seeded = mem.seed("C1:1", [
        {"role": "user", "text": "prior 1"},
        {"role": "assistant", "text": "prior 2"},
    ])
    assert seeded is True
    assert [t["text"] for t in mem.history("C1:1")] == ["prior 1", "prior 2"]


def test_seed_is_noop_when_thread_has_turns():
    mem = ThreadMemory()
    mem.add("C1:1", "user", "existing")
    seeded = mem.seed("C1:1", [{"role": "user", "text": "should not apply"}])
    assert seeded is False
    assert [t["text"] for t in mem.history("C1:1")] == ["existing"]


def test_seed_trims_to_turn_cap():
    mem = ThreadMemory(max_turns_per_thread=2)
    mem.seed("C1:1", [
        {"role": "user", "text": "1"},
        {"role": "assistant", "text": "2"},
        {"role": "user", "text": "3"},
    ])
    assert [t["text"] for t in mem.history("C1:1")] == ["2", "3"]


def _run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"✓ {t.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"✗ {t.__name__}: {e}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    return failures


if __name__ == "__main__":
    sys.exit(1 if _run_all() else 0)
