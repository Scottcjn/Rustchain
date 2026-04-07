# PPA Attestation Visualizer
> Last updated: 2026-04-07
## Overview
The PPA Attestation Visualizer was developed to provide a graphical representation of hardware fingerprint data, enhancing the understanding of performance metrics derived from RustChain's PPA fingerprint. This feature allows users to visualize complex data in a more accessible format.
## How It Works
The visualizer processes JSON data from `fingerprint_checks.py` using the `parse_json_input()` function in `src/utils/data_processing.py`. It generates a radar chart through the `visualize_hardware_fingerprint()` function in `src/visualizations/visualizer.py`, which utilizes Matplotlib for rendering. The HTML file `src/visualizations/visualizer.html` integrates Chart.js to display the radar chart in a web interface.
## Configuration
No configuration required.
## Usage
To visualize the hardware fingerprint, ensure the JSON output from `fingerprint_checks.py` is available and navigate to the visualizer page in the application.
## References
- Closes issue #2148