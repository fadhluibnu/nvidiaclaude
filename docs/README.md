# nvidiaclaude Project Manual

`nvidiaclaude` adalah wrapper untuk menjalankan Claude Code dengan provider API
yang bisa berbeda dari Anthropic resmi. Tujuan utamanya adalah memberi satu
command sederhana, `nvidiaclaude`, yang menyiapkan token, model, endpoint,
proxy lokal, failover token, dan konfigurasi Claude Code.

Project ini mendukung dua tipe upstream:

- OpenAI-compatible Chat Completions, seperti NVIDIA NIM atau gateway lain yang
  menyediakan endpoint `/v1/chat/completions`.
- Anthropic-compatible Messages API, seperti endpoint `/v1/messages`.

Claude Code tetap berbicara ke endpoint Anthropic lokal di `127.0.0.1`. Proxy
lokal kemudian memilih cara bicara ke provider upstream berdasarkan provider
mode yang aktif.

## Cara Kerja

Alur normal:

1. User menjalankan `nvidiaclaude`.
2. Wrapper membaca config lokal, environment variable, atau meminta token saat
   first-time setup.
3. Wrapper menjalankan `nvidiaclaude_proxy.py` di port lokal dinamis.
4. Wrapper mengatur environment Claude Code, terutama:
   - `ANTHROPIC_BASE_URL=http://127.0.0.1:<port>`
   - `ANTHROPIC_AUTH_TOKEN=nvidiaclaude-local`
   - `ANTHROPIC_MODEL=<model-terpilih>`
5. Claude Code mengirim request Anthropic Messages API ke proxy lokal.
6. Proxy meneruskan request ke provider upstream:
   - mode `openai`: request dikonversi ke OpenAI Chat Completions.
   - mode `anthropic`: request diteruskan sebagai Anthropic Messages API native.
7. Response upstream dikembalikan ke Claude Code dalam format Anthropic.

Proxy lokal tetap dipakai untuk mode Anthropic native supaya fitur failover
token, cooldown token, dan local rate-limit tetap bekerja.

## File Utama

- `nvidiaclaude`: wrapper macOS/Linux.
- `nvidiaclaude.ps1`: wrapper Windows PowerShell.
- `nvidiaclaude_proxy.py`: proxy lokal Anthropic-compatible.
- `install.sh`: installer macOS/Linux.
- `install.ps1`: installer Windows.
- `tests/test_proxy_failover.py`: unit test proxy, failover, provider mode, dan
  rate-limit behavior.
- `docs/`: dokumentasi lengkap.

## Provider Mode

Provider mode menentukan format request upstream.

| Mode | Kegunaan |
| --- | --- |
| `auto` | Default. Mendeteksi endpoint Anthropic native dari host/path, selain itu memakai OpenAI-compatible. |
| `openai` | Paksa OpenAI Chat Completions conversion. Cocok untuk NVIDIA NIM dan gateway OpenAI-compatible. |
| `anthropic` | Paksa Anthropic Messages API native pass-through. Cocok untuk endpoint `/v1/messages`. |

Command:

```bash
nvidiaclaude provider-mode
nvidiaclaude provider-mode auto
nvidiaclaude provider-mode openai
nvidiaclaude provider-mode anthropic
nvidiaclaude reset-provider-mode
```

Environment override:

```bash
NVIDIACLAUDE_PROVIDER_MODE=anthropic nvidiaclaude
```

Default yang direkomendasikan adalah `auto`. Gunakan mode manual jika gateway
custom salah terdeteksi.

Detail provider ada di [providers.md](providers.md).

## Endpoint dan Model

Default:

```bash
NVIDIACLAUDE_API_ENDPOINT=https://integrate.api.nvidia.com/v1/chat/completions
NVIDIACLAUDE_MODEL=minimaxai/minimax-m3
```

Command:

```bash
nvidiaclaude change-endpoint <URL>
nvidiaclaude endpoint
nvidiaclaude reset-endpoint

nvidiaclaude change-model <MODEL>
nvidiaclaude model
nvidiaclaude reset-model
```

Endpoint OpenAI-compatible bisa berupa root, `/v1`, atau full
`/v1/chat/completions`. Endpoint Anthropic-compatible bisa berupa root, `/v1`,
atau full `/v1/messages` saat provider mode efektif adalah `anthropic`.

Contoh OpenAI-compatible:

```bash
nvidiaclaude change-endpoint https://api.tokenrouter.com/v1
nvidiaclaude provider-mode openai
```

Contoh Anthropic-compatible:

```bash
nvidiaclaude change-endpoint https://api.anthropic.com/v1
nvidiaclaude provider-mode anthropic
```

## Token

Token disimpan di config lokal dalam plaintext dengan permission user-only
semampu platform.

Command:

```bash
nvidiaclaude token add
nvidiaclaude token add <KEY>
nvidiaclaude token list
nvidiaclaude token remove <INDEX>
nvidiaclaude token clear
nvidiaclaude reset
```

Urutan token:

1. Config lokal.
2. `NVIDIACLAUDE_API_KEYS`.
3. `NVIDIACLAUDE_API_KEY`.
4. `NVIDIA_API_KEYS`.
5. `NVIDIA_API_KEY`.
6. `ANTHROPIC_API_KEY`.
7. Prompt interaktif.

Jika beberapa token dikonfigurasi, proxy mencoba token berikutnya saat token
aktif gagal karena auth, quota, atau rate-limit response.

## Failover Token

Failover terjadi untuk:

- HTTP `401` atau `403`.
- Pesan invalid token, expired token, unauthorized, forbidden, authentication.
- Quota error.
- HTTP `429` atau pesan rate limit/RPM.

Jika sebuah token gagal, token itu diberi cooldown sementara. Default cooldown:

```bash
NVIDIACLAUDE_TOKEN_COOLDOWN_SECONDS=60
```

Untuk response non-streaming, failover bisa terjadi sebelum response dikirim ke
Claude Code. Untuk streaming, failover aman sebelum upstream mulai mengirim
content. Jika upstream error setelah content sebagian sudah dikirim, proxy
mengirim SSE error untuk request itu dan menandai token bermasalah.

## Rate Limit Lokal

Proxy punya proactive RPM limiter untuk menghindari provider terkena limit,
terutama limit 40 RPM. Default lama tetap dipertahankan:

```bash
NVIDIACLAUDE_RATE_LIMIT_MODE=wait
NVIDIACLAUDE_RATE_LIMIT_RPM=38
NVIDIACLAUDE_RATE_LIMIT_SCOPE=global
NVIDIACLAUDE_RATE_LIMIT_WINDOW_SECONDS=60
```

Mode:

| Mode | Perilaku |
| --- | --- |
| `wait` | Default. Request menunggu diam-diam saat bucket lokal penuh. |
| `fail-fast` | Tidak ada pending request; proxy membalas 429 lokal saat bucket penuh. |
| `off` | Local proactive throttle dimatikan; provider bisa langsung membalas 429. |

Command:

```bash
nvidiaclaude rate-limit status
nvidiaclaude rate-limit wait 38
nvidiaclaude rate-limit fail-fast 38
nvidiaclaude rate-limit off
nvidiaclaude rate-limit reset
```

Rekomendasi untuk menghindari pending request tanpa melewati 40 RPM:

```bash
nvidiaclaude rate-limit fail-fast 38
```

Detail tradeoff ada di [rate-limits.md](rate-limits.md).

## Environment Variables

Umum:

```bash
NVIDIACLAUDE_API_KEY=<KEY>
NVIDIACLAUDE_API_KEYS=<KEY1>,<KEY2>
ANTHROPIC_API_KEY=<KEY>
NVIDIACLAUDE_API_ENDPOINT=<URL>
NVIDIACLAUDE_PROVIDER_MODE=auto|openai|anthropic
NVIDIACLAUDE_MODEL=<MODEL>
```

Rate-limit:

```bash
NVIDIACLAUDE_RATE_LIMIT_MODE=wait|fail-fast|off
NVIDIACLAUDE_RATE_LIMIT_RPM=38
NVIDIACLAUDE_RATE_LIMIT_SCOPE=global|per-token
NVIDIACLAUDE_RATE_LIMIT_WINDOW_SECONDS=60
NVIDIACLAUDE_TOKEN_COOLDOWN_SECONDS=60
```

Streaming:

```bash
NVIDIACLAUDE_STREAM_PING_SECONDS=2
```

Install/update:

```bash
NVIDIACLAUDE_INSTALL_REF=dev
NVIDIACLAUDE_BIN_DIR=$HOME/.local/bin
```

Legacy NVIDIA aliases tetap didukung:

```bash
NVIDIA_API_KEY=<KEY>
NVIDIA_API_KEYS=<KEY1>,<KEY2>
NVIDIA_NIM_ENDPOINT=<URL>
NVIDIA_NIM_MODEL=<MODEL>
```

## Config Paths

| Platform | Path |
| --- | --- |
| macOS/Linux | `~/.config/nvidiaclaude/config` |
| Windows | `%APPDATA%\nvidiaclaude\config` |

Environment variable mengalahkan config file untuk run tersebut. Command
seperti `change-model`, `change-endpoint`, `provider-mode`, dan `rate-limit`
menyimpan nilai untuk run berikutnya.

## Install dan Update

macOS/Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/fadhluibnu/nvidiaclaude/main/install.sh | bash
```

Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/fadhluibnu/nvidiaclaude/main/install.ps1 | iex
```

Update:

```bash
nvidiaclaude update
```

Beta/dev branch:

```bash
NVIDIACLAUDE_INSTALL_REF=dev nvidiaclaude update
```

## Security Notes

- Token disimpan plaintext di mesin lokal. Perlakukan config file seperti file
  rahasia.
- Proxy hanya bind ke `127.0.0.1` secara default.
- Wrapper menjalankan Claude Code dengan `--dangerously-skip-permissions` agar
  workflow coding tidak meminta approval tool berulang. Jalankan hanya di
  folder yang dipercaya.
- Jangan commit config lokal atau token.

## Development

Test utama:

```bash
python3 -m unittest tests/test_proxy_failover.py
```

Syntax check wrapper:

```bash
bash -n nvidiaclaude install.sh
```

PowerShell parse check jika `pwsh` tersedia:

```powershell
pwsh -NoProfile -Command { $null = [scriptblock]::Create((Get-Content .\nvidiaclaude.ps1 -Raw)) }
```

## Troubleshooting

Jika Claude Code tidak ditemukan:

```bash
claude --version
```

Jika proxy gagal start, wrapper akan menampilkan log proxy sementara. Biasanya
penyebabnya Python tidak tersedia, file `nvidiaclaude_proxy.py` tidak berada di
sebelah wrapper, atau env token kosong.

Jika endpoint OpenAI-compatible salah diperlakukan sebagai Anthropic:

```bash
nvidiaclaude provider-mode openai
```

Jika endpoint Anthropic-compatible salah diperlakukan sebagai OpenAI:

```bash
nvidiaclaude provider-mode anthropic
```

Jika terminal terasa menggantung karena request menunggu limit lokal:

```bash
nvidiaclaude rate-limit fail-fast 38
```

Jika ingin provider yang menentukan limit sepenuhnya:

```bash
nvidiaclaude rate-limit off
```
