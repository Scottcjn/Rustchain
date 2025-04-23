import json
from .score_calculator import calculate_score

def validate_genesis(genesis_path):
    with open(genesis_path) as f:
        data = json.load(f)
    score, sig, emu, markers = calculate_score()
    result = {
        'score': score,
        'hardware_signature': sig,
        'emulation': emu,
        'unique_markers': markers,
        'validated': score >= 500
    }
    return result
