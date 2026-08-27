#!/usr/bin/env python3
"""Quick markdown external link checker (requests-based). Excludes localhost/IPs."""
import os, re, sys, requests
from urllib.parse import urlparse

EXCLUDE = re.compile(r"127\.0\.0\.1|localhost|50\.28\.86\.131|rustchain\.org/faq")
URL_RE = re.compile(r"https?://[^\s)\]>'\"`]+")
SKIP_EXT = (".png", ".jpg", ".svg", ".ico", ".woff", ".ttf")

def md_files(root):
    for dp, _, fns in os.walk(root):
        if "node_modules" in dp or ".git" in dp:
            continue
        for f in fns:
            if f.endswith(".md"):
                yield os.path.join(dp, f)

def main(root="."):
    urls = {}
    for fp in md_files(root):
        try:
            txt = open(fp, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        for m in URL_RE.findall(txt):
            u = m.rstrip(".,)")
            if EXCLUDE.search(u): continue
            if u.lower().endswith(SKIP_EXT): continue
            urls.setdefault(u, []).append(fp)
    print(f"Checking {len(urls)} unique URLs...")
    broken = {}
    s = requests.Session(); s.headers["User-Agent"] = "Mozilla/5.0 linkcheck"
    for u in urls:
        try:
            r = s.get(u, timeout=15, allow_redirects=True)
            if r.status_code >= 400:
                broken[u] = (r.status_code, urls[u][:2])
        except Exception as e:
            broken[u] = (f"ERR:{type(e).__name__}", urls[u][:2])
    print(f"\nBROKEN ({len(broken)}):")
    for u, (st, fns) in sorted(broken.items()):
        print(f"  {st}  {u}")
        print(f"        in: {fns}")
    return 0 if not broken else 1

sys.exit(main())
