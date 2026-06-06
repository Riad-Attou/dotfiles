#!/bin/bash
STATUS=$(mullvad status 2>/dev/null | head -1)

if echo "$STATUS" | grep -q "Connected"; then
    echo '{"text": "󰒃", "tooltip": "Mullvad connected", "class": "connected"}'
else
    echo '{"text": "󰒄", "tooltip": "Mullvad disconnected", "class": "disconnected"}'
fi
