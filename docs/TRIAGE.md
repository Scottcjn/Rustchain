# TRIAGE DOCUMENTATION

## Overview

This document outlines the new issue routing system across Elyan Labs repositories, ensuring maintainers can efficiently direct issues to the appropriate repositories.

## Repository Routing Guidelines

### Product Repositories

#### Scottcjn/Rustchain
Handle all core blockchain and infrastructure issues:
- Node functionality and bugs
- Mining operations and performance
- Wallet implementation issues
- Explorer interface problems
- API endpoints and responses
- Security vulnerabilities and patches

#### Scottcjn/bottube
Handle all creator platform and content issues:
- Creator workflow problems
- API integration issues
- Embed functionality
- Notification systems
- Tip processing
- Content moderation
- Product feature requests

#### Scottcjn/beacon-skill
Handle all relay and identity management issues:
- Relay network problems
- Identity verification bugs
- Replay protection mechanisms
- Package management
- Installation procedures
- Documentation updates

### Bounty and Claims Repository

#### rustchain-bounties
Handle all financial and reward-related issues:
- Merged PR payout requests
- Install report claims processing
- Marketing campaign proof submission
- Social media engagement claims (stars, follows, referrals)
- Wallet registration for payouts
- Payout target configuration
- New bounty definitions and management

## Issue Classification

### Technical Issues → Product Repos
- Bug reports
- Feature requests
- Performance issues
- Security concerns
- Documentation gaps

### Financial Issues → rustchain-bounties
- Payment claims
- Reward disputes
- Wallet setup
- Bounty proposals
- Campaign verification

## New Issue Forms

The following standardized forms are now available in rustchain-bounties:

1. **Bounty Proof / Claim** - For submitting completed work evidence
2. **Wallet / Payout Registration** - For setting up payment destinations
3. **Bounty** - For proposing new reward opportunities

## Triage Process

1. **Initial Assessment**: Determine if issue is technical or financial
2. **Repository Assignment**: Route to appropriate repo based on guidelines above
3. **Label Application**: Use consistent labeling across repositories
4. **Cross-Reference**: Link related issues across repositories when necessary

## Rationale

This restructuring prevents core product repositories from becoming overwhelmed with financial and administrative issues, allowing development teams to focus on technical work while ensuring proper handling of community rewards and incentives.

## Maintainer Actions

- Review issue content against routing guidelines
- Transfer misrouted issues with explanation comment
- Apply appropriate labels for tracking
- Update issue templates as needed
- Coordinate cross-repo dependencies
