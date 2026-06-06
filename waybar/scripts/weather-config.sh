#!/usr/bin/env bash

CONFIG="$HOME/.config/waybar/weather.conf"
CACHE="$HOME/.cache/waybar-weather.json"
THEME="$HOME/.config/rofi/tokyo-night.rasi"

CITY="Paris"
INTERVAL=1800
[ -f "$CONFIG" ] && source "$CONFIG"

# Pick city via rofi
NEW_CITY=$(echo "$CITY" | rofi -dmenu -p "󰖙  City" -theme "$THEME")
[ -z "$NEW_CITY" ] && exit 0

# Pick refresh interval
CHOICE=$(printf "15 minutes\n30 minutes\n1 hour\n3 hours\n6 hours" \
    | rofi -dmenu -p "󱑆  Refresh every" -theme "$THEME")

case "$CHOICE" in
    "15 minutes") NEW_INTERVAL=900 ;;
    "30 minutes") NEW_INTERVAL=1800 ;;
    "1 hour")     NEW_INTERVAL=3600 ;;
    "3 hours")    NEW_INTERVAL=10800 ;;
    "6 hours")    NEW_INTERVAL=21600 ;;
    *)            NEW_INTERVAL=$INTERVAL ;;
esac

# Save
echo "CITY=\"$NEW_CITY\""     > "$CONFIG"
echo "INTERVAL=$NEW_INTERVAL" >> "$CONFIG"

# Bust cache and refresh waybar
rm -f "$CACHE"
pkill -RTMIN+8 waybar
notify-send "Weather" "Set to ${NEW_CITY}, refreshing every ${CHOICE}" --expire-time=3000
