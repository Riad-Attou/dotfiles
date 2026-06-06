#!/usr/bin/env bash

WALLPAPER_DIR="$HOME/Pictures/Wallpapers"
INTERVAL=1800  # seconds (30 minutes)

# Wait for awww daemon to be ready before sending images
until awww query &>/dev/null; do
    sleep 0.5
done

while true; do
    find "$WALLPAPER_DIR" -maxdepth 1 -type f \( -name "*.jpg" -o -name "*.png" -o -name "*.jpeg" \) | shuf | while read -r img; do
        awww img "$img" --transition-type grow --transition-pos center
        ln -sf "$img" "$HOME/.cache/hyprlock-wall"
        sleep "$INTERVAL"
    done
done
