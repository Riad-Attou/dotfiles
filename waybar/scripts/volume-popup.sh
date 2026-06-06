#!/usr/bin/env bash

if pkill -f "yad.*VolumePopup"; then exit 0; fi

hyprctl keyword input:follow_mouse 3
trap 'hyprctl keyword input:follow_mouse 1' EXIT

~/.config/waybar/scripts/popup-watcher.sh "VolumePopup" &
CURRENT=$(wpctl get-volume @DEFAULT_AUDIO_SINK@ | awk '{print int($2 * 100)}')
IS_MUTED=$(wpctl get-volume @DEFAULT_AUDIO_SINK@ | grep -c MUTED)
MUTE_BTN=$([ "$IS_MUTED" -gt 0 ] && echo "🔊 Unmute" || echo "🔇 Mute")

yad --scale \
    --min-value=0 \
    --max-value=150 \
    --value="$CURRENT" \
    --print-partial \
    --mark="100:" \
    --title="VolumePopup" \
    --css="$HOME/.config/waybar/scripts/popup.css" \
    --width=220 \
    --button="$MUTE_BTN:2" \
    2>/dev/null | while IFS= read -r val; do
        wpctl set-volume @DEFAULT_AUDIO_SINK@ "${val}%" 2>/dev/null
    done

[ "${PIPESTATUS[0]}" -eq 2 ] && wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle
