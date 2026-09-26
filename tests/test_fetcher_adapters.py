"""tests.test_fetcher_adapters — offline unit tests for the real ICA+Lidl
offer fetcher adapters (MC 1355.4).

No network: fixtures are saved HTML/JSON snippets written inline below, shaped
after the live pages fetched during the MC 1355.4 session (ICA
window.__INITIAL_DATA__ -> offers.weeklyOffers; Lidl campaign page
data-grid-data tiles with regionsPrices). Covers: ICA happy path + JS
sanitizer (undefined / new Map) + malformed page -> empty feed; Lidl campaign
JSON happy path + HTML-escaped JSON + missing price fields dropped;
fail-tolerant behaviour (non-200, network exception) through pull_grocer.
"""
from __future__ import annotations

import httpx
import pytest

from src.config import PlannerConfig
from src.fetcher.grocer import pull_grocer

ICA_CFG = PlannerConfig.grocer("ica", "https://www.ica.se/erbjudanden/", chain="ica")
LIDL_CFG = PlannerConfig.grocer("lidl", "https://www.lidl.se/c/erbjudanden",
                                chain="lidl")
WILLYS_CFG = PlannerConfig.grocer("willys", "https://feeds.willys.se/week",
                                  chain="willys")

# ---- ICA fixtures (shaped after the live page, MC 1355.4) -------------------

ICA_HTML = """
<html><script>
window.__INITIAL_DATA__ = {"env":{"BASE":"x"},"offers":{"weeklyOffers":[
 {"id":"5004009053","details":{"brand":"Findus","name":"Fryst torskryggfilé",
  "packageInformation":"420 g","mechanicInfo":"119 kr/st"},
  "validTo":"2026-09-27T00:00:00",
  "parsedMechanics":{"type":"Standard","value2":"119","value4":"/st"},
  "eans":[{"id":"7310500185927"}]},
 {"id":"5004009999","details":{"brand":undefined,"name":"Kaputt",
  "mechanicInfo":"new Map([[1,2]])"},"validTo":"2026-09-27T00:00:00",
  "parsedMechanics":{"value2":"25","value4":"/kg"},"eans":[]}
]}};</script></html>
"""

ICA_MALFORMED = "<html><p>no initial data here</p></html>"

# ---- Lidl fixtures (shaped after the live campaign page) --------------------

LIDL_TILE = ('{"title":"Bananer","productId":66000056,'
             '"regionsPrices":{"1":{"currentLidlPlusPrice":{"price":{'
             '"price":14.9,"endDate":"2026-10-04T21:59:59Z",'
             '"startDate":"2026-09-15T07:46:08.286Z",'
             '"discount":{"deletedPrice":18.8,"discountText":"-20%"},'
             '"basePrice":{"text":"/kg"}}}}}}')

LIDL_NO_PRICE_TILE = ('{"title":"Inget pris","productId":66000057,'
                      '"regionsPrices":{"1":{"currentLidlPlusPrice":{"price":{'
                      '"basePrice":{"text":"/kg"}}}}}}')

LIDL_INDEX = ('<html><a href="/c/lidl-plus-erbjudanden/a10103637">kampanj</a>'
              '<a href="/c/lidl-plus-erbjudanden/a10103637">dup</a>'
              '<a href="/c/veckans-frukt-groent/a10103022">frukt</a></html>')

LIDL_CAMPAIGN = ('<html><div data-grid-data="{&quot;title&quot;:&quot;Bananer&quot;,'
                 '&quot;productId&quot;:66000056,&quot;regionsPrices&quot;:{&quot;1&quot;:'
                 '{&quot;currentLidlPlusPrice&quot;:{&quot;price&quot;:{&quot;price&quot;:14.9,'
                 '&quot;endDate&quot;:&quot;2026-10-04T21:59:59Z&quot;,'
                 '&quot;startDate&quot;:&quot;2026-09-15T07:46:08.286Z&quot;,'
                 '&quot;discount&quot;:{&quot;deletedPrice&quot;:18.8},'
                 '&quot;basePrice&quot;:{&quot;text&quot;:&quot;/kg&quot;}}}}}}"></div>'
                 '<div data-grid-data="' + LIDL_NO_PRICE_TILE.replace('"', "&quot;")
                 + '"></div></html>')


class FakeResp:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text

    def json(self):
        import json
        return json.loads(self.text)


class FakeSession:
    """httpx-like test double mapping url -> (status, text)."""

    def __init__(self, pages: dict, exc: Exception | None = None):
        self.pages = pages
        self.exc = exc
        self.calls: list[str] = []

    def get(self, url, headers=None):
        self.calls.append(url)
        if self.exc is not None:
            raise self.exc
        status, text = self.pages.get(url, (404, ""))
        return FakeResp(status, text)


# ---- ICA --------------------------------------------------------------------

def test_ica_parse_happy_path():
    from src.fetcher.adapters import ica

    entries = ica.parse_ica_offers(ICA_HTML, week_start="2026-09-21")
    assert len(entries) == 2
    first = entries[0]
    assert first["external_id"] == "5004009053"  # bare id — mapper owns the prefix
    assert first["name"] == "Findus Fryst torskryggfilé"
    assert first["price"] == 119.0
    assert first["unit"] == "st"
    assert first["valid_to"] == "2026-09-27"
    # ICA's page carries no regular piece price (comparisonPrice is the SALE
    # price per kg) -> no regular_price key, never an invented one.
    assert "regular_price" not in first


def test_ica_sanitizer_undefined_and_new_map():
    from src.fetcher.adapters import ica

    entries = ica.parse_ica_offers(ICA_HTML)
    # the second item carries undefined + new Map(...) literals; the sanitizer
    # must let the whole blob parse and the item keep its numeric mechanics
    kaputt = [e for e in entries if e["external_id"] == "5004009999"]
    assert len(kaputt) == 1
    assert kaputt[0]["price"] == 25.0
    assert kaputt[0]["unit"] == "kg"


def test_ica_malformed_page_yields_empty_feed():
    from src.fetcher.adapters import ica

    assert ica.parse_ica_offers(ICA_MALFORMED) == []
    assert ica.parse_ica_offers("") == []
    # truncated blob (unbalanced braces) -> empty, never a raise
    assert ica.parse_ica_offers('<script>window.__INITIAL_DATA__ = {"a":') == []


def test_ica_pull_fail_tolerant_non200_and_exception():
    ok = pull_grocer(ICA_CFG, "2026-W39",
                     session=FakeSession({"https://www.ica.se/erbjudanden/": (500, "")}))
    assert ok == {"grocer_id": "ica", "week_key": "2026-W39", "entries": []}

    boom = pull_grocer(ICA_CFG, "2026-W39",
                       session=FakeSession({}, exc=httpx.ConnectError("dns")))
    assert boom["entries"] == []


def test_ica_pull_happy_path_through_contract():
    session = FakeSession({"https://www.ica.se/erbjudanden/": (200, ICA_HTML)})
    feed = pull_grocer(ICA_CFG, "2026-W39", session=session)
    assert feed["grocer_id"] == "ica"
    assert feed["week_key"] == "2026-W39"
    assert len(feed["entries"]) == 2
    # valid_from is the ISO week's Monday
    assert feed["entries"][0]["valid_from"] == "2026-09-21"


# ---- Lidl -------------------------------------------------------------------

def test_lidl_campaign_urls_deduped_in_order():
    from src.fetcher.adapters import lidl

    urls = lidl.find_campaign_urls(LIDL_INDEX)
    assert urls == ["/c/lidl-plus-erbjudanden/a10103637",
                    "/c/veckans-frukt-groent/a10103022"]


def test_lidl_campaign_parse_happy_path_and_missing_price_dropped():
    from src.fetcher.adapters import lidl

    entries = lidl.parse_lidl_campaign(LIDL_CAMPAIGN, week_start="2026-09-21")
    assert len(entries) == 1  # the no-price tile is dropped
    e = entries[0]
    assert e["external_id"] == "66000056"
    assert e["name"] == "Bananer"
    assert e["price"] == 14.9
    assert e["regular_price"] == 18.8  # deletedPrice -> reference price (MC 1355.7)
    assert e["unit"] == "kg"
    assert e["valid_from"] == "2026-09-15"
    assert e["valid_to"] == "2026-10-04"


def test_lidl_pull_follows_campaign_pages():
    session = FakeSession({
        "https://www.lidl.se/c/erbjudanden": (200, LIDL_INDEX),
        "https://www.lidl.se/c/lidl-plus-erbjudanden/a10103637": (200, LIDL_CAMPAIGN),
        "https://www.lidl.se/c/veckans-frukt-groent/a10103022": (404, ""),
    })
    feed = pull_grocer(LIDL_CFG, "2026-W39", session=session)
    assert feed["grocer_id"] == "lidl"
    assert len(feed["entries"]) == 1
    assert feed["entries"][0]["external_id"] == "66000056"


def test_lidl_pull_fail_tolerant_non200_and_exception():
    ok = pull_grocer(LIDL_CFG, "2026-W39",
                     session=FakeSession({"https://www.lidl.se/c/erbjudanden": (503, "")}))
    assert ok["entries"] == []

    boom = pull_grocer(LIDL_CFG, "2026-W39",
                       session=FakeSession({}, exc=httpx.ReadTimeout("t")))
    assert boom["entries"] == []


# ---- dispatch / contract ----------------------------------------------------

def test_dispatch_unknown_chain_falls_back_to_legacy_pull():
    # hemkop has no real adapter: pull_grocer must still use the legacy
    # {base}/veckans-extrapris path (contract preserved). (Willys gained a
    # real Tjek adapter in MC 1355.10, so it no longer exercises this path.)
    hemkop = PlannerConfig.grocer("hemkop", "https://feeds.hemkop.se/week",
                                  chain="hemkop")
    session = FakeSession({
        "https://feeds.hemkop.se/week/veckans-extrapris":
            (200, '{"offers":[{"external_id":"h1","name":"Mjölk","price":12.5,'
                  '"unit":"l","valid_from":"2026-09-21","valid_to":"2026-09-27"}]}'),
    })
    feed = pull_grocer(hemkop, "2026-W39", session=session)
    assert feed["entries"][0]["external_id"] == "h1"


def test_week_start_helper():
    from src.fetcher.adapters import week_start

    assert week_start("2026-W39") == "2026-09-21"
    assert week_start("garbage") == ""
    assert week_start("") == ""


@pytest.mark.parametrize("html", ["", ICA_MALFORMED])
def test_ica_never_raises_on_garbage(html):
    from src.fetcher.adapters import ica

    assert ica.parse_ica_offers(html) == []
