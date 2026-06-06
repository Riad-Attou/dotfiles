#!/usr/bin/env bash
# Wrapper: reapply spicetify before launching Spotify.
# If Spotify was updated (backup version mismatch / stock state), re-backup
# then apply. Uses --skip-update to keep patches stable during the session.
# To update Spotify manually: spotify-update

out=$(spicetify apply 2>&1)
if printf '%s' "$out" | grep -qiE "stock state|mismatch"; then
    spicetify backup apply
fi
exec spotify-launcher --skip-update "$@"
