"""app.ingest — offer-ingest line for the matapp framtidsvision (Phase 4 T3).

Pipeline: grocer (pull) -> normalizer (RawOffer->NormalizedOffer w/ reference price +
per-ingredient extrapris flag) -> ingest.ingest_week (persist to offers table).

Stänger closure-gap 1 (PHASE0.md §A): RawOffer->NormalizedOffer->Offer carries
regular_price_cents / savings_cents, so Phase 6 optimizer can measure the >=50%-extrapris
"majoritet" rule. httpx is a RUNTIME dep here (DA FIX-1) — pinned in requirements.txt,
not dev-only.
"""
