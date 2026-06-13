# nvidiaclaude

Run [Claude Code](https://docs.claude.com/en/docs/claude-code) against
NVIDIA NIM through a local Anthropic-compatible adapter.

Install once, enter your NVIDIA API key once, and then run `nvidiaclaude`.
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
curl -fsSL https://raw.githubusercontent.com/fadhluibnu/nvidiaclaude/dev/install.sh | bash
```

Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/fadhluibnu/nvidiaclaude/dev/install.ps1 | iex
```

The beta install uses the `dev` branch, so the `dev` branch must be pushed to
GitHub before those URLs work.

Installs `nvidiaclaude` and `nvidiaclaude_proxy.py` into `~/.local/bin` on
macOS/Linux, or `%LOCALAPPDATA%\Programs\nvidiaclaude` on Windows. If the
install directory is not on your `PATH`, the installer prints the next step.

## Use

First run asks for your NVIDIA API key and saves it:

```bash
nvidiaclaude
```

Every run after that uses the same key. Any arguments pass through to `claude`:

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
nvidiaclaude reset
```

`config` saves or replaces the NVIDIA API key without a prompt. `change-key`
can prompt securely when no key is provided. `reset` removes the stored key
without removing the stored model.

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

`update` re-runs the installer from the main branch. `commands` prints the
nvidiaclaude command reference. Aliases for `commands`: `help`,
`--help-nvidiaclaude`.

### Environment Overrides

```bash
NVIDIA_API_KEY=<KEY> nvidiaclaude
NVIDIA_NIM_MODEL=<MODEL> nvidiaclaude
NVIDIA_NIM_ENDPOINT=<URL> nvidiaclaude
NVIDIACLAUDE_STREAM_PING_SECONDS=<SECONDS> nvidiaclaude
NVIDIACLAUDE_BIN_DIR=<DIR> ./install.sh
```

`NVIDIA_API_KEY` is saved for next time if no key is stored yet.
`NVIDIA_NIM_MODEL` and `NVIDIA_NIM_ENDPOINT` override config for one run.
`NVIDIACLAUDE_STREAM_PING_SECONDS` controls stream heartbeat pings while
waiting for NVIDIA NIM chunks. Set it to `0` to disable pings.
`NVIDIACLAUDE_BIN_DIR` changes where the shell installer writes files.

### Config Paths

| Platform      | Path                                               |
| ------------- | -------------------------------------------------- |
| macOS/Linux   | `~/.config/nvidiaclaude/config`                    |
| Windows       | `%APPDATA%\nvidiaclaude\config`                    |

### Ways to provide the key

The key is resolved in this order:

1. `nvidiaclaude config <KEY>` - set it inline, no prompt.
2. The stored config file - set on a previous run.
3. `NVIDIA_API_KEY` environment variable - used and saved for next time.
4. Interactive prompt - asked for automatically if none of the above is set.

## Manage Your Key

```bash
nvidiaclaude change-key        # change the stored key interactively
nvidiaclaude change-key <KEY>  # change the key without a prompt
nvidiaclaude reset             # delete the stored key
```

`config`, `set-key`, and `change` are accepted as aliases for `change-key`.

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

| Platform      | Where the key is stored                            |
| ------------- | -------------------------------------------------- |
| macOS/Linux   | `~/.config/nvidiaclaude/config` with perms `600`   |
| Windows       | `%APPDATA%\nvidiaclaude\config` with user-only ACL |

It is stored in plaintext on your machine. Treat it like any other local
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
rm -rf ~/.config/nvidiaclaude
```

Windows PowerShell:

```powershell
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\Programs\nvidiaclaude"
Remove-Item -Recurse -Force "$env:APPDATA\nvidiaclaude"
```

This project does not install, update, or remove `mimoclaude`; the two commands
use separate names and separate config directories.
