#!/usr/bin/env bash

# ----------------- Check minimum arguments --------------------------
if [ "$#" -lt 1 ]; then
    echo "Usage: ./run_function.sh <script.sh> [arg1 arg2 ...]"
    exit 1
fi

TARGET_SCRIPT="$1"
shift # Remove the script path from the argument list

# ----------------- Validate file existence --------------------------
if [ ! -f "$TARGET_SCRIPT" ]; then
    echo "Error: File '${TARGET_SCRIPT}' not found."
    exit 1
fi

# Extract the base function name (removes path and .sh extension)
SCRIPT_BASE=$(basename "$TARGET_SCRIPT")
FUNC_NAME="${SCRIPT_BASE%.*}"

# ----------------- Load external script -----------------------------
# Source the file to load its functions into the current environment
source "$TARGET_SCRIPT"

# ----------------- Verify and execute function ----------------------
# Check if the function named after the file actually exists
if ! declare -f "$FUNC_NAME" > /dev/null; then
    echo "Error: No function named '${FUNC_NAME}' found in '${TARGET_SCRIPT}'"
    exit 1
fi

# Execute the dynamic function forwarding all remaining arguments
"$FUNC_NAME" "$@"
RESULT=$?

if [ $RESULT -ne 0 ]; then
    exit 1
fi