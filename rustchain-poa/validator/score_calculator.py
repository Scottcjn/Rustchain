from .hardware_fingerprint import detect_unique_hardware_signature
from .emulation_detector import detect_emulation

def calculate_score():
    score = 1000
    emu = detect_emulation()

    # Apply emulation penalties
    if emu['likely_emulated']:
        score -= 800  # Max penalty
        print("🔻 Emulation detected! Applying penalty.")

    # Unique hardware fingerprint bonus
    sig, markers = detect_unique_hardware_signature()
    bonus = min(len(markers) * 50, 500)
    score += bonus

    # Additional heuristics
    if 'hardware_uuid' in markers and len(markers['hardware_uuid']) > 10:
        score += 50
        print("✅ Hardware UUID bonus applied.")

    if 'cpu_id' in markers:
        score += 50
        print("✅ CPU ID bonus applied.")

    return score, sig, emu, markers
