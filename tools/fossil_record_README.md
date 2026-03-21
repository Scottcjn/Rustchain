# Fossil Record 鈥?Attestation Archaeology Visualizer

Interactive D3.js visualization of RustChain attestation history, rendered as geological strata by architecture family.

## Architecture

```
tools/
  fossil_record.py         # Flask API server
  static/
    fossil_timeline.html   # D3.js stratigraphy visualization
```

## Running

```bash
pip install flask requests
python tools/fossil_record.py --port 5002
```

Then open `http://localhost:5002` in your browser.

## API Endpoints

- `GET /` 鈥?Render the visualization
- `GET /api/timeline` 鈥?Get stratigraphy data
  - Query params: `start` (epoch), `end` (epoch), `limit`
- `GET /api/archs` 鈥?Get architecture summary
- `GET /api/epochs/<id>` 鈥?Get epoch detail

## Architecture Colors

| Family | Color | Era |
|--------|-------|-----|
| 68K | Deep Brown | 1990s |
| DEC Alpha | Gray Steel | 1990s |
| Itanium | Silver Gray | 2000s |
| PowerPC G4 | Amber/Gold | 2000s |
| PowerPC G5 | Copper | 2004-2006 |
| SPARC | Deep Blue | 1990s-2000s |
| POWER8 | Navy/Slate | 2013+ |
| ARM SBC | Pale Ice Blue | 2010s+ |
| RISC-V | Teal | 2015+ |
| x86/Modern | Pale Gray | All eras |

## Visualization

- X-axis: Epoch (time)
- Y-axis: Architecture family (oldest at bottom, newest at top)
- Block opacity: Attestation density
- Hover: Full attestation metadata