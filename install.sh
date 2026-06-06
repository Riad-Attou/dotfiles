#!/usr/bin/env bash
set -euo pipefail

DOTFILES="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VSCODE_USER="$HOME/.config/Code/User"

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

echo "==> Hyprland"
symlink "$DOTFILES/hypr"        ~/.config/hypr

echo "==> Waybar"
symlink "$DOTFILES/waybar"      ~/.config/waybar

echo "==> Kitty"
symlink "$DOTFILES/kitty"       ~/.config/kitty

echo "==> Rofi"
symlink "$DOTFILES/rofi"        ~/.config/rofi

echo "==> Mako"
symlink "$DOTFILES/mako"        ~/.config/mako

echo "==> Fastfetch"
symlink "$DOTFILES/fastfetch"   ~/.config/fastfetch

echo "==> Zathura"
symlink "$DOTFILES/zathura"     ~/.config/zathura

echo "==> Starship"
symlink "$DOTFILES/starship/starship.toml" ~/.config/starship.toml

echo "==> Zsh"
symlink "$DOTFILES/zsh/zshrc"  ~/.zshrc

echo "==> Git"
symlink "$DOTFILES/git/.gitconfig" ~/.gitconfig

echo "==> EditorConfig"
symlink "$DOTFILES/editor/.editorconfig" ~/.editorconfig

echo "==> VSCode settings"
symlink "$DOTFILES/vscode/settings.json"    "$VSCODE_USER/settings.json"
symlink "$DOTFILES/vscode/keybindings.json" "$VSCODE_USER/keybindings.json"

echo "==> VSCode extensions"
while IFS= read -r ext; do
    [[ -z "$ext" || "$ext" == \#* ]] && continue
    code --install-extension "$ext" --force 2>&1 | grep -q "already installed\|successfully installed" \
        && echo "  ok   $ext" \
        || echo "  skip $ext"
done < "$DOTFILES/vscode/extensions.txt"

echo "Done."
