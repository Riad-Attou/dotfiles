#!/usr/bin/env bash

CHOICE=$(printf "󰌾  Lock\n󰒲  Sleep\n󰐥  Shutdown\n󰜉  Reboot" \
    | rofi -dmenu -p "" -theme ~/.config/rofi/tokyo-night.rasi -i)

case "$CHOICE" in
    *Lock*)     hyprlock ;;
    *Sleep*)    systemctl suspend ;;
    *Shutdown*) systemctl poweroff ;;
    *Reboot*)   systemctl reboot ;;
esac
