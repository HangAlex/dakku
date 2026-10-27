"""Reads your Anki progress through the AnkiConnect add-on (Anki must be open on this PC).

Dakku asks from the server side, so your phone can see your Anki numbers from anywhere.
"""
import json
import urllib.request


def call(url, action, params=None, timeout=4):
    body = json.dumps({"action": action, "version": 6, "params": params or {}}).encode()
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.load(response)
    if data is None:
        raise PermissionError("AnkiConnect refused the request")
    if data.get("error"):
        raise RuntimeError(data["error"])
    return data.get("result")


def snapshot(url):
    names = call(url, "deckNames")
    by_day = call(url, "getNumCardsReviewedByDay")
    counts = {}
    for name in names:
        try:
            stats = call(url, "getDeckStats", {"decks": [name]})
        except Exception:  # Anki hides an empty "Default" deck, and asking for it fails
            continue
        for deck in (stats or {}).values():
            counts[name] = [deck["new_count"], deck["learn_count"], deck["review_count"]]
    return {"decks": sorted(n for n in names if n in counts), "counts": counts, "byDay": by_day}
