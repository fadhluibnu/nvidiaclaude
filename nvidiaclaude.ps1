# nvidiaclaude - run Claude Code against NVIDIA NIM through a local adapter.
#
# Key resolution order:
#   1. `nvidiaclaude config [KEY]` - set/replace the stored key
#   2. stored config file          - set on a previous run
#   3. $env:NVIDIA_API_KEY         - used and saved for next time
#   4. interactive prompt          - asks for the key if needed

$ErrorActionPreference = 'Stop'

$ConfigDir       = Join-Path $env:APPDATA 'nvidiaclaude'
$ConfigFile      = Join-Path $ConfigDir 'config'
$DefaultEndpoint = 'https://integrate.api.nvidia.com/v1/chat/completions'
$DefaultModel    = 'minimaxai/minimax-m3'
$LocalAuthToken  = 'nvidiaclaude-local'

function Save-Key([string]$Key) {
  $Key = $Key.Trim()
  if ([string]::IsNullOrEmpty($Key)) {
    Write-Host 'Refusing to save an empty key.'
    return
  }
  New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null
  Set-Content -Path $ConfigFile -Value ("NVIDIA_API_KEY=" + $Key) -Encoding ASCII
  try {
    $acl  = New-Object System.Security.AccessControl.FileSecurity
    $acl.SetAccessRuleProtection($true, $false)
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
      "$env:USERDOMAIN\$env:USERNAME", 'FullControl', 'Allow')
    $acl.AddAccessRule($rule)
    Set-Acl -Path $ConfigFile -AclObject $acl
  } catch { }
  Write-Host "Key saved to $ConfigFile"
}

function Get-ConfigValue([string]$Name) {
  if (-not (Test-Path $ConfigFile)) { return $null }
  foreach ($line in Get-Content $ConfigFile) {
    if ($line -like "$Name=*") {
      return $line.Substring($Name.Length + 1)
    }
  }
  return $null
}

function Invoke-Setup {
  Write-Host ''
  Write-Host '+------------------------------------------+'
  Write-Host '|  nvidiaclaude - first-time setup         |'
  Write-Host '+------------------------------------------+'
  Write-Host ''
  Write-Host 'Claude Code will run against NVIDIA NIM.'
  Write-Host 'You only need to enter your NVIDIA API key once.'
  Write-Host 'Get a key from NVIDIA API Catalog.'
  Write-Host ''
  for ($i = 0; $i -lt 3; $i++) {
    $secure = Read-Host -AsSecureString 'NVIDIA API key'
    $bstr   = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    $key    = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    $key = $key.Trim()
    if ($key) { Save-Key $key; return }
    Write-Host "Key can't be empty."
  }
  Write-Host 'Aborting after 3 empty attempts.'
  exit 1
}

function Get-PythonCommand {
  $cmd = Get-Command python3 -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  $cmd = Get-Command python -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  return $null
}

function Quote-ProcessArgument([string]$Value) {
  $escaped = $Value -replace '"', '\"'
  return '"' + $escaped + '"'
}

function Start-NvidiaClaudeProxy {
  $python = Get-PythonCommand
  if (-not $python) {
    Write-Host 'Python 3 not found on PATH.'
    Write-Host 'Install Python 3 before running nvidiaclaude.'
    exit 127
  }

  $scriptDir = Split-Path -Parent $PSCommandPath
  $proxyFile = Join-Path $scriptDir 'nvidiaclaude_proxy.py'
  if (-not (Test-Path $proxyFile)) {
    Write-Host "Proxy file not found: $proxyFile"
    Write-Host 'Reinstall nvidiaclaude so nvidiaclaude_proxy.py is installed next to the command.'
    exit 1
  }

  $tempRoot = Join-Path ([IO.Path]::GetTempPath()) ('nvidiaclaude-' + [Guid]::NewGuid().ToString('N'))
  New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null
  $readyFile = Join-Path $tempRoot 'ready'
  $stdoutFile = Join-Path $tempRoot 'proxy.out.log'
  $stderrFile = Join-Path $tempRoot 'proxy.err.log'

  $proxyArgs = @($proxyFile, '--host', '127.0.0.1', '--port', '0', '--ready-file', $readyFile) |
    ForEach-Object { Quote-ProcessArgument $_ }

  $proc = Start-Process -FilePath $python `
    -ArgumentList ($proxyArgs -join ' ') `
    -PassThru `
    -WindowStyle Hidden `
    -RedirectStandardOutput $stdoutFile `
    -RedirectStandardError $stderrFile

  for ($i = 0; $i -lt 200; $i++) {
    if (Test-Path $readyFile) {
      $port = (Get-Content $readyFile -Raw).Trim()
      if ($port) {
        return @{ Process = $proc; TempRoot = $tempRoot; Port = $port; Stdout = $stdoutFile; Stderr = $stderrFile }
      }
    }
    if ($proc.HasExited) {
      Write-Host 'nvidiaclaude proxy failed to start.'
      if (Test-Path $stdoutFile) { Get-Content $stdoutFile | ForEach-Object { Write-Host "  $_" } }
      if (Test-Path $stderrFile) { Get-Content $stderrFile | ForEach-Object { Write-Host "  $_" } }
      exit 1
    }
    Start-Sleep -Milliseconds 50
  }

  Write-Host 'Timed out waiting for nvidiaclaude proxy.'
  if (Test-Path $stdoutFile) { Get-Content $stdoutFile | ForEach-Object { Write-Host "  $_" } }
  if (Test-Path $stderrFile) { Get-Content $stderrFile | ForEach-Object { Write-Host "  $_" } }
  exit 1
}

function Stop-NvidiaClaudeProxy($Proxy) {
  if (-not $Proxy) { return }
  try {
    if ($Proxy.Process -and -not $Proxy.Process.HasExited) {
      Stop-Process -Id $Proxy.Process.Id -Force -ErrorAction SilentlyContinue
    }
  } catch { }
  try {
    if ($Proxy.TempRoot -and (Test-Path $Proxy.TempRoot)) {
      Remove-Item -Recurse -Force $Proxy.TempRoot
    }
  } catch { }
}

if ($args.Count -ge 1) {
  switch -Regex ($args[0]) {
    '^(config|--config|set-key|--set-key|change|--change|change-key|--change-key)$' {
      if ($args.Count -ge 2) { Save-Key $args[1] } else { Invoke-Setup }
      Write-Host "Done. Run 'nvidiaclaude' to start."
      exit 0
    }
    '^(reset|--reset)$' {
      if (Test-Path $ConfigFile) { Remove-Item $ConfigFile -Force }
      Write-Host 'Stored key removed.'
      exit 0
    }
    '^(update|--update|upgrade|--upgrade)$' {
      Write-Host 'Updating nvidiaclaude to the latest version...'
      irm 'https://raw.githubusercontent.com/fadhluibnu/nvidiaclaude/main/install.ps1' | iex
      exit 0
    }
  }
}

$key = Get-ConfigValue 'NVIDIA_API_KEY'

if (-not $key -and $env:NVIDIA_API_KEY) {
  $key = $env:NVIDIA_API_KEY.Trim()
  Write-Host 'Using NVIDIA_API_KEY from environment; saving for next time.'
  Save-Key $key
}

if (-not $key) {
  Invoke-Setup
  $key = Get-ConfigValue 'NVIDIA_API_KEY'
}

if (-not $key) {
  Write-Host "No API key available. Run 'nvidiaclaude config' to set one."
  exit 1
}

if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
  Write-Host 'claude CLI not found on PATH.'
  Write-Host 'Install Claude Code first: https://docs.claude.com/en/docs/claude-code'
  exit 127
}

$env:NVIDIA_API_KEY = $key
if (-not $env:NVIDIA_NIM_ENDPOINT) { $env:NVIDIA_NIM_ENDPOINT = $DefaultEndpoint }
if (-not $env:NVIDIA_NIM_MODEL) { $env:NVIDIA_NIM_MODEL = $DefaultModel }

$proxy = $null
$exitCode = 1
try {
  $proxy = Start-NvidiaClaudeProxy

  $env:ANTHROPIC_BASE_URL             = "http://127.0.0.1:$($proxy.Port)"
  $env:ANTHROPIC_AUTH_TOKEN           = $LocalAuthToken
  $env:ANTHROPIC_MODEL                = $env:NVIDIA_NIM_MODEL
  $env:ANTHROPIC_DEFAULT_OPUS_MODEL   = $env:NVIDIA_NIM_MODEL
  $env:ANTHROPIC_DEFAULT_SONNET_MODEL = $env:NVIDIA_NIM_MODEL
  $env:ANTHROPIC_DEFAULT_HAIKU_MODEL  = $env:NVIDIA_NIM_MODEL
  $env:ANTHROPIC_SMALL_FAST_MODEL     = $env:NVIDIA_NIM_MODEL
  $env:CLAUDE_CODE_SUBAGENT_MODEL     = $env:NVIDIA_NIM_MODEL
  $env:CLAUDE_CODE_EFFORT_LEVEL       = 'max'

  & claude --dangerously-skip-permissions @args
  $exitCode = $LASTEXITCODE
} finally {
  Stop-NvidiaClaudeProxy $proxy
}
exit $exitCode
