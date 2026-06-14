# nvidiaclaude

Run [Claude Code](https://docs.claude.com/en/docs/claude-code) against
NVIDIA NIM through a local Anthropic-compatible adapter.

Install once, add one or more NVIDIA API tokens, and then run `nvidiaclaude`.
The command starts a local proxy, points Claude Code at it, and forwards the
requests to NVIDIA NIM.

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

First run asks for your NVIDIA API token and saves it:

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

Starts Claude Code through the local NVIDIA NIM adapter. Extra arguments pass
through to the `claude` CLI.

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
`reset` removes all stored tokens without removing the stored model.

### Model

```bash
nvidiaclaude change-model <MODEL>
nvidiaclaude set-model <MODEL>
nvidiaclaude model
nvidiaclaude reset-model
```

Use `change-model` or `set-model` to persist a model. Use `model` to show the
model new runs will use. Use `reset-model` to return to the default model.

### Maintenance

```bash
nvidiaclaude update
nvidiaclaude commands
```

`update` re-runs the installer from the selected install branch. `commands`
prints the nvidiaclaude command reference. Aliases for `commands`: `help`,
`--help-nvidiaclaude`.

### Environment Overrides

```bash
NVIDIA_API_KEY=<KEY> nvidiaclaude
NVIDIA_API_KEYS=<KEY1>,<KEY2> nvidiaclaude
NVIDIA_NIM_MODEL=<MODEL> nvidiaclaude
NVIDIA_NIM_ENDPOINT=<URL> nvidiaclaude
NVIDIACLAUDE_STREAM_PING_SECONDS=<SECONDS> nvidiaclaude
NVIDIACLAUDE_TOKEN_COOLDOWN_SECONDS=<SECONDS> nvidiaclaude
NVIDIACLAUDE_INSTALL_REF=dev nvidiaclaude update
NVIDIACLAUDE_BIN_DIR=<DIR> ./install.sh
```

`NVIDIA_API_KEY` or `NVIDIA_API_KEYS` is saved for next time if no token is
stored yet.
`NVIDIA_NIM_MODEL` and `NVIDIA_NIM_ENDPOINT` override config for one run.
`NVIDIACLAUDE_STREAM_PING_SECONDS` controls stream heartbeat pings while
waiting for NVIDIA NIM chunks. Set it to `0` to disable pings.
`NVIDIACLAUDE_TOKEN_COOLDOWN_SECONDS` controls how long a failed token is
avoided after rate-limit or token auth errors. Default: `60`.
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
2. `NVIDIA_API_KEYS` environment variable, comma-separated.
3. `NVIDIA_API_KEY` environment variable.
4. Interactive prompt - asked for automatically if none of the above is set.

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

- HTTP `429`
- quota or rate-limit messages
- invalid, expired, unauthorized, or forbidden token responses

For non-streaming requests, retry is transparent to Claude Code. For streaming
responses, retry is safe before content output starts. If a token fails after
partial streaming output, the proxy returns an SSE error for that response,
marks the token as limited when possible, and uses another token on the next
request.

## Manage Your Model

Change the stored NVIDIA NIM model without reinstalling:

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

1. `NVIDIA_NIM_MODEL` environment variable for a one-off run.
2. The stored config file.
3. The default model, `minimaxai/minimax-m3`.

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

## NVIDIA NIM Settings

By default, `nvidiaclaude` uses:

```sh
NVIDIA_NIM_ENDPOINT="https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIA_NIM_MODEL="minimaxai/minimax-m3"
```

You can override either setting for a single run:

```bash
NVIDIA_NIM_MODEL="minimaxai/minimax-m3" nvidiaclaude
NVIDIA_NIM_ENDPOINT="https://integrate.api.nvidia.com/v1/chat/completions" nvidiaclaude
```

To persist a model choice:

```bash
nvidiaclaude change-model minimaxai/minimax-m3
```

## Streaming Heartbeat

Some NVIDIA NIM models spend time in an internal thinking phase before the
first visible token. During that wait, `nvidiaclaude` sends Anthropic-compatible
SSE `ping` events so Claude Code can see that the stream is still active.

By default, a ping is sent every 2 seconds while no NVIDIA NIM stream chunk is
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

macOS / Linux:

```bash
rm ~/.local/bin/nvidiaclaude
rm ~/.local/bin/nvidiaclaude_proxy.py
rm ~/.local/bin/.nvidiaclaude-install-ref
rm -rf ~/.config/nvidiaclaude
```

Windows PowerShell:

```powershell
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\Programs\nvidiaclaude"
Remove-Item -Recurse -Force "$env:APPDATA\nvidiaclaude"
```

This project does not install, update, or remove `mimoclaude`; the two commands
use separate names and separate config directories.
