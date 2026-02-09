# RustChain Contributing Guide

Welcome to RustChain! This guide will help you contribute to the project.

---

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Contribution Types](#contribution-types)
- [Code Guidelines](#code-guidelines)
- [Pull Request Process](#pull-request-process)
- [Testing](#testing)
- [Documentation](#documentation)
- [Bounties](#bounties)
- [Community](#community)

---

## Getting Started

### Prerequisites

- **Git**: Version control
- **Python 3.8+**: Primary development language
- **GitHub Account**: For pull requests
- **Basic blockchain knowledge**: Helpful but not required

### First Steps

1. **Fork the repository**:
   ```bash
   # Visit https://github.com/Scottcjn/Rustchain
   # Click "Fork" button
   ```

2. **Clone your fork**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/Rustchain.git
   cd Rustchain
   ```

3. **Add upstream remote**:
   ```bash
   git remote add upstream https://github.com/Scottcjn/Rustchain.git
   ```

4. **Create development branch**:
   ```bash
   git checkout -b feature/my-contribution
   ```

---

## Development Setup

### Install Dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# OR
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install pytest black flake8 mypy
```

### Run Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_miner.py

# Run with coverage
pytest --cov=node --cov-report=html
```

### Code Formatting

```bash
# Format code with Black
black miners/ node/ wallet/

# Check linting with flake8
flake8 miners/ node/ wallet/

# Type checking with mypy
mypy miners/ node/ wallet/
```

---

## Contribution Types

### 1. Bug Fixes

**Process**:
1. Check if bug is already reported in [Issues](https://github.com/Scottcjn/Rustchain/issues)
2. If not, create new issue with:
   - Clear description
   - Steps to reproduce
   - Expected vs actual behavior
   - System information
3. Fork repository and create branch: `fix/issue-123-description`
4. Fix bug and add test
5. Submit pull request

**Example**:
```bash
git checkout -b fix/issue-123-vm-detection
# Make changes
git commit -m "Fix VM detection on AMD CPUs (fixes #123)"
git push origin fix/issue-123-vm-detection
```

### 2. New Features

**Process**:
1. Discuss feature in [Discussions](https://github.com/Scottcjn/Rustchain/discussions)
2. Get approval from maintainers
3. Create feature branch: `feature/description`
4. Implement feature with tests
5. Update documentation
6. Submit pull request

**Example**:
```bash
git checkout -b feature/arm64-support
# Implement feature
git commit -m "Add ARM64 architecture support"
git push origin feature/arm64-support
```

### 3. Documentation

**Process**:
1. Identify documentation gap
2. Create branch: `docs/description`
3. Write or update documentation
4. Test all code examples
5. Submit pull request

**Example**:
```bash
git checkout -b docs/raspberry-pi-guide
# Write documentation
git commit -m "Add Raspberry Pi mining guide"
git push origin docs/raspberry-pi-guide
```

### 4. Platform Support

**Process**:
1. Test on new platform
2. Create platform-specific miner (if needed)
3. Update installation scripts
4. Document platform requirements
5. Submit pull request

**Platforms we'd love support for**:
- FreeBSD
- OpenBSD
- Solaris/illumos
- RISC-V
- ARM32
- MIPS

### 5. Hardware Support

**Process**:
1. Test on vintage hardware
2. Add hardware detection
3. Implement fingerprint checks
4. Calculate appropriate multiplier
5. Document hardware specs
6. Submit pull request

**Hardware we'd love support for**:
- SPARC (Sun/Oracle)
- Alpha (DEC)
- MIPS (SGI)
- PA-RISC (HP)
- Itanium (Intel)
- 68k (Motorola)

---

## Code Guidelines

### Python Style

**Follow PEP 8** with these specifics:

```python
# Line length: 100 characters (not 79)
# Use Black formatter for consistency

# Good
def calculate_multiplier(release_year: int, current_year: int = 2026) -> float:
    """Calculate antiquity multiplier based on hardware age.
    
    Args:
        release_year: Year hardware was released
        current_year: Current year (default: 2026)
    
    Returns:
        Multiplier value (0.8 - 3.5)
    """
    age = current_year - release_year
    
    if age >= 30:
        return 3.5  # Ancient
    elif age >= 25:
        return 3.0  # Sacred
    elif age >= 20:
        return 2.5  # Vintage
    # ... etc
    
    return 1.0  # Modern

# Bad
def calc_mult(y):
    a=2026-y
    if a>=30:return 3.5
    elif a>=25:return 3.0
    # ... etc
```

### Naming Conventions

```python
# Variables and functions: snake_case
miner_id = "powerbook_g4_RTC"
def get_balance(wallet_id):
    pass

# Classes: PascalCase
class RustChainClient:
    pass

# Constants: UPPER_SNAKE_CASE
BLOCK_TIME = 600
NODE_URL = "https://50.28.86.131"

# Private methods: _leading_underscore
def _internal_helper():
    pass
```

### Documentation

**All public functions must have docstrings**:

```python
def send_rtc(from_wallet: Dict, to_address: str, amount_rtc: float) -> Dict:
    """Send RTC to another wallet.
    
    Args:
        from_wallet: Wallet dict with private_key
        to_address: Recipient wallet ID
        amount_rtc: Amount to send (in RTC)
    
    Returns:
        {
            "ok": bool,
            "tx_hash": str,
            "new_balance_rtc": float
        }
    
    Raises:
        ValueError: If amount_rtc is negative
        InsufficientBalanceError: If balance too low
    
    Example:
        >>> wallet = load_wallet("my-wallet.enc", "password")
        >>> result = send_rtc(wallet, "recipient_RTC", 5.0)
        >>> print(result["tx_hash"])
        a1b2c3d4e5f6...
    """
    # Implementation
```

### Error Handling

```python
# Good: Specific exceptions
try:
    balance = get_balance(wallet_id)
except WalletNotFoundError:
    print(f"Wallet {wallet_id} not found")
except ConnectionError:
    print("Cannot connect to node")
except Exception as e:
    print(f"Unexpected error: {e}")

# Bad: Bare except
try:
    balance = get_balance(wallet_id)
except:
    print("Error")
```

### Type Hints

**Use type hints for all function signatures**:

```python
from typing import Dict, List, Optional, Tuple

def get_miners(limit: int = 100, offset: int = 0) -> Dict[str, any]:
    """Get list of miners."""
    pass

def calculate_rewards(miners: List[Dict], pot_rtc: float) -> Dict[str, float]:
    """Calculate reward distribution."""
    pass

def find_miner(miner_id: str) -> Optional[Dict]:
    """Find miner by ID. Returns None if not found."""
    pass
```

---

## Pull Request Process

### 1. Prepare Your Changes

```bash
# Sync with upstream
git fetch upstream
git rebase upstream/main

# Run tests
pytest

# Format code
black .

# Check linting
flake8 .
```

### 2. Commit Messages

**Format**:
```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting
- `refactor`: Code restructuring
- `test`: Adding tests
- `chore`: Maintenance

**Examples**:

```bash
# Good
git commit -m "feat(miner): Add ARM64 architecture support

Implements hardware fingerprinting for ARM64 CPUs including
Apple Silicon M1/M2/M3 and Raspberry Pi 4/5.

Closes #123"

# Good
git commit -m "fix(node): Fix database lock on concurrent attestations

Adds transaction isolation to prevent database locks when
multiple miners submit attestations simultaneously.

Fixes #456"

# Bad
git commit -m "fixed stuff"
git commit -m "update"
```

### 3. Create Pull Request

1. **Push to your fork**:
   ```bash
   git push origin feature/my-contribution
   ```

2. **Open pull request** on GitHub

3. **Fill out PR template**:
   ```markdown
   ## Description
   Brief description of changes
   
   ## Type of Change
   - [ ] Bug fix
   - [ ] New feature
   - [ ] Documentation
   - [ ] Breaking change
   
   ## Testing
   - [ ] All tests pass
   - [ ] Added new tests
   - [ ] Tested on: Ubuntu 22.04, macOS 13
   
   ## Checklist
   - [ ] Code follows style guidelines
   - [ ] Documentation updated
   - [ ] No breaking changes (or documented)
   
   ## Related Issues
   Closes #123
   ```

4. **Wait for review**

### 4. Address Review Comments

```bash
# Make requested changes
git add .
git commit -m "Address review comments"
git push origin feature/my-contribution
```

### 5. Merge

Once approved, maintainers will merge your PR. Thank you for contributing!

---

## Testing

### Unit Tests

**Location**: `tests/`

**Example**:
```python
# tests/test_miner.py
import pytest
from miners.linux.rustchain_linux_miner import calculate_multiplier

def test_calculate_multiplier_vintage():
    """Test multiplier for vintage hardware."""
    multiplier = calculate_multiplier(release_year=2005)
    assert multiplier == 2.5

def test_calculate_multiplier_modern():
    """Test multiplier for modern hardware."""
    multiplier = calculate_multiplier(release_year=2024)
    assert multiplier == 1.0

def test_calculate_multiplier_ancient():
    """Test multiplier for ancient hardware."""
    multiplier = calculate_multiplier(release_year=1995)
    assert multiplier == 3.5
```

### Integration Tests

```python
# tests/test_integration.py
import pytest
from rustchain_client import RustChainClient

@pytest.fixture
def client():
    return RustChainClient("https://50.28.86.131")

def test_health_check(client):
    """Test node health endpoint."""
    health = client.health()
    assert health["ok"] == True
    assert "version" in health

def test_balance_check(client):
    """Test balance query."""
    balance = client.get_balance("test_wallet_RTC")
    assert "balance_rtc" in balance
    assert balance["balance_rtc"] >= 0
```

### Running Tests

```bash
# All tests
pytest

# Specific test file
pytest tests/test_miner.py

# Specific test function
pytest tests/test_miner.py::test_calculate_multiplier_vintage

# With coverage
pytest --cov=miners --cov=node --cov=wallet

# Verbose output
pytest -v

# Stop on first failure
pytest -x
```

---

## Documentation

### Documentation Standards

**All documentation must**:
1. Include code examples
2. Test all commands before submitting
3. Use proper markdown formatting
4. Include screenshots (if GUI)
5. Be clear and concise

### Documentation Structure

```
docs/
├── API_REFERENCE.md          # All endpoints with examples
├── MINER_SETUP_GUIDE.md      # Step-by-step miner setup
├── PYTHON_SDK_TUTORIAL.md    # SDK usage examples
├── NODE_OPERATOR_GUIDE.md    # Running attestation node
├── WALLET_USER_GUIDE.md      # Wallet management
├── ARCHITECTURE_OVERVIEW.md  # System design
├── FAQ_TROUBLESHOOTING.md    # Common issues
└── CONTRIBUTING_GUIDE.md     # This file
```

### Testing Documentation

**Before submitting documentation**:

1. **Test all commands**:
   ```bash
   # Copy command from docs
   curl -sk https://50.28.86.131/health
   
   # Verify output matches documentation
   ```

2. **Test all code examples**:
   ```python
   # Copy code from docs
   from rustchain_client import RustChainClient
   client = RustChainClient()
   health = client.health()
   print(health)
   
   # Verify it works
   ```

3. **Check links**:
   ```bash
   # Verify all internal links work
   # Verify all external links are accessible
   ```

---

## Bounties

### Active Bounties

**Documentation Sprint**: 150 RTC (distributed across contributors)

| Document | Reward | Priority | Status |
|----------|--------|----------|--------|
| API Reference | 25 RTC | HIGH | ✅ Complete |
| Miner Setup Guide | 20 RTC | HIGH | ✅ Complete |
| Python SDK Tutorial | 15 RTC | HIGH | ✅ Complete |
| Node Operator Guide | 20 RTC | MEDIUM | ✅ Complete |
| Wallet User Guide | 15 RTC | MEDIUM | ✅ Complete |
| Architecture Overview | 20 RTC | MEDIUM | ✅ Complete |
| FAQ & Troubleshooting | 15 RTC | LOW | ✅ Complete |
| Contributing Guide | 10 RTC | LOW | ✅ Complete |

**Bonus**: Complete 3+ documents: +10 RTC

### Claiming Bounties

1. **Check bounty requirements** in `bounties/dev_bounties.json`
2. **Complete work** following guidelines
3. **Submit pull request** with:
   - All requirements met
   - Tests passing
   - Documentation updated
4. **Wait for review**
5. **Receive RTC** after merge

### Future Bounties

**Platform Support**:
- FreeBSD miner: 50 RTC
- OpenBSD miner: 50 RTC
- RISC-V support: 100 RTC

**Hardware Support**:
- SPARC fingerprinting: 75 RTC
- Alpha fingerprinting: 75 RTC
- MIPS fingerprinting: 75 RTC

**Features**:
- Mobile wallet (iOS/Android): 200 RTC
- Hardware wallet integration: 300 RTC
- Lightning Network integration: 500 RTC

---

## Community

### Communication Channels

- **GitHub Discussions**: General discussion, questions
- **GitHub Issues**: Bug reports, feature requests
- **Pull Requests**: Code contributions

### Code of Conduct

**Be respectful**:
- Treat everyone with respect
- Welcome newcomers
- Be patient with questions
- Provide constructive feedback

**Be collaborative**:
- Share knowledge
- Help others
- Review pull requests
- Participate in discussions

**Be professional**:
- No harassment
- No spam
- No off-topic discussions
- Follow project guidelines

### Recognition

**Contributors are recognized in**:
- `CONTRIBUTORS.md` file
- Release notes
- Project README
- NFT badges (for significant contributions)

---

## Getting Help

### Questions?

- **General questions**: [GitHub Discussions](https://github.com/Scottcjn/Rustchain/discussions)
- **Bug reports**: [GitHub Issues](https://github.com/Scottcjn/Rustchain/issues)
- **Documentation**: `docs/` directory

### Resources

- **API Reference**: `docs/API_REFERENCE.md`
- **Architecture**: `docs/ARCHITECTURE_OVERVIEW.md`
- **Protocol**: `docs/PROTOCOL.md`
- **Whitepaper**: `docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf`

---

## Thank You!

Thank you for contributing to RustChain! Every contribution helps preserve computing history and build a more sustainable blockchain.

**Your contributions matter!** 🎉

---

**Last Updated**: February 9, 2026  
**Guide Version**: 1.0
