"""
ThreadMemory: an in-memory, per-thread conversation store for Slack Helper.

Keeps a short rolling history of turns per Slack thread so the bot can hold
follow-up conversations with continuity. Bounded two ways so it can never leak
memory in a long-running process:

- max_turns_per_thread: oldest turns in a thread are dropped (FIFO).
- max_threads: least-recently-used threads are evicted once the cap is hit.

State lives only in the process — it is intentionally lost on restart.
No Slack/JIRA/Gemini dependencies, so it can be unit-tested in isolation.
"""

from collections import OrderedDict, deque


class ThreadMemory:
    def __init__(self, max_turns_per_thread=20, max_threads=200):
        self.max_turns_per_thread = max_turns_per_thread
        self.max_threads = max_threads
        # key -> deque[{"role": str, "text": str}]; ordered by recency of use.
        self._threads = OrderedDict()

    def has(self, key):
        """True if the thread exists and holds at least one turn."""
        return key in self._threads and len(self._threads[key]) > 0

    def add(self, key, role, text):
        """Append a turn to a thread, creating it if needed. Refreshes recency."""
        thread = self._touch(key)
        thread.append({"role": role, "text": text})

    def seed(self, key, turns):
        """
        Prime an empty thread with prior turns (e.g. fetched from Slack).

        No-op if the thread already holds turns, so an in-progress conversation
        is never clobbered. Returns True if seeding happened, False otherwise.
        """
        if self.has(key):
            return False
        thread = self._touch(key)
        for turn in turns:
            thread.append({"role": turn["role"], "text": turn["text"]})
        return True

    def history(self, key):
        """Return the thread's turns in order as a fresh list. Refreshes recency."""
        if key not in self._threads:
            return []
        self._threads.move_to_end(key)
        return [dict(turn) for turn in self._threads[key]]

    def _touch(self, key):
        """Get (or create) a thread's deque and mark it most-recently-used."""
        if key in self._threads:
            self._threads.move_to_end(key)
        else:
            self._threads[key] = deque(maxlen=self.max_turns_per_thread)
            self._evict_if_needed()
        return self._threads[key]

    def _evict_if_needed(self):
        while len(self._threads) > self.max_threads:
            self._threads.popitem(last=False)  # drop least-recently-used
