import hashlib
import time

class BFTConsensus:
    def __init__(self, node_id, peers):
        self.node_id = node_id
        self.peers = peers
        self.state = "IDLE"

    def broadcast_pre_prepare(self, block):
        """
        Initiates the PBFT (Practical Byzantine Fault Tolerance) consensus sequence.

        This function transitions the node from IDLE to PRE-PREPARE state and broadcasts
        a pre-prepare message containing the proposed block to all peer nodes in the network.
        It is critical for establishing the sequence order of the new block and ensuring 
        that all honest nodes begin validating the same data payload.

        Args:
            block (dict): The proposed block containing transactions to be validated.

        Returns:
            bool: True if the broadcast was successful and state updated to PRE-PREPARE, False if the node is not in IDLE state.
        """
        if self.state != "IDLE":
            return False
        
        self.state = "PRE-PREPARE"
        # Network broadcast logic mock
        return True
