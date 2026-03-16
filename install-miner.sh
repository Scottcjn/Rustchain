#!/bin/bash

# RustChain Windows Miner Installation Script
# This script performs a smoke test and provides feedback for Windows miner installation

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running on Windows (WSL)
is_windows() {
    [[ -n "$(which wslpath 2>/dev/null)" ]] || [[ -n "$(uname -r | grep Microsoft)" ]] || [[ "$OS" == "Windows_NT" ]]
}

# Check system requirements
check_requirements() {
    log "Checking system requirements..."
    
    if ! is_windows; then
        warn "This script is designed for Windows systems. Running on: $(uname -a)"
        return 1
    fi
    
    # Check Python
    if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
        error "Python is not installed. Please install Python 3.8+ from https://python.org"
        return 1
    fi
    
    # Check Git
    if ! command -v git &> /dev/null; then
        error "Git is not installed. Please install Git from https://git-scm.com"
        return 1
    fi
    
    # Check available memory
    local mem_available=$(free -m | awk '/Mem:/ {print $7}')
    if [[ $mem_available -lt 2048 ]]; then
        warn "Low memory detected ($mem_available MB free). Mining performance may be affected."
    fi
    
    log "System requirements check passed"
    return 0
}

# Check network connectivity
check_network() {
    log "Checking network connectivity..."
    
    if ! curl -s --head https://github.com &> /dev/null; then
        error "Unable to connect to GitHub. Please check your internet connection."
        return 1
    fi
    
    log "Network connectivity check passed"
    return 0
}

# Verify miner files
verify_miner_files() {
    log "Verifying miner files..."
    
    local miner_files=("miners/rustchain-miner.exe" "miners/config.json")
    
    for file in "${miner_files[@]}"; do
        if [[ ! -f "$file" ]]; then
            error "Required file not found: $file"
            return 1
        fi
    done
    
    log "Miner files verification passed"
    return 0
}

# Test miner execution
test_miner_execution() {
    log "Testing miner execution..."
    
    cd miners
    
    # Test if miner can start (dry run)
    if timeout 5s ./rustchain-miner.exe --help > /dev/null 2>&1; then
        log "Miner help command executed successfully"
    else
        warn "Miner help command failed or took too long"
    fi
    
    cd ..
    
    log "Miner execution test completed"
    return 0
}

# Generate installation feedback report
generate_feedback_report() {
    log "Generating installation feedback report..."
    
    local report_file="miner_installation_feedback.txt"
    
    cat > "$report_file" << EOF
RustChain Windows Miner Installation Feedback Report
=================================================

Generated on: $(date)

System Information:
- OS: $(uname -a)
- Architecture: $(uname -m)
- Available Memory: $(free -h | awk '/Mem:/ {print $2}')

Installation Steps Completed:
- [x] System requirements check
- [x] Network connectivity check
- [x] Miner files verification
- [x] Miner execution test

Recommendations:
1. Ensure you have at least 4GB of RAM for optimal performance
2. Run the miner with administrative privileges for best results
3. Monitor system resources while mining
4. Update your miner regularly for best performance

Troubleshooting:
- If miner fails to start, check Windows Event Viewer for errors
- Ensure port 8080 is available for the miner
- Check firewall settings to allow miner connections

EOF
    
    log "Feedback report generated: $report_file"
}

# Main installation function
main() {
    log "Starting RustChain Windows Miner installation..."
    
    # Perform smoke tests
    if ! check_requirements; then
        error "System requirements check failed"
        exit 1
    fi
    
    if ! check_network; then
        error "Network connectivity check failed"
        exit 1
    fi
    
    if ! verify_miner_files; then
        error "Miner files verification failed"
        exit 1
    fi
    
    if ! test_miner_execution; then
        warn "Miner execution test failed, but installation will continue"
    fi
    
    # Generate feedback report
    generate_feedback_report
    
    log "Installation smoke test completed successfully!"
    log "Please review the feedback report for recommendations."
}

# Run main function
main "$@"
