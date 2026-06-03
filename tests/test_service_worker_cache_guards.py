# SPDX-License-Identifier: MIT
from pathlib import Path


SW = Path(__file__).resolve().parents[1] / "explorer" / "static" / "js" / "sw.js"


def test_service_worker_only_deletes_rustchain_caches():
    source = SW.read_text(encoding="utf-8")

    assert "const CACHE_PREFIX = 'rustchain-';" in source
    assert "function isRustChainCache(name)" in source
    assert "function isCurrentCache(name)" in source
    assert "return isRustChainCache(name) && !isCurrentCache(name);" in source
    assert ".filter(isRustChainCache)" in source
    assert "return name !== CACHE_NAME && name !== API_CACHE_NAME;" not in source
    assert "cacheNames.map((name) => caches.delete(name))" not in source


def test_service_worker_only_caches_successful_api_responses():
    source = SW.read_text(encoding="utf-8")

    assert "function isCacheableResponse(response)" in source
    assert "response && response.ok && (response.type === 'basic' || response.type === 'cors')" in source
    assert "if (!isCacheableResponse(response)) {" in source
    assert "return response;" in source
    assert "const responseClone = response.clone();" in source


def test_service_worker_handles_missing_accept_header_for_offline_html_fallback():
    source = SW.read_text(encoding="utf-8")

    assert "(request.headers.get('accept') || '').includes('text/html')" in source
    assert "request.headers.get('accept').includes('text/html')" not in source
