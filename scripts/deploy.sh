#!/bin/bash

# Heimdall Battery Sentinel Deployment Script
# Deploys the integration to Home Assistant via rsync

set -e  # Exit on error

# Configuration
REMOTE_USER="root"
REMOTE_HOST="homeassistant"
REMOTE_PORT="2222"
REMOTE_PATH="/root/homeassistant/custom_components"
LOCAL_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/custom_components/heimdall_battery_sentinel"

# Optional: Set a long-lived access token here or in ~/.config/ha_token
# Get token from: Home Assistant → Profile → Long-Lived Access Tokens
# HA_TOKEN="your_token_here"
if [ -z "$HA_TOKEN" ] && [ -f ~/.config/ha_token ]; then
    HA_TOKEN=$(cat ~/.config/ha_token)
fi

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Parse command line arguments
RESTART=false
while [[ $# -gt 0 ]]; do
    case $1 in
        -r|--restart)
            RESTART=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -r, --restart    Restart HA and reinstall integration after upload"
            echo "  -h, --help       Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0               Upload code only (fast)"
            echo "  $0 --restart     Upload code, restart HA, and reinstall integration"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# ============================================================================
# Functions
# ============================================================================

print_header() {
    echo -e "${GREEN}Heimdall Battery Sentinel Deployment${NC}"
    echo "====================================="
    echo ""
    echo "Local path:  ${LOCAL_PATH}"
    echo "Remote:      ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}"
    echo "Port:        ${REMOTE_PORT}"
    echo ""
}

check_prerequisites() {
    # Check if local directory exists
    if [ ! -d "${LOCAL_PATH}" ]; then
        echo -e "${RED}Error: Local directory not found: ${LOCAL_PATH}${NC}"
        exit 1
    fi

    # Check if rsync is available
    if ! command -v rsync &> /dev/null; then
        echo -e "${RED}Error: rsync is not installed${NC}"
        exit 1
    fi
}

upload_code() {
    echo "Step 1: Uploading new code..."
    rsync -avz \
        --delete \
        -e "ssh -p ${REMOTE_PORT}" \
        "${LOCAL_PATH}/" \
        "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/heimdall_battery_sentinel/"

    if [ $? -ne 0 ]; then
        echo ""
        echo -e "${RED}✗ Upload failed${NC}"
        exit 1
    fi

    echo -e "${GREEN}✓ Code uploaded${NC}"
    echo ""
}

unload_integration() {
    echo "Step 2: Unloading existing integration from Home Assistant..."

    if [ -n "$HA_TOKEN" ]; then
        ssh -p ${REMOTE_PORT} ${REMOTE_USER}@${REMOTE_HOST} \
            "python3 '${REMOTE_PATH}/heimdall_battery_sentinel/unload_integration.py' '${HA_TOKEN}'"

        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓ Integration unloaded from Home Assistant${NC}"
        else
            echo -e "${YELLOW}⚠ Could not unload integration (may not be installed or token invalid)${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ No HA_TOKEN configured, skipping unload step${NC}"
        echo "  To enable auto-unload:"
        echo "  1. Create long-lived token in HA: Profile → Long-Lived Access Tokens"
        echo "  2. Set HA_TOKEN in script or save to ~/.config/ha_token"
    fi
    echo ""
}

restart_homeassistant() {
    echo "Step 3: Restarting Home Assistant..."
    ssh -p ${REMOTE_PORT} ${REMOTE_USER}@${REMOTE_HOST} \
        "ha core restart" 2>/dev/null

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Home Assistant restart initiated${NC}"
    else
        echo -e "${YELLOW}⚠ Could not restart via 'ha' command, trying API...${NC}"

        if [ -n "$HA_TOKEN" ]; then
            curl -s -X POST "http://${REMOTE_HOST}:8123/api/services/homeassistant/restart" \
                -H "Authorization: Bearer ${HA_TOKEN}" \
                -H "Content-Type: application/json" \
                -o /dev/null -w '%{http_code}' | grep -q "200"

            if [ $? -eq 0 ]; then
                echo -e "${GREEN}✓ Home Assistant restart initiated via API${NC}"
            else
                echo -e "${RED}✗ Could not restart Home Assistant automatically${NC}"
                echo -e "${YELLOW}Please manually restart Home Assistant${NC}"
            fi
        else
            echo -e "${RED}✗ Could not restart (no token available)${NC}"
            echo -e "${YELLOW}Please manually restart Home Assistant${NC}"
        fi
    fi
    echo ""
}

wait_for_homeassistant() {
    echo "Step 4: Ensuring HA is responding..."
    local WAIT_START=$(date +%s)
    local TIMEOUT=300  # 5 minutes
    local HA_ONLINE=false

    while [ $(($(date +%s) - WAIT_START)) -lt $TIMEOUT ]; do
        # Try to ping the API
        if curl -s -o /dev/null -w '%{http_code}' \
                -H "Authorization: Bearer ${HA_TOKEN}" \
                -H "Content-Type: application/json" \
                "http://${REMOTE_HOST}:8123/api/" 2>/dev/null | grep -q "200"; then
            HA_ONLINE=true
            break
        fi
        echo -n "."
        sleep 5
    done

    echo ""

    if [ "$HA_ONLINE" = true ]; then
        local ELAPSED=$(($(date +%s) - WAIT_START))
        echo -e "${GREEN}✓ Home Assistant is back online (${ELAPSED}s)${NC}"
    else
        echo -e "${RED}✗ Timeout waiting for Home Assistant (5 minutes)${NC}"
        echo -e "${YELLOW}Home Assistant may still be restarting. Check manually.${NC}"
        exit 1
    fi
    echo ""
}

setup_integration() {
    echo "Step 5: Setting up Heimdall integration..."

    if [ -n "$HA_TOKEN" ]; then
        ssh -p ${REMOTE_PORT} ${REMOTE_USER}@${REMOTE_HOST} \
            "python3 ${REMOTE_PATH}/heimdall_battery_sentinel/setup_integration.py '${HA_TOKEN}'"

        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓ Integration set up successfully${NC}"
        else
            echo -e "${RED}✗ Failed to set up integration${NC}"
            echo -e "${YELLOW}You can manually add it via Settings → Devices & Services${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ No HA_TOKEN configured, skipping setup${NC}"
        echo "  Please manually add the integration via Settings → Devices & Services"
    fi

    echo ""
    echo -e "${GREEN}✓ Deployment complete!${NC}"
    echo ""
    echo "Heimdall stands watch over your batteries."
    echo "Check the sidebar for the Heimdall panel."
    echo ""
}

# ============================================================================
# Main Execution
# ============================================================================

main() {
    print_header
    check_prerequisites

    if [ "$RESTART" = true ]; then
        echo -e "${YELLOW}Starting full deployment (with restart)...${NC}"
    else
        echo -e "${YELLOW}Starting fast deployment (upload only)...${NC}"
    fi
    echo ""

    upload_code

    if [ "$RESTART" = true ]; then
        unload_integration
        restart_homeassistant
        wait_for_homeassistant
        setup_integration
    else
        echo ""
        echo -e "${GREEN}✓ Fast deployment complete!${NC}"
        echo ""
        echo "Code uploaded. Home Assistant will load changes on next restart."
        echo "To deploy with restart, use: $0 --restart"
        echo ""
    fi
}

# Run main function
main
