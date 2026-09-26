# DONE — T10e build (MC 1355.16)

ID | claim | STATUS | evidence
D1 | Commit on main implementing T10b-design REV2 (locator package, three guarded ALTERs, store-scoped Tjek ingest, menu dedup+filter+offer_sources, auth-gated preview, UI) | PASS | commit 793f991fda6cc0f761d01936765f72900f5acce6 on main ("matapp: store-level selection per postnummer (MC 1355.16)", 23 files, +1769/-16); diff stat in T10e-build-verdict.md §1
D2 | Offline fixture tests for every design-specified test incl. the P0 regression (store-scoped write must not overwrite a NULL chain-level row) | PASS | tests/test_locator.py + tests/test_store_scoping.py (24 new tests); P0 test: test_p0_store_scoped_write_never_overwrites_chain_level_row (both orders, NULL rows survive)
D3 | Fresh suite (clean __pycache__/.pytest_cache) all pass, EXIT=0 | PASS | `/srv/workspace/hotell/.venv/bin/python -m pytest tests/ -q` -> "95 passed, 3 warnings in 8.14s", EXIT=0 (raw: .tmp/final_suite.txt in the repo)
D4 | Live sanity ONCE: resolve 41451 -> nearest store per chain recorded | PASS | .tmp/live_sanity_output.json: ica/willys/coop/lidl all status ok with real store names (e.g. Willys Hemma Göteborg Majorna 1.343 km, Coop Mariagatan 0.746 km)
D5 | Live sanity ONCE: one store-scoped Tjek feed pulled | PASS | .tmp/live_sanity_output.json: Willys Alingsås Hagaplan id 2149, 111 entries, all stamped "2149:<hotspot>" + store_id; nearest store (Majorna) has no catalog this week -> designed logged fallback
D6 | Live sanity ONCE: menu journey with postal_code profile, offer_sources recorded | PASS | .tmp/live_menu_output.json: PUT /api/profile 200 (all four chains ok persisted), GET /api/menu 200, offer_sources_count 255, 15/15 days with used_offer_ids
D7 | T10d build-time musts N1-N4 implemented | PASS | per-finding notes §2 of T10e-build-verdict.md (rule-1 loud ValueError, coop cold-start policy stated + partial-run-persists-nothing test, dedup key in code, bounded caches TTL 24h + max 128)
D8 | DA gate over the BUILD (this dir's DA-verdict.md) | UNVERIFIED | this producing child cannot write the devils-advocate verdict; the orchestrator must spawn the DA phase into this out dir
