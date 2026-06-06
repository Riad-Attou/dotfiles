#!/usr/bin/env bash

# Toggle: close if already open
if pkill -f "yad.*BrightnessPopup"; then exit 0; fi

hyprctl keyword input:follow_mouse 3
trap 'hyprctl keyword input:follow_mouse 1' EXIT

~/.config/waybar/scripts/popup-watcher.sh "BrightnessPopup" &
CURRENT=$(brightnessctl -m | cut -d, -f4 | tr -d '%')

yad --scale \
    --min-value=1 \
    --max-value=100 \
    --value="$CURRENT" \
    --print-partial \
    --no-buttons \
    --title="BrightnessPopup" \
    --css="$HOME/.config/waybar/scripts/popup.css" \
    --width=240 \
    2>/dev/null | while IFS= read -r val; do
        brightnessctl set "${val}%" -q 2>/dev/null
    done
