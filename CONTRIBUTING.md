# Contributing to RustChain

Thank you for your interest in contributing to RustChain! This document provides guidelines for contributing to the project.

## 🎯 Ways to Contribute

### Code Contributions
- **Bug fixes**: Find and fix issues in the codebase
- **Features**: Implement new features or improvements
- **Documentation**: Improve or add documentation
- **Tests**: Add test coverage for existing code
- **Refactoring**: Improve code quality and maintainability

### Non-Code Contributions
- **Bug reports**: Report issues you encounter
- **Feature requests**: Suggest new features or improvements
- **Documentation feedback**: Help improve the documentation
- **Community support**: Help others in issues and discussions

## 🏆 Bounty Program

RustChain offers bounties for contributions! Check out:
- [Open bounty issues](https://github.com/Scottcjn/Rustchain/labels/bounty)
- [First contribution bounty](https://github.com/Scottcjn/Rustchain/issues/48) - Earn 10 RTC for your first merged PR!

## 🚀 Getting Started

### 1. Fork and Clone
```bash
# Fork the repository on GitHub, then:
git clone https://github.com/YOUR_USERNAME/Rustchain.git
cd Rustchain
```

### 2. Create a Branch
```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

### 3. Make Your Changes
- Follow the existing code style
- Add comments for complex logic
- Update documentation if needed
- Test your changes against the live network

### 4. Test Your Changes
```bash
# Test against the live network
curl -sk https://50.28.86.131/health

# For miner changes, test with:
python3 miners/linux/rustchain_linux_miner.py --wallet test-wallet --dry-run
```

### 5. Commit Your Changes
```bash
git add .
git commit -m "type: brief description of changes"
```

**Commit message format:**
- `feat:` for new features
- `fix:` for bug fixes
- `docs:` for documentation changes
- `refactor:` for code refactoring
- `test:` for adding tests
- `chore:` for maintenance tasks

### 6. Push and Create PR
```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub with:
- **Clear title** describing the change
- **Description** explaining what and why
- **Reference** to any related issues (e.g., "Closes #123")
- **Testing evidence** if applicable

## 📋 Code Guidelines

### Python Code Style
- Follow [PEP 8](https://pep8.org/) style guidelines
- Use meaningful variable and function names
- Add docstrings to functions and classes
- Keep functions focused and small
- Handle errors gracefully

### Shell Scripts
- Use `#!/bin/bash` shebang
- Quote variables: `"$variable"`
- Check command success: `|| exit 1`
- Add comments for complex logic

### Documentation
- Use clear, concise language
- Include code examples where helpful
- Keep line length under 80-100 characters
- Use Markdown formatting consistently

## 🧪 Testing

### Manual Testing
Before submitting a PR:
1. **Test against live network**: Ensure your changes work with the production network
2. **Test edge cases**: Try unusual inputs and scenarios
3. **Cross-platform check**: Test on multiple platforms if possible (Linux, macOS)
4. **Documentation check**: Verify any documentation changes are accurate

### For Miner Changes
```bash
# Test miner runs without errors
python3 miners/linux/rustchain_linux_miner.py --wallet test --dry-run

# Verify API connectivity
curl -sk https://50.28.86.131/health
curl -sk https://50.28.86.131/epoch
```

## 📝 Pull Request Process

1. **One PR per feature/fix**: Keep PRs focused on a single change
2. **Small commits**: Break large changes into logical commits
3. **Update documentation**: Add or update docs for new features
4. **Resolve conflicts**: Rebase on latest `main` if needed
5. **Respond to feedback**: Address reviewer comments promptly

### PR Checklist
- [ ] Code follows project style guidelines
- [ ] Changes tested against live network
- [ ] Documentation updated (if applicable)
- [ ] Commit messages follow format guidelines
- [ ] No unnecessary files included (logs, cache, etc.)
- [ ] PR description is clear and complete

## 🔍 Code Review

### What to Expect
- Maintainers will review your PR within a few days
- You may be asked to make changes
- Be patient and respectful in discussions
- Reviews help improve code quality

### Common Review Feedback
- Code style issues
- Missing error handling
- Insufficient testing
- Documentation gaps
- Performance concerns

## 🌟 First-Time Contributors

Welcome! We're excited to have you. Here are some tips:

1. **Start small**: Pick a `good first issue` or make a small documentation improvement
2. **Ask questions**: Don't hesitate to ask for clarification in issues or PRs
3. **Read existing code**: Understand the patterns before making changes
4. **Be patient**: Learning a new codebase takes time

### Good First Issues
Look for issues labeled:
- [`good first issue`](https://github.com/Scottcjn/Rustchain/labels/good%20first%20issue)
- [`help wanted`](https://github.com/Scottcjn/Rustchain/labels/help%20wanted)
- [`documentation`](https://github.com/Scottcjn/Rustchain/labels/documentation)

## 💰 Claiming Bounties

### For Bounty Issues
1. **Check availability**: Ensure no one is already assigned
2. **Comment intent**: Let maintainers know you're working on it
3. **Follow requirements**: Meet all acceptance criteria
4. **Include wallet**: Add your RTC wallet address in the PR description

### Bounty Format in PR
```markdown
## Bounty Claim
- Issue: #XX
- RTC Wallet: your-wallet-name
```

## 📧 Questions?

- **GitHub Issues**: For bug reports and feature requests
- **GitHub Discussions**: For questions and general discussion
- **Pull Requests**: For code and documentation contributions

## 🙏 Thank You!

Every contribution, no matter how small, helps make RustChain better. We appreciate your time and effort!

---

**RTC Value**: 1 RTC ≈ $0.10 USD  
**Live Network**: https://50.28.86.131  
**Explorer**: https://rustchain.org/explorer
