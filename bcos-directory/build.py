#!/usr/bin/env python3
"""
BCOS Directory Build Script
Embeds data/projects.json directly into index.html for a self-contained dist/.
No server required — drop dist/index.html anywhere.
"""
import json, re, sys, os
from pathlib import Path

SRC = Path(__file__).parent / "index.html"
DATA = Path(__file__).parent / "data" / "projects.json"
OUT  = Path(__file__).parent / "dist" / "index.html"

def build():
    print("📦 Building BCOS Certified Directory…")

    # Load data
    with open(DATA, encoding="utf-8") as f:
        projects = json.load(f)

    # Load HTML
    with open(SRC, encoding="utf-8") as f:
        html = f.read()

    # Inject data as JS variable inside a <script> tag at the end of <body>
    # Replace the fetch() call with direct data injection
    embedded_script = f"""
    <script id="bcos-data" type="application/json">
    {json.dumps(projects, indent=2)}
    </script>
    <script>
    (function() {{
        const el = document.getElementById('bcos-data');
        if (el) {{
            try {{
                const data = JSON.parse(el.textContent);
                window.__BCOS_DATA__ = data;
                // Override init to use embedded data
                const _origInit = window.init;
                window.init = async function() {{
                    allProjects = window.__BCOS_DATA__.projects || [];
                    updateStats();
                    renderProjects();
                }};
                // Run immediately since data is already available
                allProjects = window.__BCOS_DATA__.projects || [];
                updateStats();
                renderProjects();
            }} catch(e) {{
                console.error('BCOS data parse error:', e);
            }}
        }}
    }})();
    </script>
    """

    # Replace the async init fetch with embedded data
    new_html = re.sub(
        r"<script>\s*//\s*–\s*Init[\s\S]*?</script>",
        embedded_script,
        html
    )

    # Ensure dist dir
    OUT.parent.mkdir(parents=True, exist_ok=True)

    # Write output
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(new_html)

    size_kb = OUT.stat().st_size // 1024
    print(f"✅ Built: {OUT} ({size_kb} KB)")
    print(f"   Projects: {len(projects.get('projects', []))}")
    print(f"   Output is fully self-contained — no server needed!")


if __name__ == "__main__":
    build()
