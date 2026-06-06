#!/usr/bin/env bash
# Clipboard picker with image preview for rofi.
# Images are decoded to a temp dir so rofi can render thumbnails via \0icon\x1f.
# The dir persists until next invocation (so rofi can read files after this script exits).

TMPDIR_CLIP="/tmp/cliphist-previews"
rm -rf "$TMPDIR_CLIP"
mkdir -p "$TMPDIR_CLIP"

while IFS=$'\t' read -r id content; do
    entry="$id	$content"
    if [[ "$content" == "[[ binary data"* ]]; then
        imgfile="$TMPDIR_CLIP/$id.png"
        cliphist decode <<< "$entry" > "$imgfile" 2>/dev/null
        printf '%s\0icon\x1f%s\n' "$entry" "$imgfile"
    else
        printf '%s\n' "$entry"
    fi
done < <(cliphist list)
