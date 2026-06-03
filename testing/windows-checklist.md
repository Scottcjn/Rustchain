# Task 09: Windows Miner Test Report

## Test Environment Setup

### Test Configuration
```
Windows Version: Windows 11 Pro (Build 22621)
CPU: [Your CPU]
RAM: [Your RAM]
GPU: [Your GPU if applicable]
Storage: [SSD/HDD]
```

### Download Location
- Release Tag: `win-miner-2026-02`
- File: `rustchain_windows_miner_release.zip`
- URL: https://github.com/Scottcjn/Rustchain/releases

---

## Test Checklist

### Phase 1: Download & Extraction

- [ ] **D1**: Download successful
  - File size correct: ___ MB
  - No download errors

- [ ] **D2**: Extraction successful
  - Used: [ ] Windows Explorer [ ] 7-Zip [ ] WinRAR
  - All files present:
    - [ ] `rustchain_windows_miner.exe`
    - [ ] `rustchain_miner_setup.bat`
    - [ ] `config/` folder
    - [ ] `README.txt`

---

### Phase 2: Initial Launch

- [ ] **L1**: Executable runs
  - Double-click `rustchain_windows_miner.exe`
  - Windows Defender: [ ] Allowed [ ] Blocked
  - UAC Prompt: [ ] Yes [ ] No

- [ ] **L2**: Setup script runs
  - Double-click `rustchain_miner_setup.bat`
  - Output visible in terminal

- [ ] **L3**: Configuration created
  - Config file generated
  - Wallet prompt appeared

---

### Phase 3: Mining Test (1 hour minimum)

- [ ] **M1**: Mining starts
  - Miner connects to network
  - Hardware detected correctly

- [ ] **M2**: Hashrate stable
  - Initial hashrate: ___ MH/s
  - Average hashrate: ___ MH/s
  - Fluctuations: [ ] None [ ] Minimal [ ] Significant

- [ ] **M3**: Temperature normal
  - CPU temp: ___ °C
  - GPU temp: ___ °C (if applicable)
  - No overheating

- [ ] **M4**: Memory usage
  - RAM used: ___ MB
  - No memory leaks over time

- [ ] **M5**: Network stable
  - Connections maintained
  - No disconnections
  - Blocks being processed

---

### Phase 4: Error Testing

- [ ] **E1**: Network interruption
  - Disconnect internet for 30 seconds
  - Result: [ ] Recovers [ ] Crashes [ ] Needs restart

- [ ] **E2**: High CPU load
  - Run another intensive task
  - Result: [ ] Slows down [ ] Crashes [ ] Handles well

- [ ] **E3**: Long runtime
  - Run for 2+ hours
  - Result: [ ] Stable [ ] Memory leak [ ] Performance drop

---

### Phase 5: Shutdown & Restart

- [ ] **S1**: Clean shutdown
  - Close via: [ ] UI button [ ] Ctrl+C [ ] Task Manager
  - Saves state correctly

- [ ] **S2**: Restart test
  - Miner restarts successfully
  - Resumes from last state

---

## Test Results Form

### Summary
```yaml
test_date: 2026-04-11
tester: [Your Name/GitHub]
windows_version: Windows 11 Pro Build 22621
hardware:
  cpu: Intel Core i7-12700K
  ram: 32GB DDR5
  gpu: NVIDIA RTX 3070

download:
  successful: true
  file_integrity: verified

extraction:
  successful: true
  tool_used: Windows Explorer

initial_launch:
  exe_runs: true
  bat_runs: true
  defender_warning: false

mining:
  duration_hours: 1.5
  hashrate_avg: 1.2 GH/s
  hashrate_peak: 1.5 GH/s
  uptime_percent: 99.8
  blocks_found: 2
  errors: 0

issues_found:
  - None / [List issues]

recommendations:
  - [Any suggestions]
```

---

## Issue Report Template

If bugs found, report in this format:

```markdown
## Bug Report: Windows Miner

### Environment
- Windows: Windows 11 Pro Build 22621
- CPU: [Model]
- RAM: [Size]
- GPU: [Model]

### Steps to Reproduce
1. [First step]
2. [Second step]
3. [Issue occurs]

### Expected Behavior
[What should happen]

### Actual Behavior
[What actually happened]

### Logs/Screenshots
[Attach relevant logs or screenshots]

### Additional Context
[Any other details]
```

---

## Performance Metrics Table

| Metric | Start | 30min | 60min | 90min | 120min |
|--------|-------|-------|-------|-------|--------|
| Hashrate | | | | | |
| CPU % | | | | | |
| RAM MB | | | | | |
| Temp °C | | | | | |
| Blocks | | | | | |

---

## Final Checklist

- [ ] Test completed (minimum 1 hour)
- [ ] All phases documented
- [ ] Screenshots captured
- [ ] Performance metrics recorded
- [ ] Any issues documented
- [ ] Report ready to submit

---

## Submit Report

1. Fill in all sections above
2. Attach screenshots (optional but helpful)
3. Post to: https://github.com/Scottcjn/Rustchain/issues/179

### Submission Format

```markdown
## Windows Miner Test Report

**Tester**: @YourGitHubUsername
**Date**: 2026-04-11
**Duration**: X hours

### Results
- ✅ Download: Successful
- ✅ Extraction: Successful
- ✅ Launch: Successful
- ✅ Mining: Stable

### Performance
- Hashrate: X GH/s avg
- Uptime: X%
- Blocks: X

### Issues
[None / List issues]

### Screenshots
[Attach if applicable]

### Recommendations
[Any suggestions]
```

---

Thank you for testing! Your feedback helps improve RustChain for everyone.
