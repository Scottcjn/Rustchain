import os, platform, shutil, subprocess

# Only ever resolve the virtualization-detection helper from trusted, root-owned
# system directories — never from an attacker-controllable PATH. PoA rewards
# authentic vintage hardware, so a node operator running inside a VM/emulator is
# the adversary here: if `systemd-detect-virt` were looked up via PATH, that
# operator could plant a fake binary earlier on PATH that always prints "none"
# and make emulated hardware pass as physical.
_TRUSTED_BIN_DIRS = (
    "/usr/bin",
    "/bin",
    "/usr/sbin",
    "/sbin",
    "/run/current-system/sw/bin",  # NixOS
)


def _resolve_detect_virt():
    """Return an absolute path to systemd-detect-virt found only in trusted
    system directories, or None if it is not present in any of them."""
    return shutil.which(
        "systemd-detect-virt", path=os.pathsep.join(_TRUSTED_BIN_DIRS)
    )


def detect_emulation():
    emu_flags = []
    score = 0
    try:
        if platform.system() == 'Linux':
            detect_virt = _resolve_detect_virt()
            if detect_virt:
                output = subprocess.check_output([detect_virt]).decode().strip()
                if output and output != 'none':
                    emu_flags.append(f"Detected virtualization: {output}")
                    score += 50
    except:
        pass
    return {'flags': emu_flags, 'score': score, 'likely_emulated': score > 30}
