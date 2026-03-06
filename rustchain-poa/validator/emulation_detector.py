import platform, subprocess

def detect_emulation():
    emu_flags = []
    score = 0
    try:
        if platform.system() == 'Linux':
            output = subprocess.check_output(['systemd-detect-virt']).decode().strip()
            if output and output != 'none':
                emu_flags.append(f"Detected virtualization: {output}")
                score += 50
    except:
        pass
    return {'flags': emu_flags, 'score': score, 'likely_emulated': score > 30}
