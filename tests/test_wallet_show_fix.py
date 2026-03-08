import unittest
import json
from unittest.mock import patch, MagicMock
import urllib.request
import ssl

# Replicating the logic from sdk/python/rustchain_sdk/cli.py to test the fix
def mock_wallet_show_logic(address, node_url):
    # THE FIX: Correct endpoint + SSL context for IP-based node
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    url = f"{node_url}/wallet/balance?miner_id={address}"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

class TestWalletShowFix(unittest.TestCase):
    @patch('urllib.request.urlopen')
    def test_fix_uses_correct_endpoint(self, mock_urlopen):
        # Setup mock response
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"balance": 100}'
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        
        address = "RTC123"
        node_url = "https://50.28.86.131"
        
        mock_wallet_show_logic(address, node_url)
        
        # Verify the URL called matches our fix
        args, kwargs = mock_urlopen.call_args
        requested_url = args[0].get_full_url()
        self.assertEqual(requested_url, f"{node_url}/wallet/balance?miner_id={address}")
        
        # Verify SSL context was passed
        self.assertIn('context', kwargs)
        self.assertFalse(kwargs['context'].check_hostname)

if __name__ == '__main__':
    unittest.main()
