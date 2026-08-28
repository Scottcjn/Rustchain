from pathlib import Path

README = Path(__file__).resolve().parents[1] / 'README.md'


def test_readme_explains_active_nodes_vs_active_miners():
    text = README.read_text(encoding='utf-8')
    assert '| **Identity** | Hardware fingerprinting — agents prove they run on real machines, not spoofed VMs | Live — active miner count is dynamic; see `/api/miners` |' in text
    assert '| 5 attestation nodes across 3 continents (NA ×3, Asia ×1, Local ×1) | [Live explorer](https://rustchain.org/explorer/) |' in text
    assert '| Live active miners count (changes over time) | `curl -fsS https://rustchain.org/api/miners` |' in text
    assert '| **Identity** | Hardware fingerprinting — agents prove they run on real machines, not spoofed VMs | Live, 20+ miners |' not in text
    assert '| 20+ miners attesting | `curl -fsS https://rustchain.org/api/miners` |' not in text
