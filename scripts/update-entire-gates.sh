#!/bin/bash
# Update the Entire Gates 'Checks' sub-gate configuration to scope it to only
# the three actual CI workflow checks, preventing non-CI bookkeeping checks
# (like the Trunk Merge Queue's own check) from poisoning the gate.
#
# Issue: https://github.com/elviskahoro/native/issues/92

set -euo pipefail

# Configuration
REPO_OWNER="elviskahoro"
REPO_NAME="native"
TRAILS_API_BASE="https://api.trails.app/api"
API_ENDPOINT="${TRAILS_API_BASE}/v1/trails/gh/${REPO_OWNER}/${REPO_NAME}/gates"

# Get the API token
if [[ -z "${TRUNK_API_TOKEN:-}" ]]; then
    echo "Error: TRUNK_API_TOKEN not found in environment" >&2
    exit 1
fi

echo "Updating Entire Gates configuration for ${REPO_OWNER}/${REPO_NAME}"
echo "API endpoint: ${API_ENDPOINT}"
echo ""

# Fetch current configuration
echo "Fetching current gates configuration..."
CURRENT_CONFIG=$(curl -s -H "Authorization: Bearer ${TRUNK_API_TOKEN}" \
    -H "Content-Type: application/json" \
    "${API_ENDPOINT}")

if [[ -z "$CURRENT_CONFIG" ]]; then
    echo "Error: Failed to fetch current gates configuration" >&2
    exit 1
fi

echo "Current gates configuration fetched successfully"
echo ""

# Extract the checks gate and update it
UPDATED_CONFIG=$(echo "$CURRENT_CONFIG" | jq '.gates[] | select(.gateKey == "checks")')

if [[ -z "$UPDATED_CONFIG" ]]; then
    echo "Error: 'checks' sub-gate not found in current configuration" >&2
    exit 1
fi

echo "Current 'Checks' sub-gate configuration:"
echo "$UPDATED_CONFIG" | jq '.'
echo ""

# Create the new required_checks array
NEW_REQUIRED_CHECKS=$(jq -n '[
  "Trunk Check",
  "Unit tests",
  "Generate & Verify Docs and Social Cards"
]')

# Update the configuration with the new required_checks
UPDATED_CONFIG=$(echo "$UPDATED_CONFIG" | jq ".config.required_checks = ${NEW_REQUIRED_CHECKS}")

echo "New 'Checks' sub-gate configuration:"
echo "$UPDATED_CONFIG" | jq '.'
echo ""

# Prepare the patch payload
PATCH_PAYLOAD=$(jq -n --argjson gate "$UPDATED_CONFIG" '{gates: [$gate]}')

# Make the PATCH request
echo "Applying configuration update..."
RESPONSE=$(curl -s -X PATCH \
    -H "Authorization: Bearer ${TRUNK_API_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "$PATCH_PAYLOAD" \
    "${API_ENDPOINT}")

# Check if the request was successful
if echo "$RESPONSE" | jq . >/dev/null 2>&1; then
    echo "✓ Successfully updated Entire Gates configuration"
    echo ""
    echo "Updated configuration:"
    echo "$RESPONSE" | jq '.'
    echo ""
    echo "✓ Update completed successfully"
    echo ""
    echo "The 'Checks' sub-gate will now only require these CI checks:"
    echo "  - Trunk Check"
    echo "  - Unit tests"
    echo "  - Generate & Verify Docs and Social Cards"
    echo ""
    echo "Non-CI bookkeeping checks (like 'Trunk Merge Queue (main)') will no longer"
    echo "poison the gate when the merge queue has a setback."
else
    echo "Error: Failed to update gates configuration" >&2
    echo "Response: $RESPONSE" >&2
    exit 1
fi
