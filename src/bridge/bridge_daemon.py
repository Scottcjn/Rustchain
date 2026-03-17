# BridgeDaemon: Daemon to handle the RustChain to Ergo bridge
import time
from ergo_connector import ErgoBridgeConnector

class BridgeDaemon:
    def __init__(self, ergo_rpc_url, rustchain_node_url, contract_address):
        self.connector = ErgoBridgeConnector(ergo_rpc_url, rustchain_node_url, contract_address)

    def start(self):
        while True:
            try:
                # Get Merkle root from RustChain
                merkle_root = self.connector.get_merkle_root()

                # Verify if contract exists on Ergo
                if self.connector.verify_contract():
                    # Submit Merkle root to Ergo
                    result = self.connector.submit_merkle_root_to_ergo(merkle_root)
                    print(f'Successfully submitted Merkle root: {result}')
                else:
                    print('Contract does not exist on Ergo')

            except Exception as e:
                print(f'Error: {e}')

            time.sleep(60)  # Sleep for 1 minute before retrying
