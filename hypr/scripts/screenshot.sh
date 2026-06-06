#!/usr/bin/env bash
# screenshot.sh area|screen [annotate]
# With annotate: captures → opens satty for annotation → saves + copies on save.
# Without annotate: direct grimblast copysave (original fast behavior).

MODE="${1:-area}"
ANNOTATE="${2:-}"
OUTDIR="$HOME/Pictures/Screenshots"
FILE="$OUTDIR/$(date +%Y%m%d_%H%M%S).png"

mkdir -p "$OUTDIR"

if [[ "$ANNOTATE" == "annotate" ]]; then
    TMP=$(mktemp /tmp/screenshot-XXXXXX.png)
    if grimblast save "$MODE" "$TMP"; then
        satty --filename "$TMP" \
            --output-filename "$FILE" \
            --copy-command wl-copy \
            --actions-on-enter save-to-file,save-to-clipboard,exit \
            --early-exit \
            --floating-hack
    fi
    rm -f "$TMP"
else
    grimblast copysave "$MODE" "$FILE"
fi
