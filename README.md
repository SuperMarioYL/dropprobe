[English](./README.en.md) | **简体中文**

<div align="right"><sub><b>简体中文</b>&nbsp;&nbsp;⇄&nbsp;&nbsp;<a href="./README.en.md">English</a></sub></div>

<p align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./assets/hero-cn-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="./assets/hero-cn-light.svg">
  <img src="./assets/hero-cn-light.svg" width="880" alt="DropProbe — 每周开放权重 drop 的一键烟雾测试">
</picture>
</p>

<p align="center"><sub>每周开放权重模型 drop 的一键烟雾测试 —— 在你自己的硬件上 30 秒试跑，告诉你哪个 fork / quant / 配置能跑起来。</sub></p>

<p align="center">
  <a href="./LICENSE"><img src="https://img.shields.io/github/license/SuperMarioYL/dropprobe?color=blue&label=license" alt="license"></a>
  <a href="https://github.com/SuperMarioYL/dropprobe/releases"><img src="https://img.shields.io/github/v/release/SuperMarioYL/dropprobe?label=release" alt="release"></a>
  <a href="https://github.com/SuperMarioYL/dropprobe/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/SuperMarioYL/dropprobe/ci.yml?branch=main&label=ci" alt="ci"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="python">
</p>

**每周都有新的开放权重模型 drop，但你得手动找 fork、猜 GGUF quant、查 day-0 支持。DropProbe 用一条命令对你本机硬件烟雾测试每个新 drop，直接给出能跑的 fork / quant / config。**

<h2><img src="https://api.iconify.design/tabler/topology-star-3.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 架构</h2>

<p align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./assets/atlas-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="./assets/atlas-light.svg">
  <img src="./assets/atlas-light.svg" width="880" alt="架构：lab/HF feed 与硬件检测汇入 smoke-probe，再输出 ProbeCard 报告">
</picture>
</p>

数据流：`drops.py` 从 HF 拉本周 carousel → `hardware.py` 探测本机 VRAM / RAM / 磁盘 → `probe.py` 用最小可行 quant 跑 30 秒试推理 → `report.py` 输出 rich 表 / `--json`。`config_db.yaml` 把每个 drop 的 fork / quant / day-0 工具就绪度喂给探针层。

## 目录

- [为什么造这个](#为什么造这个)
- [安装](#安装)
- [快速开始](#快速开始)
- [用法](#用法)
- [Demo](#demo)
- [路线图](#路线图)
- [License](#license)

<h2><img src="https://api.iconify.design/tabler/bulb.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 为什么造这个</h2>

r/LocalLLaMA 有句话说「the open-weights carousel never stops」—— DeepSeek、Kimi、GLM、Qwen、MiniMax 几乎每周轮替 drop，但每个 drop 你都得手动重做一遍：哪个 llama.cpp fork 支持它、哪个 GGUF quant 放得进你的 VRAM、ComfyUI / llama.cpp 有没有加 day-0 支持。最痛的案例是有人因为「在我的机器上没法试」干脆自己用 C99 写了个推理引擎。DropProbe 把这套重复的体力活压成一条命令：在你**真实的硬件**上对每个新 drop 跑 30 秒试推理，吐出一张能直接复制运行命令的 ProbeCard 表。静态 VRAM 算术只能告诉你 quant 放不放得下；烟雾测试能告诉你 fork **到底跑不跑得起来**。

<h2><img src="https://api.iconify.design/tabler/rocket.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 安装</h2>

```bash
# 推荐用 uv（< 30 秒，不在安装期拉任何模型权重）
uv tool install dropprobe
# 或用 pipx
pipx install dropprobe
```

> 需要本机有 `llama.cpp`（`llama-cli`）或 `ollama` 在 PATH 上。m2 烟雾测试会自动选一个；两个都没有时退化为只列出 drop + 硬件画像（m1 行为）。

<h2><img src="https://api.iconify.design/tabler/rocket.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 快速开始</h2>

```bash
# 1. 安装
uv tool install dropprobe
# 2. 列出本周 drop + 你的硬件画像（m1 —— 还不跑探针）
dropprobe latest --list
# 3. （m2 起）跑烟雾测试，复制能跑的运行命令
dropprobe latest
```

<details><summary>样例输出（m1 <code>--list</code>）</summary>

```
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

</details>

<h2><img src="https://api.iconify.design/tabler/terminal-2.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 用法</h2>

```bash
# 只看本周 carousel + 本机硬件（m1 已可用 —— 探针在 m2）
dropprobe latest --list

# 指定回看窗口（默认 7 天，carousel 节奏）
dropprobe latest --list --window 14

# 指定模型缓存目录（用于测量真实可用磁盘）
dropprobe latest --list --cache-dir /data/hf

# m2 起：跑 30 秒烟雾测试，每个 drop 出一张 ProbeCard
dropprobe latest

# m3 起：导出完整 JSON 报告
dropprobe latest --json > report.json

# 版本
dropprobe --version
```

核心数据原语是 **ProbeCard** —— 每个 drop 一条可运行配置记录：

| 字段 | 含义 |
|---|---|
| `model_id` / `lab` / `drop_date` | 模型标识与发布信息 |
| `hardware_profile` | 本机 VRAM / RAM / GPU 架构 / 磁盘 |
| `quant` | 适配的 GGUF quant（名 / 体积 / 来源仓库，如 `Q2_K` 自 `GrEarl/Kimi-K3-GGUF`） |
| `backend` | 跑得动的后端 fork（如 `pwilkin/llama.cpp` `kimi-k3-text`） |
| `tooling` | day-0 工具就绪度（comfyui / llama_cpp / ollama） |
| `runnable` / `smoke_probe_ok` | 烟雾测试结果 |
| `run_cmd` | 可直接复制粘贴的运行命令 |

<h2><img src="https://api.iconify.design/tabler/photo.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> Demo</h2>

<p align="center"><img src="./assets/demo.gif" width="880" alt="dropprobe latest --list 演示"></p>

原始录制在 `assets/demo.cast`（asciinema 格式）；`docs/demo.tape` 是可重放的 vhs 脚本，`.github/workflows/demo.yml` 按需重渲染 gif。

<h2><img src="https://api.iconify.design/tabler/map-2.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 路线图</h2>

- [x] **m1 · 抓取 drop** —— 从 HF / lab 列表拉本周 carousel + 探测本机硬件；`dropprobe latest --list` 打印 drop + 硬件画像。
- [ ] **m2 · 烟雾测试** —— 从 config_db 选最小可行 quant + 后端 fork，用 llama.cpp / ollama 跑 30 秒试推理，记录 `runnable` / `smoke_probe_ok`；`dropprobe latest` 跑探针。
- [ ] **m3 · 出报告** —— 打印完整 ProbeCard 表（模型 / 适配 quant / VRAM / fork / 工具就绪 / 运行命令）+ `dropprobe latest --json` 导出。
- [ ] 未来 —— 社区 PR 流水线给 config_db 加 drop 行（这是计划里盯着的「真实使用」信号）。

<h2><img src="https://api.iconify.design/tabler/license.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> License</h2>

MIT —— 见 [LICENSE](./LICENSE)。提 issue 或 PR 欢迎在 [GitHub Issues](https://github.com/SuperMarioYL/dropprobe/issues)。

<p align="center"><sub><a href="./LICENSE">MIT</a> © 2026 SuperMarioYL</sub></p>
