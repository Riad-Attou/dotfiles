#Requires -RunAsAdministrator

Write-Host "Linking configuration files..."

$repo   = $PSScriptRoot
$vscode = "$env:APPDATA\Code\User"

function New-RepoLink {
    param(
        [string]$Target,
        [string]$Link
    )

    if (!(Test-Path $Target)) {
        Write-Warning "Source not found, skipping: $Target"
        return
    }

    if (Test-Path $Link -PathType Any) {
        $existing = Get-Item $Link -Force
        if ($existing.LinkType -eq "SymbolicLink") {
            Remove-Item $Link -Force
        } else {
            $bak = "$Link.bak"
            if (Test-Path $bak) {
                Remove-Item $Link -Force
            } else {
                Rename-Item $Link $bak -Force
                Write-Host "  Backed up: $bak"
            }
        }
    }

    $dir = Split-Path $Link -Parent
    if (!(Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }

    New-Item -ItemType SymbolicLink -Path $Link -Target $Target | Out-Null
    Write-Host "  Linked: $Link"
}

# VSCode
New-RepoLink "$repo\vscode\settings.json"    "$vscode\settings.json"
New-RepoLink "$repo\vscode\keybindings.json" "$vscode\keybindings.json"

# EditorConfig
New-RepoLink "$repo\editor\.editorconfig" "$HOME\.editorconfig"

# Git config
New-RepoLink "$repo\git\.gitconfig" "$HOME\.gitconfig"

# Latexindent config
New-RepoLink "$repo\latex\latexindent.yaml" "$HOME\.latexindent.yaml"

Write-Host "Configuration linked."