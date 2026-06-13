# nvidiaclaude installer for Windows (PowerShell).
# Usage:
#   irm https://raw.githubusercontent.com/fadhluibnu/nvidiaclaude/main/install.ps1 | iex

$ErrorActionPreference = 'Stop'

$Repo = 'https://raw.githubusercontent.com/fadhluibnu/nvidiaclaude/main'
$Dest = Join-Path $env:LOCALAPPDATA 'Programs\nvidiaclaude'

New-Item -ItemType Directory -Force -Path $Dest | Out-Null

Write-Host "Installing nvidiaclaude to $Dest ..."
Invoke-WebRequest -UseBasicParsing "$Repo/nvidiaclaude.ps1" -OutFile (Join-Path $Dest 'nvidiaclaude.ps1')
Invoke-WebRequest -UseBasicParsing "$Repo/nvidiaclaude_proxy.py" -OutFile (Join-Path $Dest 'nvidiaclaude_proxy.py')

# A .cmd shim so `nvidiaclaude` works from cmd.exe and PowerShell alike.
$shim = @'
@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0nvidiaclaude.ps1" %*
'@
Set-Content -Path (Join-Path $Dest 'nvidiaclaude.cmd') -Value $shim -Encoding ASCII

# Put the install dir on the user PATH if it isn't already.
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if (-not $userPath) { $userPath = '' }
if ($userPath -notlike "*$Dest*") {
  $newPath = if ($userPath) { "$userPath;$Dest" } else { $Dest }
  [Environment]::SetEnvironmentVariable('Path', $newPath, 'User')
  $env:Path = "$env:Path;$Dest"
  Write-Host "Added $Dest to your user PATH."
  Write-Host 'Open a NEW terminal for it to take effect.'
}

Write-Host 'Installed. Run: nvidiaclaude'
