# nvidiaclaude

Run [Claude Code](https://docs.claude.com/en/docs/claude-code) against
NVIDIA NIM through a local Anthropic-compatible adapter.

Install once, enter your NVIDIA API key once, and then run `nvidiaclaude`.
The command starts a local proxy, points Claude Code at it, and forwards the
requests to NVIDIA NIM.

> Requires the `claude` CLI and Python 3 to already be installed.

## Install

### macOS / Linux

```bash
curl -fsSL https://raw.githubusercontent.com/fadhluibnu/nvidiaclaude/main/install.sh | bash
```

Installs `nvidiaclaude` and `nvidiaclaude_proxy.py` into `~/.local/bin`. If
that directory is not on your `PATH`, the installer prints the line to add.

### Windows (PowerShell)

```powershell
irm https://raw.githubusercontent.com/fadhluibnu/nvidiaclaude/main/install.ps1 | iex
```

Installs `nvidiaclaude` into `%LOCALAPPDATA%\Programs\nvidiaclaude` and adds it
to your user `PATH`. Open a new terminal afterward.

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
