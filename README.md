# Dotfiles

Arch Linux + Hyprland setup. Public, shareable configs — no personal data.

| Tool | Location |
|------|----------|
| Hyprland | `hypr/hyprland.conf` + `hypr/scripts/` |
| Waybar | `waybar/config.jsonc`, `waybar/style.css`, `waybar/scripts/` |
| Kitty | `kitty/kitty.conf` |
| Rofi | `rofi/launcher.rasi`, `rofi/tokyo-night.rasi` |
| Mako | `mako/config` |
| Fastfetch | `fastfetch/config.jsonc` |
| Zathura | `zathura/zathurarc` |
| Starship | `starship/starship.toml` |
| Zsh | `zsh/zshrc` |
| VSCode | `vscode/settings.json`, `vscode/keybindings.json`, `vscode/extensions.txt` |
| Git | `git/.gitconfig` |
| EditorConfig | `editor/.editorconfig` |

## Stack

- **WM:** Hyprland
- **Bar:** Waybar with custom Python popup system (volume, brightness, battery, bluetooth, wifi, media, calendar, Mullvad)
- **Terminal:** Kitty + Yazi
- **Launcher:** Rofi
- **Notifications:** Mako
- **Theme:** Tokyo Night GTK, Catppuccin cursors
- **Shell:** Zsh + Starship

## Install

```bash
git clone https://github.com/Riad-Attou/dotfiles ~/dotfiles
cd ~/dotfiles
chmod +x install.sh
./install.sh
```

> **Note:** Edit `hypr/hyprland.conf` and uncomment/fill the bluetooth autoconnect line with your device MAC.

## License

MIT
