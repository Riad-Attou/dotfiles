#!/usr/bin/env bash

CONFIG="$HOME/.config/waybar/weather.conf"
CACHE="$HOME/.cache/waybar-weather.json"

# Defaults
CITY="Paris"
INTERVAL=1800

[ -f "$CONFIG" ] && source "$CONFIG"

# Use cache if recent enough
if [ -f "$CACHE" ]; then
    AGE=$(( $(date +%s) - $(stat -c %Y "$CACHE") ))
    [ "$AGE" -lt "$INTERVAL" ] && cat "$CACHE" && exit 0
fi

# Wait for Mullvad to connect (up to 60s) before making requests
WAITED=0
while ! mullvad status 2>/dev/null | grep -q "Connected"; do
    if [ "$WAITED" -ge 60 ]; then
        [ -f "$CACHE" ] && cat "$CACHE" && exit 0
        echo '{"text":"󰒄 No VPN","tooltip":"Waiting for Mullvad..."}'
        exit 0
    fi
    sleep 2
    WAITED=$((WAITED + 2))
done

# Geocode city
ENCODED_CITY=$(python3 -c "import urllib.parse, sys; print(urllib.parse.quote(sys.argv[1]))" "$CITY")
GEO=$(curl -sf --max-time 5 "https://geocoding-api.open-meteo.com/v1/search?name=${ENCODED_CITY}&count=1&language=en&format=json")

if [ -z "$GEO" ] || [ "$(echo "$GEO" | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('results', [])))" 2>/dev/null)" = "0" ]; then
    echo '{"text":"󰖐 N/A","tooltip":"Cannot fetch weather for '"$CITY"'"}' | tee "$CACHE"
    exit 0
fi

LAT=$(echo "$GEO" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['results'][0]['latitude'])")
LON=$(echo "$GEO" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['results'][0]['longitude'])")

# Fetch weather
WEATHER=$(curl -sf --max-time 5 "https://api.open-meteo.com/v1/forecast?latitude=$LAT&longitude=$LON&current_weather=true&temperature_unit=celsius&windspeed_unit=kmh")

if [ -z "$WEATHER" ]; then
    echo '{"text":"󰖐 N/A","tooltip":"Cannot fetch weather"}' | tee "$CACHE"
    exit 0
fi

TEMP=$(echo "$WEATHER" | python3 -c "import json,sys; d=json.load(sys.stdin); print(round(d['current_weather']['temperature']))")
CODE=$(echo "$WEATHER" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['current_weather']['weathercode'])")
IS_DAY=$(echo "$WEATHER" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['current_weather']['is_day'])")

# Map WMO code to icon
case $CODE in
    0)  [ "$IS_DAY" = "1" ] && ICON="󰖙" || ICON="󰖔"; DESC="Clear" ;;
    1)  [ "$IS_DAY" = "1" ] && ICON="󰖙" || ICON="󰖔"; DESC="Mostly clear" ;;
    2)  ICON="󰖕"; DESC="Partly cloudy" ;;
    3)  ICON="󰖐"; DESC="Overcast" ;;
    45|48) ICON="󰖑"; DESC="Fog" ;;
    51|53|55) ICON="󰖗"; DESC="Drizzle" ;;
    61|63|65) ICON="󰖗"; DESC="Rain" ;;
    71|73|75|77) ICON="󰖘"; DESC="Snow" ;;
    80|81|82) ICON="󰖗"; DESC="Showers" ;;
    85|86) ICON="󰖘"; DESC="Snow showers" ;;
    95|96|99) ICON="󰖓"; DESC="Thunderstorm" ;;
    *) ICON="󰖐"; DESC="Unknown" ;;
esac

OUTPUT="{\"text\":\"${ICON} ${TEMP}°C\",\"tooltip\":\"${DESC} in ${CITY}\"}"
echo "$OUTPUT" | tee "$CACHE"
