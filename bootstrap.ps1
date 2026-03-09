#Requires -RunAsAdministrator

Write-Host "================================="
Write-Host "Bootstrapping development machine"
Write-Host "================================="

function Install-PackageIfMissing($package) {
    winget list --id $package --exact --accept-source-agreements 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Installing $package ..."
        winget install --id $package -e --source winget --accept-package-agreements --accept-source-agreements
    } else {
        Write-Host "$package already installed"
    }
}

# Ensure winget exists
if (!(Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-Host "Winget not found. Please install App Installer from Microsoft Store."
    exit 1
}

# Install core tools
Install-PackageIfMissing "Git.Git"
Install-PackageIfMissing "Python.Python.3.12"
Install-PackageIfMissing "Microsoft.VisualStudioCode"
Install-PackageIfMissing "TeXLive.TeXLive"

$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path", "User")

# Install Python tooling
Write-Host "Installing Python development tools..."
pip install -r "$PSScriptRoot\python\requirements-dev.txt"

# Install VSCode extensions
Write-Host "Installing VSCode extensions..."
& "$PSScriptRoot\install-vscode-extensions.ps1"

# Setup configuration links
Write-Host "Linking configuration files..."
& "$PSScriptRoot\install.ps1"

Write-Host ""
Write-Host "Bootstrap complete."
Write-Host ""
Write-Host "Action required: set your Git identity:"
Write-Host '  git config --global user.name "Your Name"'
Write-Host '  git config --global user.email "you@example.com"'