from rustchain.models import Miner
def test_miner_model():
    data = {"miner": "abc", "hardware_type": "x86", "antiquity_multiplier": 0.8, "last_attest": 123}
    miner = Miner(**data)
    assert miner.miner == "abc"
