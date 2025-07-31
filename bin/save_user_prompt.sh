#!/bin/bash

# Input JSON file (or stdin if not provided)
INPUT_JSON=${1:-/dev/stdin}
# Output YAML file
OUTPUT_YAML=${CLAUDE_PROJECT_DIR}/user_prompts.yaml

# Get current timestamp
TIMESTAMP=$(date '+%Y-%m-%d %H:%M')

# Extract prompt from JSON and escape it properly
PROMPT=$(jq -r '.prompt // empty' "$INPUT_JSON")

# Check if prompt exists
if [ -z "$PROMPT" ]; then
    echo "Error: No 'prompt' key found in JSON input" >&2
    exit 1
fi

# Initialize YAML file if it doesn't exist
if [ ! -f "$OUTPUT_YAML" ]; then
    echo "user_prompts:" > "$OUTPUT_YAML"
fi

# Use yq to add the new prompt entry
# The -i flag edits in place, and we use proper YAML literal block syntax
yq eval ".user_prompts[\"$TIMESTAMP\"] = \"$PROMPT\"" -i "$OUTPUT_YAML"

# Convert the string value to literal block style for better readability
yq eval ".user_prompts[\"$TIMESTAMP\"] style=\"literal\"" -i "$OUTPUT_YAML"
