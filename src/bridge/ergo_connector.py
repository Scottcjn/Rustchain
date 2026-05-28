# ErgoBridgeConnector: Interface for connecting RustChain to Ergo mainnet
import requests
from numbers import Real
from urllib.parse import quote

DEFAULT_REQUEST_TIMEOUT_SECONDS = 10


class ErgoBridgeConnector:
    def __init__(
        self,
        ergo_rpc_url,
        rustchain_node_url,
        contract_address,
        request_timeout=DEFAULT_REQUEST_TIMEOUT_SECONDS,
    ):
        if (
            isinstance(request_timeout, bool)
            or not isinstance(request_timeout, Real)
            or request_timeout <= 0
        ):
            raise ValueError("request_timeout must be a positive number")
        self.ergo_rpc_url = ergo_rpc_url
        self.rustchain_node_url = rustchain_node_url
        self.contract_address = contract_address
        self.request_timeout = request_timeout

    def get_merkle_root(self):
        # Get Merkle root from RustChain node
        response = requests.get(
            f'{self.rustchain_node_url}/get_merkle_root',
            timeout=self.request_timeout,
        )
        if response.status_code == 200:
            return response.json()['merkle_root']
        else:
            raise Exception('Failed to fetch Merkle root from RustChain')

    def submit_merkle_root_to_ergo(self, merkle_root):
        # Submit Merkle root to Ergo contract
        data = {"contract_address": self.contract_address, "merkle_root": merkle_root}
        response = requests.post(
            f'{self.ergo_rpc_url}/submit_merkle_root',
            json=data,
            timeout=self.request_timeout,
        )
        if response.status_code != 200:
            raise Exception('Failed to submit Merkle root to Ergo')
        return response.json()

    def verify_contract(self):
        # Verify if the contract exists on Ergo
        contract_path = quote(self.contract_address, safe="")
        response = requests.get(
            f'{self.ergo_rpc_url}/verify_contract/{contract_path}',
            timeout=self.request_timeout,
        )
        if response.status_code == 200:
            return response.json()['status'] == 'exists'
        else:
            raise Exception('Failed to verify contract on Ergo')
