#!/bin/bash

# Docker Compose Test Script
# Tests if docker-compose.yml files can successfully build by calling docker-compose up
# and logs the results
#
# Usage: ./test_docker_apps.sh /path/to/app1 /path/to/app2 /path/to/app3

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
HOME_DIR=$(pwd)

LOG_FILE="$(pwd)/docker_test_results.log"
SUCCESS_FILE="$(pwd)/successful_apps.txt"
FAILED_FILE="$(pwd)/failed_apps.txt"

# Check if any arguments provided
if [ $# -eq 0 ]; then
    echo "Error: No directories provided"
    echo "Usage: $0 /path/to/app1 /path/to/app2 ..."
    echo "Example: $0 ~/apps/resto_api ~/apps/crypto-portfolio"
    exit 1
fi

# Clear previous results
> "$LOG_FILE"
> "$SUCCESS_FILE"
> "$FAILED_FILE"

echo "========================================" | tee -a "$LOG_FILE"
echo "Docker Compose Build Test" | tee -a "$LOG_FILE"
echo "Started: $(date)" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Counter variables
total=0
success=0
failed=0

# Function to test a directory
test_docker_compose() {
    local dir=$1
    local dir_name=$(basename "$dir")

    echo -e "${YELLOW}Testing: $dir_name${NC}" | tee -a "$LOG_FILE"
    echo "  Path: $dir" | tee -a "$LOG_FILE"

    # Check if directory exists
    if [ ! -d "$dir" ]; then
        echo -e "${RED}✗ $dir_name -> FAIL (directory does not exist)${NC}" | tee -a "$LOG_FILE"
        echo "$dir_name -> FAIL (directory does not exist)" >> "$FAILED_FILE"
        return 1
    fi

    cd "$dir" || {
        echo -e "${RED}✗ $dir_name -> FAIL (cannot access directory)${NC}" | tee -a "$LOG_FILE"
        echo "$dir_name -> FAIL (cannot access directory)" >> "$FAILED_FILE"
        return 1
    }

    # Check if docker-compose.yml exists
    if [ ! -f "docker-compose.yml" ]; then
        echo -e "${RED}✗ $dir_name -> FAIL (no docker-compose.yml)${NC}" | tee -a "$LOG_FILE"
        echo "$dir_name -> FAIL (no docker-compose.yml)" >> "$FAILED_FILE"
        cd - > /dev/null
        return 1
    fi

    # Try to build and start with timeout
    echo "  Building and starting containers..." | tee -a "$LOG_FILE"

    # Run docker compose up with timeout
    docker compose up -d > /tmp/docker_build_$$.log 2>&1
    local exit_code=$?

    if [ $exit_code -eq 0 ]; then
        # Check if containers are actually running
        sleep 5  # Give containers a moment to start

        local running_containers=$(docker compose ps --services --filter "status=running" 2>/dev/null | wc -l)

        if [ $running_containers -gt 0 ]; then
            echo -e "${GREEN}✓ $dir_name -> SUCCESS${NC}" | tee -a "$LOG_FILE"
            echo "$dir_name" >> "$SUCCESS_FILE"

            # Show running containers
            echo "  Running containers:" | tee -a "$LOG_FILE"
            docker compose ps 2>&1 | tee -a "$LOG_FILE"

            cd - > /dev/null
            return 0
        else
            echo -e "${RED}✗ $dir_name -> FAIL (no containers running)${NC}" | tee -a "$LOG_FILE"
            echo "$dir_name -> FAIL (no containers running)" >> "$FAILED_FILE"
            echo "  Build output:" >> "$LOG_FILE"
            cat /tmp/docker_build_$$.log >> "$LOG_FILE"
            cd - > /dev/null
            return 1
        fi
    elif [ $exit_code -eq 124 ]; then
        echo -e "${RED}✗ $dir_name -> FAIL (timeout after ${TIMEOUT}s)${NC}" | tee -a "$LOG_FILE"
        echo "$dir_name -> FAIL (timeout)" >> "$FAILED_FILE"
        echo "  Build output:" >> "$LOG_FILE"
        cat /tmp/docker_build_$$.log >> "$LOG_FILE"
        cd - > /dev/null
        return 1
    else
        echo -e "${RED}✗ $dir_name -> FAIL (build error)${NC}" | tee -a "$LOG_FILE"
        echo "$dir_name -> FAIL (build error)" >> "$FAILED_FILE"
        echo "  Build output:" >> "$LOG_FILE"
        cat /tmp/docker_build_$$.log >> "$LOG_FILE"
        cd - > /dev/null
        return 1
    fi
}

# Function to cleanup
cleanup_docker_compose() {
    local dir=$1
    local dir_name=$(basename "$dir")

    echo "  Cleaning up $dir_name..." | tee -a "$LOG_FILE"

    cd "$dir" || return

    docker compose down > /dev/null 2>&1

    echo "  Cleanup complete" | tee -a "$LOG_FILE"
    echo "" | tee -a "$LOG_FILE"
}

# Main logic - iterate through provided directories
for dir in "$@"; do
    # Expand tilde to home directory if present
    dir="${dir/#\~/$HOME}"

    total=$((total + 1))

    if test_docker_compose "$dir"; then
        success=$((success + 1))
    else
        failed=$((failed + 1))
    fi

    # Always cleanup after test
    cleanup_docker_compose "$dir"

done

# Print summary
echo "" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "Test Summary" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "Total tested: $total" | tee -a "$LOG_FILE"
echo -e "${GREEN}Successful: $success${NC}" | tee -a "$LOG_FILE"
echo -e "${RED}Failed: $failed${NC}" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
echo "Detailed results saved to:" | tee -a "$LOG_FILE"
echo "  - Full log: $LOG_FILE" | tee -a "$LOG_FILE"
echo "  - Successful apps: $SUCCESS_FILE" | tee -a "$LOG_FILE"
echo "  - Failed apps: $FAILED_FILE" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
echo "Completed: $(date)" | tee -a "$LOG_FILE"

# Cleanup temp files
rm -f /tmp/docker_build_*.log

# Exit with appropriate code
if [ $failed -gt 0 ]; then
    exit 1
else
    exit 0
fi