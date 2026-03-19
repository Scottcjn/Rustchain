# Contributing to Rustchain

Welcome to the Rustchain project! We appreciate your interest in contributing to our blockchain implementation in Rust. This guide will help you get started and ensure smooth collaboration.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Code Style Guidelines](#code-style-guidelines)
- [Pull Request Process](#pull-request-process)
- [Bug Reports](#bug-reports)
- [Feature Requests](#feature-requests)
- [Documentation Improvements](#documentation-improvements)
- [Testing Requirements](#testing-requirements)
- [Community Guidelines](#community-guidelines)
- [RTC Bounty Program](#rtc-bounty-program)

## Getting Started

Before contributing, please:

1. Read our [Code of Conduct](CODE_OF_CONDUCT.md)
2. Check existing issues and pull requests to avoid duplicates
3. Join our community discussions
4. Familiarize yourself with the project structure and goals

### First-Time Contributors

Look for issues labeled with:
- `good first issue` - Perfect for newcomers
- `documentation` - Documentation improvements
- `easy bounty` - Small fixes with RTC rewards

## Development Setup

### Prerequisites

- Rust 1.70+ with Cargo
- Git
- Python 3.8+ (for Flask components)
- Node.js 16+ (for frontend tooling)

### Local Setup

1. **Fork and Clone**
   ```bash
   git clone https://github.com/yourusername/Rustchain.git
   cd Rustchain
   ```

2. **Install Rust Dependencies**
   ```bash
   cargo build
   ```

3. **Install Python Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run Tests**
   ```bash
   cargo test
   python -m pytest
   ```

5. **Start Development Server**
   ```bash
   # Rust components
   cargo run
   
   # Flask app
   flask run
   ```

## Code Style Guidelines

### Rust Code

- Follow standard Rust formatting with `rustfmt`
- Use `clippy` for linting
- Include SPDX license header:
  ```rust
  // SPDX-License-Identifier: MIT
  ```
- Write comprehensive documentation
- Follow naming conventions:
  - `snake_case` for functions and variables
  - `PascalCase` for types and structs
  - `SCREAMING_SNAKE_CASE` for constants

### Python/Flask Code

- Follow PEP 8 style guidelines
- Use Flask patterns, NOT Django
- Include type hints where appropriate
- Write docstrings for functions and classes
- Keep route handlers simple and delegate to service layers

### General Guidelines

- Write clear, self-documenting code
- Include comments for complex logic
- Keep functions small and focused
- Use meaningful variable names
- Maintain consistent indentation (4 spaces)

## Pull Request Process

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Changes**
   - Write tests for new functionality
   - Update documentation as needed
   - Follow code style guidelines

3. **Test Locally**
   ```bash
   cargo test
   cargo clippy
   cargo fmt --check
   python -m pytest
   ```

4. **Commit Changes**
   ```bash
   git add .
   git commit -m "feat: add new blockchain validation logic"
   ```

5. **Push and Create PR**
   ```bash
   git push origin feature/your-feature-name
   ```

### PR Requirements

- [ ] Clear title and description
- [ ] Tests pass locally
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] No merge conflicts
- [ ] Linked to relevant issue

### Commit Message Format

Use conventional commits:
- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation changes
- `style:` - Code style changes
- `refactor:` - Code refactoring
- `test:` - Adding tests
- `chore:` - Maintenance tasks

## Bug Reports

When reporting bugs, include:

### Required Information
- **Environment**: OS, Rust version, Python version
- **Steps to Reproduce**: Clear, numbered steps
- **Expected Behavior**: What should happen
- **Actual Behavior**: What actually happens
- **Error Messages**: Full error text and stack traces
- **Screenshots**: If applicable

### Template
```markdown
**Environment:**
- OS: [e.g., Ubuntu 22.04]
- Rust version: [e.g., 1.70.0]
- Python version: [e.g., 3.10.0]

**Steps to Reproduce:**
1. Step one
2. Step two
3. Step three

**Expected Behavior:**
[Description]

**Actual Behavior:**
[Description]

**Error Messages:**
```
[Error text here]
```

**Additional Context:**
[Any other relevant information]
```

## Feature Requests

For new features:

1. **Check Existing Issues**: Avoid duplicates
2. **Describe Use Case**: Why is this needed?
3. **Provide Examples**: How would it work?
4. **Consider Impact**: Performance, security, complexity

### Template
```markdown
**Feature Summary:**
[Brief description]

**Use Case:**
[Why this feature is needed]

**Proposed Implementation:**
[How it might work]

**Alternatives Considered:**
[Other approaches you've thought about]

**Additional Context:**
[Any other relevant information]
```

## Documentation Improvements

We welcome documentation contributions:

### Types of Documentation
- **API Documentation**: Code comments and docstrings
- **User Guides**: How-to guides and tutorials
- **Architecture Docs**: Design decisions and system overview
- **README Updates**: Installation and usage instructions

### Documentation Standards
- Write in clear, simple language
- Include code examples
- Test all code examples
- Update table of contents
- Check for spelling and grammar

## Testing Requirements

### Test Coverage
- Unit tests for core functionality
- Integration tests for component interaction
- End-to-end tests for critical paths
- Performance tests for bottlenecks

### Running Tests
```bash
# Rust tests
cargo test

# Python tests
python -m pytest

# Coverage report
cargo tarpaulin --out html
pytest --cov=src
```

### Writing Tests
- Test both success and failure cases
- Use descriptive test names
- Keep tests focused and independent
- Mock external dependencies

## Community Guidelines

### Code of Conduct
- Be respectful and inclusive
- Welcome newcomers
- Provide constructive feedback
- Help others learn and grow

### Communication
- Use GitHub issues for bug reports and feature requests
- Join our Discord for real-time discussions
- Follow up on your contributions
- Be patient with review processes

### Recognition
Contributors are recognized through:
- Git commit history
- Contributor lists in documentation
- RTC bounty rewards
- Community shoutouts

## RTC Bounty Program

### How It Works
1. Look for issues labeled with `bounty` and RTC amounts
2. Complete the task and submit a PR
3. Comment on the issue with:
   - Link to your PR
   - Your wallet address for RTC payment
4. Receive payment after PR is merged

### Bounty Types
- **Easy Bounty (2 RTC)**: Typos, documentation fixes, small improvements
- **Medium Bounty (5-10 RTC)**: Bug fixes, small features
- **Large Bounty (20+ RTC)**: Major features, security improvements

### Bounty Rules
- Multiple claims allowed for different fixes
- Payment after PR approval and merge
- Quality standards still apply
- Communicate if you're working on a bounty

### Current Bounties
Check issues with the `bounty` label for:
- Documentation improvements
- Code cleanup
- Bug fixes
- Feature implementations

---

## Getting Help

- **GitHub Issues**: For bugs and feature requests
- **Discord**: Real-time chat and support
- **Documentation**: Check existing docs first
- **Code Review**: Learn from PR feedback

Thank you for contributing to Rustchain! Together, we're building the future of blockchain technology. 🚀