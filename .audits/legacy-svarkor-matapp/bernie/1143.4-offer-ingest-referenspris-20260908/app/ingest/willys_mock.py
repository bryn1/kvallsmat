"""Recorded willys-feed mock for the Phase 4 (T3) offer-ingest gate-C3 harness.

Built from the LIVE willys open feed structure VERIFIED 2026-09-07 (PHASE0-research Q4):
each offer carries BOTH the sale price (price.value=49.9) AND the reference price
(comparePrice "71,29 kr", lowestHistoricalPrice.value=66.9, conditionLabel "Spara ...").

This is the host-mock the harness injects as the httpx-like ``session`` HAL-seam
(PHASE0-map line 72: pull_grocer(grocer_cfg, week_key, session=None)). The entries are
shaped to exercise the reference-price PASSTHROUGH: comparePrice is the willys string form
so the fetcher's parse_swedish_kr() must turn "71,29 kr" -> 7129 cents.

Any week window is honoured: valid_from/to sit inside the week the harness passes so the
normalizer's running-week filter keeps them.
"""

# A small recorded willys week — sale price always below comparePrice (a real "extrapris").
WILLYS_FEED_2026_W37 = {
    "offers": [
        {
            "external_id": "w37-0001",
            "name": "Kvarg vanilj 1kg",
            "price": 49.9,
            "comparePrice": "71,29 kr",
            "lowestHistoricalPrice": {"currencyIso": "SEK", "value": 66.9},
            "conditionLabel": "Spara 17,00 kr/st",
            "unit": "kg",
            "valid_from": "2026-09-07",
            "valid_to": "2026-09-13",
        },
        {
            "external_id": "w37-0002",
            "name": "Havregryn 1kg",
            "price": 19.9,
            "comparePrice": "29,90 kr",
            "lowestHistoricalPrice": {"currencyIso": "SEK", "value": 25.9},
            "unit": "kg",
            "valid_from": "2026-09-07",
            "valid_to": "2026-09-13",
        },
        {
            "external_id": "w37-0003",
            "name": "Ägg 12-pack",
            "price": 39.9,
            # NOTE: deliberately NO comparePrice on this entry — exercises the None path
            # (falls back to lowestHistoricalPrice.value, and stays non-extrapris if the
            # discount is absent). Kept in-week so the normalizer keeps it.
            "lowestHistoricalPrice": {"currencyIso": "SEK", "value": 35.0},
            "unit": "st",
            "valid_from": "2026-09-07",
            "valid_to": "2026-09-13",
        },
    ]
}


class MockSession:
    """Injected httpx-like session (HAL host-mock): serves the recorded willys feed."""

    def __init__(self, feed=WILLYS_FEED_2026_W37, status_code=200):
        self._feed = feed
        self._status_code = status_code
        self.requests = []

    def get(self, url, headers=None):
        self.requests.append({"url": url, "headers": headers or {}})
        feed, status_code = self._feed, self._status_code
        return _Resp(feed, status_code)

    def close(self):
        pass


class _Resp:
    """httpx-like response for the mock session (status_code + json())."""

    def __init__(self, feed, status_code):
        self._feed = feed
        self.status_code = status_code

    def json(self):
        return self._feed
