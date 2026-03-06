import platform, subprocess, re, json, hashlib, os

def detect_unique_hardware_signature():
    unique_markers = {}

    try:
        if platform.system() == 'Darwin':
            output = subprocess.check_output(['system_profiler', 'SPHardwareDataType']).decode()
            hw_uuid = re.search(r'Hardware UUID: (.*)', output)
            if hw_uuid:
                unique_markers['hardware_uuid'] = hw_uuid.group(1).strip()
        elif platform.system() == 'Windows':
            mb_serial = subprocess.check_output(['wmic', 'baseboard', 'get', 'serialnumber']).decode().strip().split('\n')[1].strip()
            cpu_id = subprocess.check_output(['wmic', 'cpu', 'get', 'processorid']).decode().strip().split('\n')[1].strip()
            unique_markers['mb_serial'] = mb_serial
            unique_markers['cpu_id'] = cpu_id
        elif platform.system() == 'Linux':
            for tag in ['system-serial-number', 'bios-version', 'baseboard-product-name']:
                try:
                    out = subprocess.check_output(['dmidecode', '-s', tag]).decode().strip()
                    unique_markers[tag] = out
                except:
                    continue
    except Exception as e:
        unique_markers['error'] = str(e)

    sig_data = json.dumps(unique_markers, sort_keys=True).encode()
    hardware_signature = hashlib.sha256(sig_data).hexdigest()
    return hardware_signature, unique_markers
