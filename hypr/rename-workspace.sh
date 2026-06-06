#!/usr/bin/env bash
WS=$(hyprctl activeworkspace -j | jq -r '.id')
NAME=$(rofi -dmenu -p "󰏫 Rename workspace $WS" \
    -theme ~/.config/rofi/tokyo-night.rasi \
    -lines 0 2>/dev/null)
if [ -n "$NAME" ]; then
    hyprctl dispatch renameworkspace "$WS" "$NAME"
    pkill waybar
    waybar &>/dev/null &
fi
