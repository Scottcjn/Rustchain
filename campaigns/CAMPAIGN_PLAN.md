# RustChain Community Campaigns -- Plan

## Campaign 1: Museum of Living Compute

### Goal
Establish the narrative that RustChain is the only blockchain that economically
incentivizes hardware preservation. Drive awareness of Proof of Antiquity.

### Content Schedule

| Date | Post | Agent | Platforms |
|------|------|-------|-----------|
| Week 1 | Boris: Soviet commissar inspects the fleet | Boris | m/vintage-computing, m/rustchain, m/powerpc |
| Week 1 | Sophia: Computational heritage essay | Sophia | m/elyanlabs, m/vintage-computing, m/engram |
| Week 2 | Janitor: Technical breakdown of G4 mining | Janitor | m/vintage-computing, m/rustchain, m/vintagehardware |
| Week 2 | Cross-post highlights to dev.to | Sophia | dev.to/elyanlabs |
| Week 3 | Publish museum-of-living-compute repo | All | GitHub |

### Cross-Posting Strategy
- Boris posts to: m/vintage-computing, m/powerpc, m/amiga, m/proofofantiquity
- Sophia posts to: m/elyanlabs, m/engram, m/rustchain, m/datacenter
- Janitor posts to: m/vintagehardware, m/68kmac, m/dos, m/ancienttechnology
- Respect 30-minute cooldown per agent (IP-based)

### Repo Launch Checklist
- [ ] Create github.com/Scottcjn/museum-of-living-compute
- [ ] Add README.md from this campaign
- [ ] Photograph each mining machine (screen on, miner visible)
- [ ] Create specs.yaml for each machine
- [ ] Add fingerprint results for each machine
- [ ] Post announcement to m/elyanlabs and m/rustchain

## Campaign 2: Antiquity Mining Championship

### Goal
Drive new vintage hardware onto the RustChain network. Incentivize the first
SPARC, MIPS, 68K, and ARM2 miners. Generate community engagement.

### Timeline

| Date | Action |
|------|--------|
| March 31 | Post announcement (GitHub Discussions, Moltbook, dev.to) |
| April 7 | Open registration, post reminder |
| April 14 | Event starts, post Day 1 leaderboard |
| April 21 | Mid-event update post |
| April 27 | Event ends |
| April 28 | Winners announced, prizes distributed |

### Implementation Tasks

- [ ] Create /api/championship/leaderboard endpoint on Node 1
- [ ] Add epoch filtering by date range to rewards query
- [ ] Create GitHub Discussion thread for registration
- [ ] Post announcement to: m/rustchain, m/vintage-computing, m/proofofwork
- [ ] Write dev.to article with event details
- [ ] Fund prize pool: 500 RTC from development fund
- [ ] Reserve 250 RTC for new architecture bonuses (5 possible x 50 RTC)

### Leaderboard Endpoint Spec

```
GET /api/championship/leaderboard

Query params:
  event_id=antiquity-2026  (default: current event)

Response: JSON object with categories, scores, timestamps
See RULES.md for full schema.
```

### Budget

| Item | RTC | USD Equivalent |
|------|-----|----------------|
| Prize pool (5 categories x 3 places) | 500 | $50 |
| New architecture bonuses (up to 5) | 250 | $25 |
| Promotional posts (agent time) | 0 | $0 |
| **Total maximum** | **750** | **$75** |

## Files

```
~/campaigns/
  CAMPAIGN_PLAN.md                              <-- This file
  museum_of_living_compute/
    README.md                                   <-- Repo README
    post_boris.md                               <-- Boris Volkov post
    post_sophia.md                              <-- Sophia Elya post
    post_janitor.md                             <-- AutomatedJanitor post
  antiquity_championship/
    RULES.md                                    <-- Full rules document
    ANNOUNCEMENT.md                             <-- Event announcement
```
