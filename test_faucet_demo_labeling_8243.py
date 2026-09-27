"""
Regression tests for issue #8243:
"Retire or clearly label legacy faucet.py (records drips, sends nothing)
 + fix FAUCET.md + audit mock_mode".

Two independent silent-success failures are covered here:

1. Root `faucet.py` performs no node call at all, yet answered every drip with
   a success payload and the UI copy "Sent X RTC". It must now identify itself
   as a demo in the payload (`sent: false`) and in the page.

2. `faucet_service/faucet_service.py` defaulted `mock_mode` to True, so a faucet
   deployed without an explicit setting recorded drips and paid nobody. The
   default is now False, and a configuration that cannot pay is reported at
   startup instead of one 500 per drip.

Run:
    python -m pytest test_faucet_demo_labeling_8243.py -v
"""

import importlib.util
import inspect
import os
import re
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO_ROOT)

import faucet  # noqa: E402  (root demo faucet)


def _load_faucet_service():
    """Import faucet_service/faucet_service.py under its own module name."""
    path = os.path.join(REPO_ROOT, 'faucet_service', 'faucet_service.py')
    spec = importlib.util.spec_from_file_location('faucet_service_8243', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules['faucet_service_8243'] = module
    spec.loader.exec_module(module)
    return module


faucet_service = _load_faucet_service()


# ---------------------------------------------------------------------------
# 1. Root faucet.py must not claim it sent anything
# ---------------------------------------------------------------------------

@pytest.fixture()
def demo_client(tmp_path, monkeypatch):
    """Flask test client for the demo faucet, backed by a throwaway DB."""
    monkeypatch.setattr(faucet, 'DATABASE', str(tmp_path / 'faucet.db'))
    faucet.init_db()
    faucet.app.config['TESTING'] = True
    with faucet.app.test_client() as client:
        yield client


WALLET = 'RTC' + 'a' * 40


class TestDemoFaucetPayload:
    def test_drip_reports_that_nothing_was_sent(self, demo_client):
        resp = demo_client.post('/faucet/drip', json={'wallet': WALLET})
        assert resp.status_code == 200
        data = resp.get_json()
        # The request is accepted and recorded ...
        assert data['ok'] is True
        assert data['wallet'] == WALLET
        # ... but the payload must state that no transfer happened.
        assert data['sent'] is False
        assert data['demo'] is True
        assert data['tx_hash'] is None
        assert 'no RTC was sent' in data['notice']

    def test_amount_is_not_advertised_as_a_transfer(self, demo_client):
        """`amount` may stay for rate-limit accounting, but not alone."""
        data = demo_client.post('/faucet/drip', json={'wallet': WALLET}).get_json()
        assert data['amount'] == faucet.MAX_DRIP_AMOUNT
        # A client that only knows the old schema must still be able to detect
        # the demo from a field that did not exist before.
        assert 'sent' in data

    def test_rate_limited_response_is_unchanged(self, demo_client):
        demo_client.post('/faucet/drip', json={'wallet': WALLET})
        resp = demo_client.post('/faucet/drip', json={'wallet': WALLET})
        assert resp.status_code == 429
        assert resp.get_json()['ok'] is False


class TestDemoFaucetCopy:
    def test_page_warns_that_it_does_not_pay(self, demo_client):
        body = demo_client.get('/faucet').get_data(as_text=True)
        assert 'DEMO' in body
        assert 'does not pay' in body.lower()

    def test_success_copy_does_not_claim_rtc_was_sent(self, demo_client):
        body = demo_client.get('/faucet').get_data(as_text=True)
        # The old copy was: "✅ Success! Sent ' + data.amount + ' RTC to '"
        assert not re.search(r"Success!\s*Sent", body)
        assert 'no RTC was sent' in body

    def test_module_is_stamped_as_demo(self):
        doc = faucet.__doc__ or ''
        assert 'DEMO' in doc
        assert 'does not pay' in doc.lower()
        assert faucet.DEMO_MODE is True

    def test_module_makes_no_node_call(self):
        """The demo must stay a demo: no HTTP client is wired in.

        This is the whole point of #8243 -- the module claims a transfer it
        never attempts. If someone later adds a real transfer here, this test
        fails and the demo labelling has to be revisited.
        """
        source = inspect.getsource(faucet)
        assert not re.search(r'^\s*import requests', source, re.M)
        assert not re.search(r'^\s*import urllib', source, re.M)
        assert 'requests.post(' not in source
        assert 'urlopen(' not in source


# ---------------------------------------------------------------------------
# 2. faucet_service mock_mode default + startup audit
# ---------------------------------------------------------------------------

class TestMockModeDefault:
    def test_default_config_does_not_enable_mock_mode(self):
        assert faucet_service.DEFAULT_CONFIG['distribution']['mock_mode'] is False

    def test_config_without_mock_mode_key_is_treated_as_real(self):
        """A partial config file must not silently fall back to mock mode."""
        source = inspect.getsource(faucet_service)
        assert "get('mock_mode', True)" not in source

    def test_status_reports_real_mode_for_a_config_without_the_key(self):
        vars_ = faucet_service.get_template_vars({'distribution': {}})
        assert vars_['mock_mode'] is False


def _config(mock_mode=False, admin_key=None):
    dist = {'amount': 0.5, 'mock_mode': mock_mode}
    if admin_key is not None:
        dist['admin_key'] = admin_key
    return {'distribution': dist}


class TestStartupAudit:
    def test_real_mode_without_admin_key_refuses_to_start(self, monkeypatch):
        monkeypatch.delenv('RC_ADMIN_KEY', raising=False)
        with pytest.raises(faucet_service.FaucetConfigError) as exc:
            faucet_service.check_distribution_config(_config(), strict=True)
        assert 'RC_ADMIN_KEY' in str(exc.value)

    def test_real_mode_with_env_admin_key_is_healthy(self, monkeypatch):
        monkeypatch.setenv('RC_ADMIN_KEY', 'secret')
        assert faucet_service.check_distribution_config(_config(), strict=True) == []

    def test_real_mode_with_config_admin_key_is_healthy(self, monkeypatch):
        monkeypatch.delenv('RC_ADMIN_KEY', raising=False)
        cfg = _config(admin_key='secret')
        assert faucet_service.check_distribution_config(cfg, strict=True) == []

    def test_non_strict_reports_instead_of_raising(self, monkeypatch):
        monkeypatch.delenv('RC_ADMIN_KEY', raising=False)
        problems = faucet_service.check_distribution_config(_config(), strict=False)
        assert problems and 'RC_ADMIN_KEY' in problems[0]

    def test_mock_mode_is_announced_but_allowed(self, monkeypatch, caplog):
        monkeypatch.delenv('RC_ADMIN_KEY', raising=False)
        with caplog.at_level('WARNING', logger='rustchain_faucet'):
            problems = faucet_service.check_distribution_config(
                _config(mock_mode=True), strict=True
            )
        assert problems == ['distribution.mock_mode is enabled: no RTC will be sent']
        assert 'NO RTC WILL BE SENT' in caplog.text

    def test_empty_config_is_audited_without_crashing(self, monkeypatch):
        monkeypatch.delenv('RC_ADMIN_KEY', raising=False)
        problems = faucet_service.check_distribution_config({}, strict=False)
        assert problems and 'RC_ADMIN_KEY' in problems[0]


# ---------------------------------------------------------------------------
# 3. Shipped configuration and documentation
# ---------------------------------------------------------------------------

class TestShippedConfigAndDocs:
    def test_example_config_does_not_ship_mock_mode_on(self):
        import yaml
        path = os.path.join(REPO_ROOT, 'faucet_service', 'faucet_config.yaml')
        with open(path, encoding='utf-8') as handle:
            cfg = yaml.safe_load(handle)
        assert cfg['distribution']['mock_mode'] is False

    def test_deploy_script_keeps_mock_mode_off(self):
        path = os.path.join(REPO_ROOT, 'testnet', 'deploy_testnet.sh')
        with open(path, encoding='utf-8') as handle:
            body = handle.read()
        assert re.search(r'^\s*mock_mode:\s*false', body, re.M)
        assert 'RC_ADMIN_KEY' in body

    def test_faucet_md_points_at_the_service(self):
        with open(os.path.join(REPO_ROOT, 'FAUCET.md'), encoding='utf-8') as handle:
            body = handle.read()
        assert 'faucet_service/faucet_service.py' in body
        # It must no longer tell operators to run the demo.
        assert not re.search(r'^\s*python faucet\.py\s*$', body, re.M)
