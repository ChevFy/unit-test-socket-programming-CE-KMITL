#!/bin/bash
# Network condition setup script for Docker containers
# Usage: ./network_setup.sh <delay> <loss> <duplicate> <reorder>
# Example: ./network_setup.sh 5ms 2% null null
# Note: Use 'null' for parameters you don't want to apply

DELAY=$1
LOSS=$2
DUPLICATE=$3
REORDER=$4

# Clear existing tc rules
echo "Clearing existing network rules..."
tc qdisc del dev eth0 root 2>/dev/null || true

# Build netem command dynamically
NETEM_CMD="tc qdisc add dev eth0 root netem"

# Add delay if specified
if [ "$DELAY" != "null" ] && [ -n "$DELAY" ]; then
    NETEM_CMD="$NETEM_CMD delay $DELAY"
fi

# Add loss if specified
if [ "$LOSS" != "null" ] && [ -n "$LOSS" ]; then
    NETEM_CMD="$NETEM_CMD loss $LOSS"
fi

# Add duplicate if specified
if [ "$DUPLICATE" != "null" ] && [ -n "$DUPLICATE" ]; then
    NETEM_CMD="$NETEM_CMD duplicate $DUPLICATE"
fi

# Add reorder if specified
if [ "$REORDER" != "null" ] && [ -n "$REORDER" ]; then
    NETEM_CMD="$NETEM_CMD reorder $REORDER"
fi

# Apply network conditions if any were specified
if [ "$NETEM_CMD" != "tc qdisc add dev eth0 root netem" ]; then
    echo "Applying network conditions: $NETEM_CMD"
    $NETEM_CMD
    
    if [ $? -eq 0 ]; then
        echo "Network conditions applied successfully"
        tc qdisc show dev eth0
    else
        echo "Error: Failed to apply network conditions"
        exit 1
    fi
else
    echo "No network conditions specified (all parameters are null)"
fi
