# Contributing to Rustchain

Welcome to the Rustchain project! We're excited to have you contribute to our blockchain implementation in Python.

## Getting Started

### Prerequisites

- Python 3.8 or higher
- Flask framework
- SQLite3 (included with Python)
- Git

### Setup Instructions

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/yourusername/Rustchain.git
   cd Rustchain
   ```

3. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

4. Install dependencies:
   ```bash
   pip install flask requests hashlib
   ```

5. Run the application:
   ```bash
   python app.py
   ```

## Code Style and Standards

### Mandatory Coding Rules

- **Database**: Use raw `sqlite3` ONLY (NO SQLAlchemy, NO Django ORM)
- **Framework**: Use Flask patterns ONLY (NOT Django)
- **File Structure**: Flat file structure (files in root or `node/` directory)
- **Database Pattern**: Use `sqlite3.connect(DB_PATH)` context manager pattern
- **Templates**: Use `render_template_string` for inline HTML (NOT separate template files)
- **Headers**: Include `SPDX-License-Identifier: MIT` header in all code files
- **New Files**: PREFER creating new standalone `.py` files in root directory
- **Existing Files**: NEVER modify existing files - only add new ones

### Code Examples

#### Database Connection Pattern
```python
# SPDX-License-Identifier: MIT

import sqlite3

DB_PATH = "blockchain.db"

def get_blocks():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM blocks")
        return cursor.fetchall()
```

#### Flask Route Pattern
```python
from flask import Flask, render_template_string

app = Flask(__name__)

@app.route('/blocks')
def show_blocks():
    html_template = """
    <html>
        <body>
            <h1>Blockchain Blocks</h1>
            <!-- inline HTML here -->
        </body>
    </html>
    """
    return render_template_string(html_template)
```

### Style Guidelines

- Use 4 spaces for indentation (NOT tabs)
- End files with exactly one newline
- No trailing whitespace
- Keep comments brief and only where needed
- Use natural variable names with slight variations
- No docstrings for every function - only for public API methods
- Remove unused imports

## Pull Request Guidelines

### Before Submitting

1. Test your changes thoroughly
2. Ensure code follows the mandatory coding rules above
3. Reference existing patterns in `node/rustchain_v2_integrated_v2.2.1_rip200.py`
4. Run basic syntax checks

### PR Process

1. Create a feature branch from main:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes following the code style requirements

3. Commit with descriptive messages:
   ```bash
   git commit -m "Add new mining difficulty adjustment algorithm"
   ```

4. Push to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

5. Open a Pull Request with:
   - Clear description of changes
   - Reference to any related issues
   - Screenshots if UI changes involved

### PR Requirements

- All new code files must include MIT license header
- Use Flask patterns exclusively
- Database interactions must use raw sqlite3
- No modifications to existing files (create new ones instead)
- Follow flat file structure convention

## Bounty System

### Current Bounties

We offer RTC (Rustchain Token) bounties for contributions:

- **EASY BOUNTY (1 RTC)**: Documentation, simple features, bug fixes
- **MEDIUM BOUNTY (5 RTC)**: New features, performance improvements
- **HARD BOUNTY (10 RTC)**: Core blockchain functionality, security enhancements

### Bounty Guidelines

1. Check existing issues tagged with `bounty`
2. Comment on the issue to claim it
3. Submit PR within reasonable timeframe
4. PR must be approved and merged to receive bounty
5. One bounty per person per issue

## Issue Guidelines

### Reporting Bugs

Include:
- Python version
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Error messages or logs

### Feature Requests

Include:
- Clear description of the feature
- Use case or problem it solves
- Proposed implementation approach
- Any breaking changes

### Issue Labels

- `bounty` - Issues with RTC rewards
- `easy` - Good for beginners
- `documentation` - Documentation related
- `bug` - Something isn't working
- `enhancement` - New feature or improvement
- `blockchain` - Core blockchain functionality
- `mining` - Mining related features
- `network` - P2P networking features

## Development Tips

1. Study the existing codebase in `node/` directory
2. Test with multiple nodes when working on networking features
3. Use the built-in blockchain explorer for debugging
4. Maintain backward compatibility when possible
5. Consider security implications for blockchain-related changes

## Community

- Be respectful and constructive in all interactions
- Help other contributors when possible
- Share knowledge and explain your implementations
- Follow the code of conduct

## Questions?

Feel free to open an issue with the `question` label or reach out to the maintainers.

Thank you for contributing to Rustchain!
