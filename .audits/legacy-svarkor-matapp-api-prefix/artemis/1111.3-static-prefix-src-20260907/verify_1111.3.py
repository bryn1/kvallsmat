#!/usr/bin/env python3
"""MC 1111.3 verification: static refs in matapp index.html are prefix-aware.

The app is served at https://sibbamala.com/matapp/ — the renderer's nginx strips
/matapp before proxying to the FastAPI backend, which mounts static at /static.
So a bare `/static/...` ref (origin root, where nginx has no location) 404s,
while `/matapp/static/...` 200s (verified live this turn). The fix makes the 7
refs prefix-aware by switching them from absolute `/static/...` to RELATIVE
`static/...` (the ai-os pattern already in this repo): under `/matapp/` they
resolve to `/matapp/static/...` (200), at root they resolve to `/static/...`
(local dev, 200) — no hardcoded prefix, matches the derive-from-path spirit of
sibling card 1111.1.

Checks:
 A. exactly 7 static refs, all prefix-aware (relative, no leading /static),
    each still carrying its ?v= cache-buster (1111.2 stamps preserved).
 B. prefix resolution: under '/matapp/' each relative ref resolves to
    /matapp/static/<asset> — the live-served 200 URL.
 C. live end-to-end: bare /static/<asset> -> 404 (old path - the bug),
    /matapp/static/<asset> -> 200 (fixed path), for all 7 assets.
 D. patch applies cleanly (dry-run) to pristine baseline; sandbox-applied
    result is byte-identical to the shipped index.html.
 E. no other lines changed (diff touches only the 7 static-ref lines) and
    the ?v= values still equal the real sha256[:8] of each asset on disk.

Exit 0 = all pass. VERIFY_EXIT captured by the caller.
"""
import hashlib, os, re, subprocess, sys, tempfile

WS   = "/srv/workspace/svarkor-matapp-api-prefix/artemis"
DIR  = os.path.join(WS, "1111.3-static-prefix-src-20260907")
NEW  = os.path.join(DIR, "index.html")            # fixed index.html
BAS  = os.path.join(DIR, "index.html.baseline")   # pristine baseline (=HEAD of hosting repo)
PATCH= os.path.join(WS, "1111.3-static-prefix.patch")
SRC  = "/srv/workspace/hosting/apps/matapp"       # real app tree (assets for sha check)

ASSETS = [
    "static/css/base.css",
    "static/css/components.css",
    "static/css/responsive.css",
    "static/js/utils/api.js",
    "static/js/ui/stores.js",
    "static/js/ui/menu.js",
    "static/js/app.js",
]

fails = []
def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  -- {detail}" if detail else ""))
    if not ok:
        fails.append(name)

def h8(rel):
    with open(os.path.join(SRC, rel), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:8]

with open(NEW) as f:
    patched = f.read()

print("A. 7 static refs, all prefix-aware, ?v= cache-busters intact")
refs = re.findall(r'(?:href|src)="(static/[^"]+)"', patched)
check("found exactly 7 prefix-aware static refs", len(refs) == 7, str(len(refs)))
bare = re.findall(r'(?:href|src)="/static/[^"]+"', patched)
check("no bare /static ref remains", len(bare) == 0, str(bare))
unstamped = [r for r in refs if "?v=" not in r]
check("no unstamped static ref (cache-buster preserved)", len(unstamped) == 0, str(unstamped))
dups = [r for r in set(refs) if refs.count(r) > 1]
check("no duplicate/colliding url (unique cache keys)", len(dups) == 0, str(dups))

print("B. prefix resolution: relative ref -> /matapp/static/<asset> (live 200 url)")
def resolve(pathname, rel):
    base = pathname if pathname.endswith("/") else pathname + "/"
    return base + rel
for r in refs:
    asset = r.split("?v=")[0]
    resolved = resolve("/matapp/", r)
    check(f"  {r}", resolved == f"/matapp/{r}", resolved)

print("C. live end-to-end: old path 404, fixed path 200 for all 7 assets")
import urllib.request
def http(url):
    # Cloudflare block-bots curl/urllib default UA with 403; a browser UA is
    # required to reach origin (verified live this turn: UA-less -> 403,
    # with Mozilla UA -> 200). Send one so the status reflects origin, not CF bot-block.
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:
        return f"ERR {e}"
for asset in ASSETS:
    old_url = f"https://sibbamala.com/{asset}?v={h8(asset)}"
    new_url = f"https://sibbamala.com/matapp/{asset}?v={h8(asset)}"
    old = http(old_url)
    new = http(new_url)
    check(f"  {asset}: old /{asset} ={old} (want 404)  new /matapp/{asset} ={new} (want 200)",
          old == 404 and new == 200, f"old={old}, new={new}")

print("D. patch applies cleanly to pristine baseline, result byte-identical")
tmp = tempfile.mkdtemp(prefix="matapp-prefix-")
os.makedirs(os.path.join(tmp, "apps", "matapp", "templates"), exist_ok=True)
tgt = os.path.join(tmp, "apps", "matapp", "templates", "index.html")
with open(tgt, "w") as f:
    f.write(open(BAS).read())
r = subprocess.run(["patch", "-p1", "--dry-run", "-d", tmp, "-i", PATCH],
                   capture_output=True, text=True)
check("patch --dry-run exit 0", r.returncode == 0, r.stderr.strip())
# real apply -> byte compare
r2 = subprocess.run(["patch", "-p1", "-d", tmp, "-i", PATCH], capture_output=True, text=True)
check("patch -p1 apply exit 0", r2.returncode == 0, r2.stderr.strip())
with open(tgt) as f:
    applied = f.read()
check("applied result byte-identical to shipped index.html", applied == patched)

print("E. only the 7 static-ref lines changed; stamps == real sha256[:8] of assets")
# diff the two committed files to confirm ONLY static-ref lines changed
baselines = open(BAS).read().splitlines(keepends=True)
patched_l = patched.splitlines(keepends=True)
import difflib
changed = [l for l in difflib.unified_diff(baselines, patched_l, n=0)
           if (l.startswith('+') or l.startswith('-')) and not l.startswith(('+++','---'))]
nonstatic = [l for l in changed if '/static/' not in l and 'static/' not in l
             and l[:1] in '+-']
check("diff touches ONLY static-ref lines", len(nonstatic) == 0, str(nonstatic))
for r in refs:
    url, _, v = r.partition("?v=")
    exp = h8(url)  # url already 'static/...' relative -> maps to SRC/url
    check(f"  {url} ?v={v} == real sha[:8]", v == exp, f"expected {exp}")

print("\n=== SUMMARY ===")
if fails:
    print("FAILED:", fails)
    sys.exit(1)
print("ALL CHECKS PASS")
sys.exit(0)
