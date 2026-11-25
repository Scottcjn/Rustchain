import os
import re
from pathlib import Path

target_files = []
for root, dirs, files in os.walk('.'):
    if '.git' in root or 'node_modules' in root or 'venv' in root:
        continue
    for file in files:
        if file.endswith('.md'):
            target_files.append(os.path.join(root, file))

section_to_inject = """
## Where is my config?

Depending on how you installed Rustchain, your configuration file will be located in one of two places:
- **`~/.rustchain/config.json`** (if you used `setup.sh`, `install-miner.sh`, or followed `INSTALL.md`)
- **`/opt/rustchain-miner/config.json`** (if you used `rustchain.org/install.sh` system-wide installer)

You can find it by running:
```bash
cat /opt/rustchain-miner/config.json 2>/dev/null || cat ~/.rustchain/config.json
