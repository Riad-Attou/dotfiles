#!/usr/bin/env bash
# Closes popup when focus moves away (click-based, not hover)
TITLE="$1"
SOCKET="$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock"

sleep 0.4

socat - "UNIX-CONNECT:$SOCKET" 2>/dev/null | while IFS= read -r line; do
    if [[ "$line" == activewindow\>\>* ]]; then
        ACTIVE_TITLE="${line##*,}"
        if [[ "$ACTIVE_TITLE" != "$TITLE" ]]; then
            pkill -f "yad.*$TITLE" 2>/dev/null
            exit 0
        fi
    fi
done
