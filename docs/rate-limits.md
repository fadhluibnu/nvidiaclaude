# Rate Limit Guide

`nvidiaclaude` punya local proactive RPM limiter di proxy. Tujuannya adalah
mengurangi kemungkinan provider upstream membalas `429 Too Many Requests`,
terutama untuk provider dengan limit sekitar 40 request per menit.

Default:

```bash
NVIDIACLAUDE_RATE_LIMIT_MODE=wait
NVIDIACLAUDE_RATE_LIMIT_RPM=38
NVIDIACLAUDE_RATE_LIMIT_SCOPE=global
NVIDIACLAUDE_RATE_LIMIT_WINDOW_SECONDS=60
```

Angka 38 dipakai sebagai margin di bawah 40 RPM.

## Command

```bash
nvidiaclaude rate-limit status
nvidiaclaude rate-limit wait [RPM]
nvidiaclaude rate-limit fail-fast [RPM]
nvidiaclaude rate-limit off
nvidiaclaude rate-limit reset
```

Contoh:

```bash
nvidiaclaude rate-limit fail-fast 38
```

## Mode

| Mode | Perilaku | Dampak |
| --- | --- | --- |
| `wait` | Request menunggu diam-diam saat bucket lokal penuh. | Paling aman untuk provider, tapi request bisa terlihat pending. |
| `fail-fast` | Proxy langsung membalas local 429 saat bucket lokal penuh. | Tidak ada pending request, tetap menjaga limit lokal. |
| `off` | Local proactive throttle dimatikan. | Tidak ada pending lokal, tapi provider bisa kena 429. |

## Rekomendasi

Untuk kebutuhan "jangan ada pending request tapi tetap jangan kena limit 40
RPM", gunakan:

```bash
nvidiaclaude rate-limit fail-fast 38
```

Alasannya:

- request tidak ditahan oleh proxy;
- provider tidak menerima request saat bucket lokal penuh;
- Claude Code mendapat error cepat dan bisa berhenti atau retry sesuai
  perilaku client;
- margin 38 memberi ruang kecil dari limit 40 RPM.

Gunakan `off` hanya jika:

- provider/gateway sudah punya queue sendiri;
- ingin throughput maksimum dan siap menerima 429 dari provider;
- sedang debug dan local limiter mengganggu observasi.

## Scope

Scope dikontrol dengan:

```bash
NVIDIACLAUDE_RATE_LIMIT_SCOPE=global
NVIDIACLAUDE_RATE_LIMIT_SCOPE=per-token
```

`global` berarti semua token berbagi satu bucket RPM. Ini default yang aman
untuk provider yang menghitung limit per akun, project, atau gateway.

`per-token` berarti setiap token punya bucket sendiri. Gunakan hanya jika
provider memastikan limit benar-benar per token. Jika provider menghitung limit
secara global, `per-token` bisa membuat total request melewati limit provider.

## Window

Window dikontrol dengan:

```bash
NVIDIACLAUDE_RATE_LIMIT_WINDOW_SECONDS=60
```

Default 60 detik sesuai konsep RPM. Untuk test lokal bisa dibuat kecil, tapi
untuk penggunaan normal sebaiknya tetap 60.

## Cooldown vs Rate Limit

Ada dua mekanisme yang berbeda:

1. Local proactive RPM limiter.
2. Token cooldown setelah provider mengembalikan auth/quota/rate-limit error.

Cooldown dikontrol dengan:

```bash
NVIDIACLAUDE_TOKEN_COOLDOWN_SECONDS=60
```

Jika provider membalas `429`, token tersebut ditandai cooling down. Jika ada
token lain, proxy mencoba token berikutnya. Jika semua token cooling down, proxy
mengembalikan error yang menjelaskan kapan token mungkin tersedia lagi.

## Contoh Setup

Default aman:

```bash
nvidiaclaude rate-limit reset
```

Tidak pending, tetap menjaga batas 40 RPM:

```bash
nvidiaclaude rate-limit fail-fast 38
```

Provider menentukan semua limit:

```bash
nvidiaclaude rate-limit off
```

Token punya limit masing-masing:

```bash
NVIDIACLAUDE_RATE_LIMIT_SCOPE=per-token nvidiaclaude
```

## Troubleshooting

Jika request terlihat diam lama, cek mode:

```bash
nvidiaclaude rate-limit status
```

Jika `mode=wait`, request memang bisa menunggu ketika bucket lokal penuh.
Ubah ke:

```bash
nvidiaclaude rate-limit fail-fast 38
```

Jika masih kena provider 429 saat mode `fail-fast`, kemungkinan:

- RPM provider lebih rendah dari 38;
- provider menghitung request dari aplikasi lain juga;
- provider menghitung limit per akun/project, bukan hanya per token;
- `NVIDIACLAUDE_RATE_LIMIT_SCOPE=per-token` dipakai padahal limit provider
  sebenarnya global.

Turunkan RPM:

```bash
nvidiaclaude rate-limit fail-fast 30
```

Jika provider memberi `Retry-After`, proxy memakai nilai itu untuk cooldown
token. Jika tidak ada, proxy memakai `NVIDIACLAUDE_TOKEN_COOLDOWN_SECONDS`.
