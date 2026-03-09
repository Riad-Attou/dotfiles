if (!(Get-Command code -ErrorAction SilentlyContinue)) {
    Write-Warning "VSCode 'code' command not found. Make sure VSCode is installed and available in PATH."
    exit 1
}

Write-Host "Installing VSCode extensions..."

Get-Content "$PSScriptRoot\vscode\extensions.txt" |
    Where-Object { $_.Trim() -ne "" } |
    ForEach-Object { code --install-extension $_ }

Write-Host "Extensions installed."