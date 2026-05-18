from pathlib import Path

JS = Path('explorer/static/js/explorer.js').read_text()


def test_explorer_normalizes_paginated_miners_response():
    assert 'function normalizeMinersResponse(response)' in JS
    assert 'response?.miners || []' in JS
    assert "state.miners = normalizeMinersResponse(await fetchAPI('/api/miners'));" in JS


def test_explorer_keeps_legacy_array_response_compatible():
    assert 'Array.isArray(response) ? response' in JS
