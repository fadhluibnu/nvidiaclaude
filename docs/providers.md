# Provider Guide

Dokumen ini menjelaskan cara memilih endpoint dan provider mode.

## Ringkasan Mode

`nvidiaclaude` selalu membuat Claude Code berbicara ke proxy lokal. Yang
berubah adalah format request dari proxy lokal ke provider upstream.

| Provider mode | Upstream format | Cocok untuk |
| --- | --- | --- |
| `auto` | Dideteksi otomatis | Default untuk kebanyakan user |
| `openai` | OpenAI Chat Completions | NVIDIA NIM, TokenRouter, gateway OpenAI-compatible |
| `anthropic` | Anthropic Messages API | Anthropic API atau gateway Anthropic-compatible |

Command:

```bash
nvidiaclaude provider-mode
nvidiaclaude provider-mode auto
nvidiaclaude provider-mode openai
nvidiaclaude provider-mode anthropic
nvidiaclaude reset-provider-mode
```

Env one-off:

```bash
NVIDIACLAUDE_PROVIDER_MODE=anthropic nvidiaclaude
```

## Auto Detection

Mode `auto` memilih `anthropic` jika endpoint terlihat seperti Anthropic-native:

- host `api.anthropic.com`
- host `api.claude.com`
- host subdomain `*.anthropic.com`
- path berakhir dengan `/messages`

Selain itu, mode efektif menjadi `openai`.

Jika gateway custom memakai host umum tetapi path Anthropic-compatible, gunakan
URL lengkap:

```bash
nvidiaclaude change-endpoint https://gateway.example/v1/messages
nvidiaclaude provider-mode auto
```

Jika masih salah deteksi, paksa mode:

```bash
nvidiaclaude provider-mode anthropic
```

## OpenAI-Compatible Providers

Mode `openai` menerima request Anthropic dari Claude Code, lalu mengubahnya ke
OpenAI Chat Completions.

Endpoint yang diterima:

```text
https://provider.example
https://provider.example/v1
https://provider.example/v1/chat/completions
```

Normalisasi:

| Input | Upstream request |
| --- | --- |
| `https://provider.example` | `https://provider.example/v1/chat/completions` |
| `https://provider.example/v1` | `https://provider.example/v1/chat/completions` |
| `https://provider.example/v1/chat/completions` | tidak diubah |

Auth upstream:

```text
Authorization: Bearer <token>
```

Contoh NVIDIA NIM:

```bash
nvidiaclaude change-endpoint https://integrate.api.nvidia.com/v1/chat/completions
nvidiaclaude change-model minimaxai/minimax-m3
nvidiaclaude provider-mode openai
nvidiaclaude token add <NVIDIA_OR_GATEWAY_KEY>
nvidiaclaude
```

Contoh gateway OpenAI-compatible:

```bash
nvidiaclaude change-endpoint https://api.tokenrouter.com/v1
nvidiaclaude change-model <GATEWAY_MODEL>
nvidiaclaude provider-mode openai
nvidiaclaude token add <GATEWAY_KEY>
nvidiaclaude
```

## Anthropic-Compatible Providers

Mode `anthropic` meneruskan request Claude Code sebagai Messages API native.
Proxy tetap mengganti `model` sesuai `NVIDIACLAUDE_MODEL`, supaya command
`change-model` tetap menjadi sumber konfigurasi utama.

Endpoint yang diterima:

```text
https://api.anthropic.com
https://api.anthropic.com/v1
https://api.anthropic.com/v1/messages
```

Normalisasi:

| Input | Upstream request |
| --- | --- |
| `https://api.anthropic.com` | `https://api.anthropic.com/v1/messages` |
| `https://api.anthropic.com/v1` | `https://api.anthropic.com/v1/messages` |
| `https://api.anthropic.com/v1/messages` | tidak diubah |

Auth upstream:

```text
x-api-key: <token>
anthropic-version: 2023-06-01
```

Header Anthropic dari request Claude Code seperti `anthropic-beta` ikut
diteruskan.

Contoh Anthropic API:

```bash
nvidiaclaude change-endpoint https://api.anthropic.com/v1
nvidiaclaude change-model claude-sonnet-4-5
nvidiaclaude provider-mode anthropic
nvidiaclaude token add <ANTHROPIC_API_KEY>
nvidiaclaude
```

Atau one-off:

```bash
ANTHROPIC_API_KEY=<KEY> \
NVIDIACLAUDE_API_ENDPOINT=https://api.anthropic.com/v1 \
NVIDIACLAUDE_PROVIDER_MODE=anthropic \
NVIDIACLAUDE_MODEL=claude-sonnet-4-5 \
nvidiaclaude
```

## Choosing a Mode

Gunakan `auto` jika:

- endpoint first-party Anthropic atau path jelas `/messages`;
- endpoint OpenAI-compatible standar;
- tidak ada gateway custom yang ambigu.

Gunakan `openai` jika:

- provider docs menyebut OpenAI-compatible;
- provider docs memakai `/v1/chat/completions`;
- auto salah menganggap gateway sebagai Anthropic.

Gunakan `anthropic` jika:

- provider docs menyebut Anthropic Messages API;
- provider docs memakai `/v1/messages`;
- ingin memakai API Anthropic resmi melalui failover/rate-limit lokal
  nvidiaclaude.

## Dampak Arsitektur

Mode Anthropic tetap lewat proxy lokal, bukan bypass langsung, karena:

- token failover tetap tersedia;
- cooldown token tetap konsisten;
- local rate-limit `wait`, `fail-fast`, dan `off` tetap berlaku;
- wrapper tetap punya satu cara setup Claude Code.

Tradeoff-nya: ada satu hop lokal tambahan. Hop ini berada di `127.0.0.1` dan
tidak mengubah payload Anthropic selain field `model` serta header auth
upstream.
