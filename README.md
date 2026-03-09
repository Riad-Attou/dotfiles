# Dotfiles

Personal development environment configuration for Windows + VSCode.

Configurations managed:

| Tool              | File                                                   |
| ----------------- | ------------------------------------------------------ |
| VSCode            | `vscode/settings.json`, `vscode/keybindings.json`      |
| VSCode extensions | `vscode/extensions.txt`                                |
| Python tooling    | `python/requirements-dev.txt`, `python/pyproject.toml` |
| Git               | `git/.gitconfig`                                       |
| LaTeX formatting  | `latex/latexindent.yaml`                               |
| EditorConfig      | `editor/.editorconfig`                                 |

---

## Structure

```
dotfiles/
│
├── vscode/
│   ├── settings.json        # VSCode user settings
│   ├── keybindings.json     # VSCode keybindings
│   └── extensions.txt       # VSCode extension list
│
├── python/
│   ├── requirements-dev.txt # Python dev tools (black, ruff, ...)
│   └── pyproject.toml       # black + ruff config
│
├── latex/
│   └── latexindent.yaml     # latexindent formatter config
│
├── git/
│   └── .gitconfig           # Git aliases, editor, pull/push defaults
│
├── editor/
│   └── .editorconfig        # Universal editor config (indent, charset, ...)
│
├── bootstrap.ps1            # Full machine setup (install + link everything)
├── install.ps1              # Create symlinks only
└── install-vscode-extensions.ps1  # Install VSCode extensions only
```

---

## How symlinks work

Instead of copying config files to the locations that tools expect, `install.ps1` creates **symbolic links** — filesystem pointers that make a file appear in multiple places at once.

For example, after running `install.ps1`, `%APPDATA%\Code\User\settings.json` is not a real file: it's a symlink that points to `vscode/settings.json` in this repo. VSCode reads it transparently, and any edit you make (whether through VSCode's UI or directly in the repo) is the same edit to the same file.

This means:

- You edit configs in one place (the repo), not scattered across the system
- `git diff` shows all your config changes
- Pulling updates on a new machine is a single `git pull` + `.\install.ps1`

> **Windows requirement**: creating symlinks requires either **administrator rights** or **Developer Mode** enabled in Windows Settings → For Developers.

---

## Requirements

- Windows 10/11
- PowerShell 5.1+
- [winget](https://learn.microsoft.com/en-us/windows/package-manager/winget/) (App Installer from Microsoft Store)
- **Administrator rights** or [Developer Mode](https://learn.microsoft.com/en-us/windows/apps/get-started/enable-your-device-for-development) enabled (required for symbolic links)

---

## Bootstrap a new machine

> Run PowerShell as Administrator.

Clone the repository:

```powershell
git clone https://github.com/<your-username>/dotfiles.git
cd dotfiles
```

Run the bootstrap script:

```powershell
.\bootstrap.ps1
```

This will automatically:

1. Install **Git**, **Python 3.12**, **VSCode**, **TeXLive** via winget
2. Install Python dev tools: `black`, `ruff`, `pre-commit`, `pytest`, `mypy`
3. Install all VSCode extensions from `vscode/extensions.txt`
4. Symlink all config files to their expected locations

After bootstrap, set your Git identity (not stored in the repo):

```powershell
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

---

## Symlink config files only

To re-link configs without re-installing tools (e.g. after pulling updates):

```powershell
.\install.ps1
```

---

## Install VSCode extensions only

```powershell
.\install-vscode-extensions.ps1
```

---

## How to update

### Update VSCode settings or keybindings

Edit `vscode/settings.json` or `vscode/keybindings.json` directly — they are symlinked, so VSCode picks up changes immediately. Commit and push.

### Update VSCode extensions

```powershell
code --list-extensions > vscode/extensions.txt
```

Then commit and push.

### Update Python tools

Edit `python/requirements-dev.txt`, then re-run:

```powershell
pip install -r python/requirements-dev.txt
```

### Update Git config

Edit `git/.gitconfig` directly. The symlink means changes apply immediately system-wide.

### Pull updates on another machine

```powershell
git pull
.\install.ps1   # re-links in case new files were added
```

# License

MIT
