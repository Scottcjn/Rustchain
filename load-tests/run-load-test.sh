#!/bin/bash
#
# RustChain API Load Test Runner
# 
# Usage:
#   ./run-load-test.sh [k6|locust] [scenario]
#
# Examples:
#   ./run-load-test.sh k6 smoke
#   ./run-load-test.sh k6 load
#   ./run-load-test.sh locust --headless
#

set -e

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Defaults
TARGET_URL="${TARGET_URL:-https://rustchain.org}"
MINER_ID="${MINER_ID:-scott}"
DURATION="${DURATION:-5m}"
USERS="${USERS:-10}"
SPAWN_RATE="${SPAWN_RATE:-2}"
OUTPUT_DIR="${OUTPUT_DIR:-./results}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}============================================================${NC}"
    echo -e "${BLUE}  RustChain API Load Test${NC}"
    echo -e "${BLUE}============================================================${NC}"
    echo ""
}

print_config() {
    echo -e "${YELLOW}Configuration:${NC}"
    echo "  Target URL:  ${TARGET_URL}"
    echo "  Miner ID:    ${MINER_ID}"
    echo "  Duration:    ${DURATION}"
    echo "  Users:       ${USERS}"
    echo "  Spawn Rate:  ${SPAWN_RATE}"
    echo "  Output Dir:  ${OUTPUT_DIR}"
    echo ""
}

setup_output_dir() {
    mkdir -p "${OUTPUT_DIR}"
    echo -e "${GREEN}Output directory ready: ${OUTPUT_DIR}${NC}"
}

run_k6() {
    local scenario="${1:-load}"
    
    echo -e "${GREEN}Running k6 load test (scenario: ${scenario})...${NC}"
    echo ""
    
    # Check if k6 is installed
    if ! command -v k6 &> /dev/null; then
        echo -e "${RED}Error: k6 is not installed.${NC}"
        echo "Install k6: https://k6.io/docs/getting-started/installation/"
        echo ""
        echo "macOS:     brew install k6"
        echo "Linux:     sudo apt-get install k6"
        echo "Windows:   winget install k6"
        exit 1
    fi
    
    # Create timestamp for results
    local timestamp=$(date +%Y%m%d_%H%M%S)
    
    case "${scenario}" in
        smoke)
            k6 run \
                --out json="${OUTPUT_DIR}/k6-smoke-${timestamp}.json" \
                -e TARGET_URL="${TARGET_URL}" \
                -e MINER_ID="${MINER_ID}" \
                k6-load-test.js
            ;;
        load)
            k6 run \
                --config k6-config.json \
                --out json="${OUTPUT_DIR}/k6-load-${timestamp}.json" \
                -e TARGET_URL="${TARGET_URL}" \
                -e MINER_ID="${MINER_ID}" \
                k6-load-test.js
            ;;
        stress)
            k6 run \
                --config k6-config.json \
                --out json="${OUTPUT_DIR}/k6-stress-${timestamp}.json" \
                -e TARGET_URL="${TARGET_URL}" \
                -e MINER_ID="${MINER_ID}" \
                k6-load-test.js
            ;;
        quick-smoke)
            k6 run \
                --config k6-scenarios.json \
                --scenario quick-smoke \
                --out json="${OUTPUT_DIR}/k6-quick-smoke-${timestamp}.json" \
                -e TARGET_URL="${TARGET_URL}" \
                -e MINER_ID="${MINER_ID}" \
                k6-load-test.js
            ;;
        api-baseline)
            k6 run \
                --config k6-scenarios.json \
                --scenario api-baseline \
                --out json="${OUTPUT_DIR}/k6-baseline-${timestamp}.json" \
                -e TARGET_URL="${TARGET_URL}" \
                -e MINER_ID="${MINER_ID}" \
                k6-load-test.js
            ;;
        soak-test)
            k6 run \
                --config k6-scenarios.json \
                --scenario soak-test \
                --out json="${OUTPUT_DIR}/k6-soak-${timestamp}.json" \
                -e TARGET_URL="${TARGET_URL}" \
                -e MINER_ID="${MINER_ID}" \
                k6-load-test.js
            ;;
        spike-test)
            k6 run \
                --config k6-scenarios.json \
                --scenario spike-test \
                --out json="${OUTPUT_DIR}/k6-spike-${timestamp}.json" \
                -e TARGET_URL="${TARGET_URL}" \
                -e MINER_ID="${MINER_ID}" \
                k6-load-test.js
            ;;
        *)
            echo -e "${RED}Unknown scenario: ${scenario}${NC}"
            echo "Available scenarios: smoke, load, stress, quick-smoke, api-baseline, soak-test, spike-test"
            exit 1
            ;;
    esac
    
    echo ""
    echo -e "${GREEN}k6 test complete!${NC}"
    echo "Results saved to: ${OUTPUT_DIR}/"
}

run_locust() {
    local mode="${1:---headless}"
    
    echo -e "${GREEN}Running Locust load test (mode: ${mode})...${NC}"
    echo ""
    
    # Check if locust is installed
    if ! command -v locust &> /dev/null; then
        echo -e "${RED}Error: Locust is not installed.${NC}"
        echo "Install with: pip install -r locust-requirements.txt"
        exit 1
    fi
    
    # Create timestamp for results
    local timestamp=$(date +%Y%m%d_%H%M%S)
    
    if [ "${mode}" = "web" ] || [ "${mode}" = "--web" ]; then
        # Web UI mode
        locust \
            -f locust-load-test.py \
            --host="${TARGET_URL}" \
            --web-host=127.0.0.1 \
            --web-port=8089
    else
        # Headless mode
        locust \
            -f locust-load-test.py \
            --host="${TARGET_URL}" \
            --headless \
            -u "${USERS}" \
            -r "${SPAWN_RATE}" \
            --run-time="${DURATION}" \
            --html="${OUTPUT_DIR}/locust-report-${timestamp}.html" \
            --json="${OUTPUT_DIR}/locust-results-${timestamp}.json"
    fi
    
    echo ""
    echo -e "${GREEN}Locust test complete!${NC}"
    echo "Results saved to: ${OUTPUT_DIR}/"
}

show_help() {
    echo "RustChain API Load Test Runner"
    echo ""
    echo "Usage: $0 [tool] [options]"
    echo ""
    echo "Tools:"
    echo "  k6       - Run k6 load tests"
    echo "  locust   - Run Locust load tests"
    echo "  help     - Show this help message"
    echo ""
    echo "K6 Scenarios:"
    echo "  smoke      - Quick 30s smoke test"
    echo "  load       - Standard load test (5m)"
    echo "  stress     - Stress test with peak load"
    echo "  quick-smoke - Very quick CI/CD test"
    echo "  api-baseline - Baseline performance test"
    echo "  soak-test  - Long-running endurance test"
    echo "  spike-test - Sudden load spike test"
    echo ""
    echo "Locust Modes:"
    echo "  web        - Run with web UI (default port 8089)"
    echo "  headless   - Run without UI (default)"
    echo ""
    echo "Examples:"
    echo "  $0 k6 smoke"
    echo "  $0 k6 load"
    echo "  $0 k6 stress"
    echo "  $0 locust web"
    echo "  $0 locust headless"
    echo ""
    echo "Environment Variables:"
    echo "  TARGET_URL  - API base URL (default: https://rustchain.org)"
    echo "  MINER_ID    - Miner wallet ID (default: scott)"
    echo "  DURATION    - Test duration (default: 5m)"
    echo "  USERS       - Concurrent users for Locust (default: 10)"
    echo "  SPAWN_RATE  - User spawn rate for Locust (default: 2)"
    echo "  OUTPUT_DIR  - Results output directory (default: ./results)"
    echo ""
}

# Main
print_header

case "${1:-help}" in
    k6)
        setup_output_dir
        print_config
        run_k6 "${2:-load}"
        ;;
    locust)
        setup_output_dir
        print_config
        run_locust "${2:-headless}"
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}Unknown command: ${1}${NC}"
        echo ""
        show_help
        exit 1
        ;;
esac
