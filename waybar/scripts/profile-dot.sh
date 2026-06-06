#!/usr/bin/env bash
PROFILE=$(cat /sys/firmware/acpi/platform_profile 2>/dev/null || echo "balanced")
case "$PROFILE" in
    low-power)   echo '{"text": "●", "class": "save",    "tooltip": "Power Saver"}' ;;
    performance) echo '{"text": "●", "class": "perf",    "tooltip": "Performance"}' ;;
    *)           echo '{"text": "●", "class": "balanced", "tooltip": "Balanced"}' ;;
esac
