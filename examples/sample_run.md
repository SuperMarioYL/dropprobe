# Example — a week with DropProbe

This is what using DropProbe looks like on a typical Friday after a carousel drop.

## 1. List the week's drops + your hardware (m1)

```console
$ dropprobe latest --list
DropProbe 0.1.0 — fetching the last 7d of drops...

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

## 2. Smoke-probe each drop (m2)

```console
$ dropprobe latest
# ... fires a 30s test inference per drop via llama.cpp / ollama ...
```

## 3. Copy the runnable command (m3)

The row for the drop you care about ends with a copy-paste `run_cmd`, e.g.:

```bash
llama.cpp/kimi-k3-text -m Q2_K.gguf -c 4096 -n 128 --no-warmup
```

Paste it into your terminal — the model runs. That's the whole point: no fork-hunting, no quant-guessing, per drop, every week.
