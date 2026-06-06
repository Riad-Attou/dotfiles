#!/usr/bin/env bash

# Pick the best player: prefer Playing > Paused, ignore Stopped/browsers with no track
pick_player() {
    local playing="" paused=""
    while read -r p; do
        local s
        s=$(playerctl -p "$p" status 2>/dev/null)
        case "$s" in
            Playing) playing="${playing:-$p}" ;;
            Paused)  paused="${paused:-$p}"  ;;
        esac
    done < <(playerctl -l 2>/dev/null)
    echo "${playing:-$paused}"
}

PLAYER=$(pick_player)

if [ -z "$PLAYER" ]; then
    echo '{"text": "", "tooltip": "", "class": "stopped"}'
    exit 0
fi

STATUS=$(playerctl -p "$PLAYER" status 2>/dev/null)
ARTIST=$(playerctl -p "$PLAYER" metadata artist 2>/dev/null)
TITLE=$(playerctl -p "$PLAYER" metadata title 2>/dev/null)

if [ -z "$TITLE" ]; then
    echo '{"text": "", "tooltip": "", "class": "stopped"}'
    exit 0
fi

MAX=35
DISPLAY="$ARTIST - $TITLE"
[ -z "$ARTIST" ] && DISPLAY="$TITLE"
if [ ${#DISPLAY} -gt $MAX ]; then
    DISPLAY="${DISPLAY:0:$MAX}…"
fi

if [ "$STATUS" = "Playing" ]; then
    ICON="󰎆"
    CLASS="playing"
else
    ICON="󰏤"
    CLASS="paused"
fi

TOOLTIP="${ARTIST:+$ARTIST\n}$TITLE\n\nScroll up: next  |  Scroll down: previous"
echo "{\"text\": \"$ICON  $DISPLAY\", \"tooltip\": \"$TOOLTIP\", \"class\": \"$CLASS\"}"
