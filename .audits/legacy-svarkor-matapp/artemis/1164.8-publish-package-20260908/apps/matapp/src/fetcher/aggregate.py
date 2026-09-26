"""M2 fetcher.aggregate — CONTRACT C2 part 2.

aggregate(feeds) -> RawFeed

Merges the per-grocer RawFeeds of a week into one flat RawFeed. Fail-tolerant like the
pull: an empty or malformed feed contributes nothing; non-dict entries are dropped.
Callers hand the result to the normalizer (C4) for the running-week filter + mapping.
"""
from __future__ import annotations


def aggregate(feeds) -> dict:
    week_key = None
    entries = []
    for feed in feeds:
        if not isinstance(feed, dict):
            continue
        week_key = week_key or feed.get("week_key")
        for e in feed.get("entries") or []:
            if isinstance(e, dict):
                entries.append(e)
    return {"week_key": week_key, "entries": entries}
