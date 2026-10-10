# Example — a week with DropProbe

This is what using DropProbe looks like on a typical Friday after a carousel drop.

## 1. List the week's drops + your hardware

```console
$ dropprobe latest --list
DropProbe 0.3.0 — fetching the last 7d of drops...

This week's open-weight drops
 Model                                  Lab       Drop date   Files
 moonshotai/Kimi-K3-Instruct           Kimi      2026-08-01    14
 deepseek-ai/DeepSeek-V4-Flash         DeepSeek  2026-07-30    22
 zhipuai/GLM-5.5-9B-Chat               GLM       2026-07-29     8
 Qwen/Qwen3-Next-80B                   Qwen      2026-07-27    19
 MiniMaxAI/MiniMax-H3                  MiniMax   2026-07-26    31

Your hardware
 Axis             Value
 GPU arch         nvidia
 GPU              NVIDIA GeForce RTX 5090
 GPU count        2
 VRAM (GiB)       48.0
 RAM (GiB)        128.0
 Disk free (GiB)  512.0
```

## 2. Probe status

`dropprobe latest` assembles a ProbeCard per drop, but live inference probing
is not wired in yet. When no probe has run, the command falls back to the
drops + hardware view and says so:

```console
$ dropprobe latest
DropProbe 0.3.0 — fetching the last 7d of drops...
  (no probe ran — showing drops + hardware for now)

This week's open-weight drops
 ...
```

## 3. Read the candidate run command

Each ProbeCard (visible via `dropprobe latest --json`) carries a candidate
`run_cmd` assembled from the bundled config DB, e.g.:

```bash
llama.cpp/kimi-k3-text -m Q2_K.gguf -c 4096 -n 128 --no-warmup
```

These are maintainer-curated templates, not validated commands — check the
actual backend arguments before running one. The static fit verdict (`runnable`)
tells you whether the candidate quant fits your hardware; the final "it runs"
check is still yours.
