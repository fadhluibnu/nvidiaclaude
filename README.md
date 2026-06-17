# nvidiaclaude

Run [Claude Code](https://docs.claude.com/en/docs/claude-code) against
OpenAI Chat Completions-compatible providers through a local
Anthropic-compatible adapter.

Install once, add one or more provider API tokens, and then run
`nvidiaclaude`. The command starts a local proxy, points Claude Code at it, and
forwards requests to the configured provider. NVIDIA NIM remains the default
provider endpoint.

> Requires the `claude` CLI and Python 3 to already be installed.

## Install

### Stable: main

macOS / Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/fadhluibnu/nvidiaclaude/main/install.sh | bash
```

Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/fadhluibnu/nvidiaclaude/main/install.ps1 | iex
```

### Beta: dev

macOS / Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/fadhluibnu/nvidiaclaude/dev/install.sh | NVIDIACLAUDE_INSTALL_REF=dev bash
```

Windows PowerShell:

```powershell
$env:NVIDIACLAUDE_INSTALL_REF = 'dev'
irm https://raw.githubusercontent.com/fadhluibnu/nvidiaclaude/dev/install.ps1 | iex
```

The installer stores the selected channel, so `nvidiaclaude update` keeps using
the same branch. The beta install uses the `dev` branch, so the `dev` branch
must be pushed to GitHub before those URLs work.

Installs `nvidiaclaude` and `nvidiaclaude_proxy.py` into `~/.local/bin` on
macOS/Linux, or `%LOCALAPPDATA%\Programs\nvidiaclaude` on Windows. If the
install directory is not on your `PATH`, the installer prints the next step.

## Use

First run asks for your provider API token and saves it:

```bash
nvidiaclaude
```

Every run after that uses the stored token list. Any arguments pass through to
`claude`:

```bash
nvidiaclaude "refactor this module"
nvidiaclaude --help
```

Show the nvidiaclaude-specific command reference:

```bash
nvidiaclaude commands
```

## Command Reference

### Start

```bash
nvidiaclaude [CLAUDE_ARGS...]
```

Starts Claude Code through the local OpenAI-compatible adapter. Extra
arguments pass through to the `claude` CLI.

### API Key

```bash
nvidiaclaude config <KEY>
nvidiaclaude change-key [KEY]
nvidiaclaude token add [KEY]
nvidiaclaude token list
nvidiaclaude token remove <INDEX>
nvidiaclaude token clear
nvidiaclaude reset
```

`config` and `change-key` replace the stored token list with one token.
`token add` appends another token for automatic failover. `token list` masks
stored values, `token remove` deletes one token by index, and `token clear` or
`reset` removes all stored tokens without removing the stored model or endpoint.

### Model

```bash
nvidiaclaude change-model <MODEL>
nvidiaclaude set-model <MODEL>
nvidiaclaude model
nvidiaclaude reset-model
```

Use `change-model` or `set-model` to persist a model. Use `model` to show the
model new runs will use. Use `reset-model` to return to the default model.

### Endpoint

```bash
nvidiaclaude change-endpoint <URL>
nvidiaclaude set-endpoint <URL>
nvidiaclaude endpoint
nvidiaclaude reset-endpoint
```

Use `change-endpoint` or `set-endpoint` to persist a provider endpoint. Use
`endpoint` to show the endpoint new runs will use. Use `reset-endpoint` to
return to the default NVIDIA endpoint.

### Maintenance

```bash
nvidiaclaude update
nvidiaclaude uninstall
nvidiaclaude commands
```

`update` re-runs the installer from the selected install branch. `uninstall`
removes installed files, stored config, temporary files, and leftover local
proxy processes. `commands` prints the nvidiaclaude command reference. Aliases
for `commands`: `help`, `--help-nvidiaclaude`.

### Environment Overrides

```bash
NVIDIACLAUDE_API_KEY=<KEY> nvidiaclaude
NVIDIACLAUDE_API_KEYS=<KEY1>,<KEY2> nvidiaclaude
NVIDIACLAUDE_MODEL=<MODEL> nvidiaclaude
NVIDIACLAUDE_API_ENDPOINT=<URL> nvidiaclaude
NVIDIA_API_KEY=<KEY> nvidiaclaude
NVIDIA_API_KEYS=<KEY1>,<KEY2> nvidiaclaude
NVIDIA_NIM_MODEL=<MODEL> nvidiaclaude
NVIDIA_NIM_ENDPOINT=<URL> nvidiaclaude
NVIDIACLAUDE_STREAM_PING_SECONDS=<SECONDS> nvidiaclaude
NVIDIACLAUDE_TOKEN_COOLDOWN_SECONDS=<SECONDS> nvidiaclaude
NVIDIACLAUDE_RATE_LIMIT_RPM=<RPM> nvidiaclaude
NVIDIACLAUDE_RATE_LIMIT_SCOPE=global nvidiaclaude
NVIDIACLAUDE_RATE_LIMIT_WINDOW_SECONDS=<SECONDS> nvidiaclaude
NVIDIACLAUDE_INSTALL_REF=dev nvidiaclaude update
NVIDIACLAUDE_BIN_DIR=<DIR> ./install.sh
```

`NVIDIACLAUDE_API_KEY` or `NVIDIACLAUDE_API_KEYS` is saved for next time if no
token is stored yet. `NVIDIA_API_KEY` and `NVIDIA_API_KEYS` are legacy aliases.
`NVIDIACLAUDE_MODEL` and `NVIDIACLAUDE_API_ENDPOINT` override config for one
run. `NVIDIA_NIM_MODEL` and `NVIDIA_NIM_ENDPOINT` are legacy aliases.
`NVIDIACLAUDE_STREAM_PING_SECONDS` controls stream heartbeat pings while
waiting for provider chunks. Set it to `0` to disable pings.
`NVIDIACLAUDE_TOKEN_COOLDOWN_SECONDS` controls how long a failed token is
avoided after token auth, quota, or rate-limit errors. Default: `60`.
`NVIDIACLAUDE_RATE_LIMIT_RPM` proactively throttles provider requests. Default:
`38`; set it to `0` to disable proactive throttling.
`NVIDIACLAUDE_RATE_LIMIT_SCOPE` can be `global` or `per-token`. Default:
`global`.
`NVIDIACLAUDE_RATE_LIMIT_WINDOW_SECONDS` controls the RPM window length.
Default: `60`.
`NVIDIACLAUDE_INSTALL_REF` overrides the install/update branch for one run.
`NVIDIACLAUDE_BIN_DIR` changes where the shell installer writes files.

### Config Paths

| Platform      | Path                                               |
| ------------- | -------------------------------------------------- |
| macOS/Linux   | `~/.config/nvidiaclaude/config`                    |
| Windows       | `%APPDATA%\nvidiaclaude\config`                    |

### Ways to Provide Tokens

Tokens are resolved in this order:

1. Stored config file.
2. `NVIDIACLAUDE_API_KEYS` environment variable, comma-separated.
3. `NVIDIACLAUDE_API_KEY` environment variable.
4. `NVIDIA_API_KEYS` environment variable, comma-separated legacy alias.
5. `NVIDIA_API_KEY` environment variable, legacy alias.
6. Interactive prompt - asked for automatically if none of the above is set.

## Manage Your Tokens

```bash
nvidiaclaude token add         # add a token interactively
nvidiaclaude token add <KEY>   # add a token without a prompt
nvidiaclaude token list        # show masked stored tokens
nvidiaclaude token remove 2    # delete token number 2
nvidiaclaude token clear       # delete all stored tokens
nvidiaclaude reset             # alias for clearing stored tokens
```

`config`, `set-key`, and `change` are accepted as aliases for `change-key`.
They replace the stored token list with a single token for compatibility with
older installs.

## Auto Failover

When multiple tokens are configured, the local proxy automatically switches to
the next token for token-specific failures:

- invalid or expired token responses
- unauthorized or forbidden token responses
- token auth or token quota messages
- HTTP `429`, RPM, or rate-limit messages

When a token returns `429`, the proxy marks that token as cooling down and
immediately tries the next ready token. If every configured token is cooling
down after provider rate-limit responses, the request fails with a clear error
so Claude Code can stop instead of waiting for a long internal retry loop.

The proxy also has a silent proactive RPM throttle to avoid hitting provider
request-per-minute limits. When the shared RPM bucket is full, the proxy waits
internally without printing rate-limit noise to your terminal. Use
`NVIDIACLAUDE_RATE_LIMIT_SCOPE=per-token` only when your tokens are known to
have separate RPM buckets.

For streaming responses, failover is safe before content output starts. If a
token fails after partial streaming output, the proxy returns an SSE error for
that response and avoids that token for the cooldown window.

## Manage Your Model

Change the stored provider model without reinstalling:

```bash
nvidiaclaude change-model <MODEL>
nvidiaclaude set-model <MODEL>
```

Show the model that new runs will use:

```bash
nvidiaclaude model
```

Return to the default model:

```bash
nvidiaclaude reset-model
```

The model is resolved in this order:

1. `NVIDIACLAUDE_MODEL` environment variable for a one-off run.
2. `NVIDIA_NIM_MODEL` environment variable, legacy alias.
3. The stored config file, preferring `NVIDIACLAUDE_MODEL` over legacy
   `NVIDIA_NIM_MODEL`.
4. The default model, `minimaxai/minimax-m3`.

Changing the stored model affects the next `nvidiaclaude` run. A process that
is already running keeps the model that was selected when its local proxy
started.

## Update

```bash
nvidiaclaude update
```

The update command uses the branch selected during installation. Override it
for a one-off update:

```bash
NVIDIACLAUDE_INSTALL_REF=dev nvidiaclaude update
```

| Platform      | Where tokens are stored                            |
| ------------- | -------------------------------------------------- |
| macOS/Linux   | `~/.config/nvidiaclaude/config` with perms `600`   |
| Windows       | `%APPDATA%\nvidiaclaude\config` with user-only ACL |

Tokens are stored in plaintext on your machine. Treat them like any other local
credential.

## Provider Endpoint

By default, `nvidiaclaude` uses:

```sh
NVIDIACLAUDE_API_ENDPOINT="https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIACLAUDE_MODEL="minimaxai/minimax-m3"
```

Change the stored provider endpoint without reinstalling:

```bash
nvidiaclaude change-endpoint https://api.tokenrouter.com/v1
nvidiaclaude set-endpoint https://api.tokenrouter.com/v1
```

Show the endpoint that new runs will use:

```bash
nvidiaclaude endpoint
```

Return to the default NVIDIA endpoint:

```bash
nvidiaclaude reset-endpoint
```

The endpoint can be either a provider base URL ending in `/v1` or the full Chat
Completions URL. These two TokenRouter values are equivalent:

```bash
https://api.tokenrouter.com/v1
https://api.tokenrouter.com/v1/chat/completions
```

Internally, `nvidiaclaude` sends requests to `/chat/completions`. If you provide
`https://api.tokenrouter.com/v1`, it is normalized to
`https://api.tokenrouter.com/v1/chat/completions`. For normal use, prefer the
shorter `/v1` form; use the full URL when a provider documents a custom Chat
Completions path.

You can override endpoint or model for a single run:

```bash
NVIDIACLAUDE_MODEL="minimaxai/minimax-m3" nvidiaclaude
NVIDIACLAUDE_API_ENDPOINT="https://api.tokenrouter.com/v1" nvidiaclaude
```

Legacy NVIDIA-specific env names still work:

```bash
NVIDIA_NIM_MODEL="minimaxai/minimax-m3" nvidiaclaude
NVIDIA_NIM_ENDPOINT="https://integrate.api.nvidia.com/v1/chat/completions" nvidiaclaude
```

The endpoint is resolved in this order:

1. `NVIDIACLAUDE_API_ENDPOINT` environment variable for a one-off run.
2. `NVIDIA_NIM_ENDPOINT` environment variable, legacy alias.
3. The stored config file, preferring `NVIDIACLAUDE_API_ENDPOINT` over legacy
   `NVIDIA_NIM_ENDPOINT`.
4. The default NVIDIA endpoint.

### TokenRouter Example

```bash
nvidiaclaude change-endpoint https://api.tokenrouter.com/v1
nvidiaclaude change-model <TOKENROUTER_MODEL>
nvidiaclaude token add <TOKENROUTER_API_KEY>
nvidiaclaude
```

Use the model name exactly as TokenRouter documents it. TokenRouter must expose
an OpenAI-compatible Chat Completions API for the selected model.

## Streaming Heartbeat

Some provider models spend time in an internal thinking phase before the first
visible token. During that wait, `nvidiaclaude` sends Anthropic-compatible SSE
`ping` events so Claude Code can see that the stream is still active.

By default, a ping is sent every 2 seconds while no provider stream chunk is
available. To change the interval for one run:

```bash
NVIDIACLAUDE_STREAM_PING_SECONDS=1 nvidiaclaude
```

To disable heartbeat pings:

```bash
NVIDIACLAUDE_STREAM_PING_SECONDS=0 nvidiaclaude
```

## What It Sets

`nvidiaclaude` starts a local adapter on `127.0.0.1` and sets Claude Code to use
that local Anthropic-compatible endpoint:

```sh
ANTHROPIC_BASE_URL="http://127.0.0.1:<dynamic-port>"
ANTHROPIC_AUTH_TOKEN="nvidiaclaude-local"
ANTHROPIC_MODEL="minimaxai/minimax-m3"
ANTHROPIC_DEFAULT_OPUS_MODEL="minimaxai/minimax-m3"
ANTHROPIC_DEFAULT_SONNET_MODEL="minimaxai/minimax-m3"
ANTHROPIC_DEFAULT_HAIKU_MODEL="minimaxai/minimax-m3"
ANTHROPIC_SMALL_FAST_MODEL="minimaxai/minimax-m3"
CLAUDE_CODE_SUBAGENT_MODEL="minimaxai/minimax-m3"
CLAUDE_CODE_EFFORT_LEVEL="max"
```

Then it runs:

```sh
claude --dangerously-skip-permissions "$@"
```

> `--dangerously-skip-permissions` lets Claude run tools without per-action
> approval prompts. Use it in a directory you trust.

## Uninstall

Preferred:

```bash
nvidiaclaude uninstall
```

Windows PowerShell:

```powershell
nvidiaclaude uninstall
```

The uninstall command stops leftover `nvidiaclaude_proxy.py` processes for the
installed copy, removes installed command files, removes stored config and
tokens, removes temporary `nvidiaclaude` directories, and removes the Windows
user PATH entry added by the PowerShell installer. This project does not
install a systemd, launchd, or Windows service.

Manual fallback for macOS / Linux:

```bash
pkill -f nvidiaclaude_proxy.py 2>/dev/null || true
rm -f ~/.local/bin/nvidiaclaude
rm -f ~/.local/bin/nvidiaclaude_proxy.py
rm -f ~/.local/bin/.nvidiaclaude-install-ref
rm -rf ~/.config/nvidiaclaude
find "${TMPDIR:-/tmp}" -maxdepth 1 -type d -name 'nvidiaclaude.*' -user "$(id -u)" -exec rm -rf {} + 2>/dev/null || true
```

Manual fallback for Windows PowerShell:

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -like '*nvidiaclaude_proxy.py*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\Programs\nvidiaclaude" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "$env:APPDATA\nvidiaclaude" -ErrorAction SilentlyContinue
Get-ChildItem ([IO.Path]::GetTempPath()) -Directory -Filter 'nvidiaclaude-*' -ErrorAction SilentlyContinue |
  Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
```

Check for leftover proxy processes:

macOS / Linux:

```bash
pgrep -af nvidiaclaude_proxy.py
```

Windows PowerShell:

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -like '*nvidiaclaude_proxy.py*' } |
  Select-Object ProcessId, CommandLine
```

This project does not install, update, or remove `mimoclaude`; the two commands
use separate names and separate config directories.
