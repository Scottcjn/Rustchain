# RustChain Release Checklist

## Pre-Release Verification

- [ ] All tests pass: `pytest tests/ -v`
- [ ] Test coverage >= 80%: `pytest tests/ --cov=rustchain --cov-report=term-missing`
- [ ] Type checking passes: `mypy rustchain/`
- [ ] Code formatting: `black rustchain/`
- [ ] Version updated in `setup.py` and `pyproject.toml`
- [ ] CHANGELOG updated with release notes
- [ ] README.md reflects current functionality

## Build Package

```bash
cd sdk/

# Clean previous builds
rm -rf build/ dist/ *.egg-info

# Build source distribution and wheel
python -m build

# Verify package contents
twine check dist/*
```

## TestPyPI Verification

```bash
# Upload to TestPyPI
twine upload --repository testpypi dist/*

# Create a fresh virtual environment for testing
python -m venv /tmp/rustchain-test
source /tmp/rustchain-test/bin/activate

# Install from TestPyPI
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple rustchain

# Verify installation
python -c "import rustchain; print(rustchain.__version__)"

# Test basic functionality
python -c "from rustchain import RustChainClient, AsyncRustChainClient; print('Sync and async clients imported successfully')"

# Deactivate test environment
deactivate
```

## PyPI Release

```bash
# Upload to PyPI
twine upload dist/*

# Verify on PyPI
# Visit: https://pypi.org/project/rustchain/
```

## Post-Release

- [ ] Verify package on PyPI: https://pypi.org/project/rustchain/
- [ ] Test installation: `pip install rustchain`
- [ ] Update GitHub release with changelog
- [ ] Notify community via announcement channels

## Troubleshooting

### Package name conflict
If you see "This filename has already been used", increment the version number in `setup.py` and `pyproject.toml`.

### Missing files in distribution
Check `MANIFEST.in` includes all necessary files.

### TestPyPI authentication
Ensure `~/.pypirc` contains:
```ini
[testpypi]
  username = __token__
  password = pypi-...
```

### PyPI authentication
Ensure `~/.pypirc` contains:
```ini
[pypi]
  username = __token__
  password = pypi-...
```

## Quick Commands Reference

| Command | Description |
|---------|-------------|
| `python -m build` | Build source and wheel distributions |
| `twine check dist/*` | Validate package metadata |
| `twine upload --repository testpypi dist/*` | Upload to TestPyPI |
| `twine upload dist/*` | Upload to PyPI |
| `pip install rustchain` | Install from PyPI |
| `pip install --index-url https://test.pypi.org/simple/ rustchain` | Install from TestPyPI |
