#!/usr/bin/env bash
set -euo pipefail

DOTFILES="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VSCODE_USER="$HOME/.config/Code/User"

# ── helpers ──────────────────────────────────────────────────────────────────

symlink() {
  local src="$1" dst="$2"
  mkdir -p "$(dirname "$dst")"
  if [[ -e "$dst" && ! -L "$dst" ]]; then
    echo "  backing up $dst → $dst.bak"
    mv "$dst" "$dst.bak"
  fi
  ln -sf "$src" "$dst"
  echo "  $dst -> $src"
}

# ── VSCode ────────────────────────────────────────────────────────────────────

echo "==> VSCode settings"
symlink "$DOTFILES/vscode/settings.json"    "$VSCODE_USER/settings.json"
symlink "$DOTFILES/vscode/keybindings.json" "$VSCODE_USER/keybindings.json"

echo "==> VSCode extensions"
while IFS= read -r ext; do
  [[ -z "$ext" || "$ext" == \#* ]] && continue
  if code --install-extension "$ext" --force 2>&1 | grep -q "already installed\|successfully installed"; then
    echo "  ok   $ext"
  else
    code --install-extension "$ext" --force 2>&1 | tail -1 | xargs -I{} echo "  fail $ext: {}"
  fi
done < "$DOTFILES/vscode/extensions.txt"

# ── Git ───────────────────────────────────────────────────────────────────────

echo "==> Git"
symlink "$DOTFILES/git/.gitconfig" "$HOME/.gitconfig"

# ── Editor ────────────────────────────────────────────────────────────────────

echo "==> Editorconfig"
symlink "$DOTFILES/editor/.editorconfig" "$HOME/.editorconfig"

echo "Done."
