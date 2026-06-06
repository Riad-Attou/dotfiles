#!/usr/bin/env bash

if pkill -f "yad.*BatteryPopup"; then exit 0; fi

BAT="/sys/class/power_supply/BAT0"
PIPE=$(mktemp -u /tmp/batt-popup-XXXXXX)
mkfifo "$PIPE"

get_text() {
    local CAPACITY STATUS ENERGY_NOW ENERGY_FULL ENERGY_FULL_DESIGN POWER_NOW PROFILE
    CAPACITY=$(cat "$BAT/capacity" 2>/dev/null)
    STATUS=$(cat "$BAT/status" 2>/dev/null)
    ENERGY_NOW=$(cat "$BAT/energy_now" 2>/dev/null)
    ENERGY_FULL=$(cat "$BAT/energy_full" 2>/dev/null)
    ENERGY_FULL_DESIGN=$(cat "$BAT/energy_full_design" 2>/dev/null)
    POWER_NOW=$(cat "$BAT/power_now" 2>/dev/null)
    PROFILE=$(cat /sys/firmware/acpi/platform_profile 2>/dev/null)

    python3 - <<EOF
energy_full        = ${ENERGY_FULL:-0}
energy_full_design = ${ENERGY_FULL_DESIGN:-0}
energy_now         = ${ENERGY_NOW:-0}
power_now          = ${POWER_NOW:-0}
status             = "${STATUS}"
capacity           = ${CAPACITY:-0}
profile            = "${PROFILE}"

full_wh   = energy_full / 1_000_000
design_wh = energy_full_design / 1_000_000
power_w   = power_now / 1_000_000
health    = (energy_full / energy_full_design * 100) if energy_full_design else 0

icon = "󰂄" if status == "Charging" else ("󰚥" if status == "Full" else "󰁹")

time_line = ""
if status == "Discharging" and power_now > 0:
    h = energy_now / power_now
    time_line = f'<span foreground="#7dcfff">⏱</span>  <span foreground="#c0caf5">{int(h)}h {int((h%1)*60):02d}m remaining</span>'
elif status == "Charging" and power_now > 0:
    h = (energy_full - energy_now) / power_now
    time_line = f'<span foreground="#7dcfff">⏱</span>  <span foreground="#c0caf5">{int(h)}h {int((h%1)*60):02d}m to full</span>'

profile_colors = {"low-power": "#7aa2f7", "balanced": "#c0caf5", "performance": "#f7768e", "max-power": "#bb9af7"}
profile_labels = {"low-power": "🔵  Low Power", "balanced": "⚪  Balanced", "performance": "🔴  Performance", "max-power": "🟣  Max Power"}
p_color = profile_colors.get(profile, "#c0caf5")
p_label = profile_labels.get(profile, profile)

sep = '<span foreground="#2a2b3d">──────────────────────</span>'

lines = [
    f'<span foreground="#7aa2f7" weight="bold" size="large">{icon}  {capacity}%</span>  <span foreground="#545c7e">{status}</span>',
    sep,
    f'<span foreground="#e0af68">⚡</span>  <span foreground="#c0caf5">{power_w:.1f}W</span>   <span foreground="#f7768e">❤</span>  <span foreground="#c0caf5">{health:.0f}%</span>',
    f'<span foreground="#9ece6a">🔋</span>  <span foreground="#c0caf5">{full_wh:.1f}Wh</span>  <span foreground="#545c7e">/ {design_wh:.1f}Wh</span>',
]
if time_line:
    lines.append(time_line)
lines += [
    sep,
    f'<span foreground="{p_color}" weight="bold">{p_label}</span>',
]

print("\n".join(lines))
EOF
}

PROFILE=$(cat /sys/firmware/acpi/platform_profile 2>/dev/null)
BTN_SAVER="🔵 Save"
BTN_BALANCED="⚪ Bal"
BTN_PERF="🔴 Perf"
[ "$PROFILE" = "low-power"   ] && BTN_SAVER="🔵 Save ✓"
[ "$PROFILE" = "balanced"    ] && BTN_BALANCED="⚪ Bal ✓"
[ "$PROFILE" = "performance" ] && BTN_PERF="🔴 Perf ✓"

(
    while true; do
        sleep 3
        TEXT=$(get_text)
        echo "text:${TEXT//$'\n'/\\n}" || break
    done
) > "$PIPE" &
UPDATER=$!

yad --info \
    --text="$(get_text)" \
    --listen \
    --title="BatteryPopup" \
    --css="$HOME/.config/waybar/scripts/popup.css" \
    --width=220 \
    --button="$BTN_SAVER:2" \
    --button="$BTN_BALANCED:3" \
    --button="$BTN_PERF:4" \
    < "$PIPE"
EXIT=$?

kill $UPDATER 2>/dev/null
rm -f "$PIPE"

case $EXIT in
    2) powerprofilesctl set power-saver ;;
    3) powerprofilesctl set balanced ;;
    4) powerprofilesctl set performance ;;
esac
