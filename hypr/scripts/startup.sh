#!/usr/bin/env bash
# Move the WhatsApp Chrome window to workspace 5 after Chrome restores its session.
# WhatsApp's window class is "google-chrome" (same as the main window); it is only
# distinguishable by its title, so match on title. Runs once at Hyprland start.

for i in $(seq 1 40); do
    sleep 1
    RESULT=$(hyprctl clients -j 2>/dev/null | python3 -c "
import json, sys
clients = json.load(sys.stdin)
for c in clients:
    if 'whatsapp' in c.get('title', '').lower():
        if c['workspace']['id'] == 5:
            print('already')
        else:
            print(c['address'])
        break
" 2>/dev/null)

    case "$RESULT" in
        already) break ;;
        0x*)     hyprctl dispatch movetoworkspacesilent "5,address:$RESULT"; break ;;
    esac
done
