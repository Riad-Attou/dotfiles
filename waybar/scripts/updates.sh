#!/bin/bash
COUNT=$(checkupdates 2>/dev/null | wc -l)
AUR=$(yay -Qu 2>/dev/null | wc -l)
TOTAL=$((COUNT + AUR))

if [ "$TOTAL" -eq 0 ]; then
    echo '{"text": "", "tooltip": "System up to date", "class": "uptodate"}'
else
    echo "{\"text\": \"󰚰 $TOTAL\", \"tooltip\": \"$COUNT pacman · $AUR AUR\", \"class\": \"pending\"}"
fi
