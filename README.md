[English](README.en.md) | **简体中文**

<picture>
  <source media="(max-width: 640px) and (prefers-color-scheme: dark)" srcset="assets/presentation/hero-mobile-dark.svg">
  <source media="(max-width: 640px)" srcset="assets/presentation/hero-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="assets/presentation/hero-dark.svg">
  <img src="assets/presentation/hero-light.svg" width="960" alt="DropProbe — Separate configuration hints from a real probe.">
</picture>

**DropProbe 汇总选定模型组织近期更新的条目与本机硬件画像，并提供候选量化、后端和工具状态的静态配置结构。**

`Python 3.12+` · [MIT](LICENSE) · [GitHub](https://github.com/SuperMarioYL/dropprobe) · [网站](https://dropprobe.lei6393.com)

## 为什么需要它

准备尝试一个模型时，下载地址、量化大小、后端分支和机器内存通常分散在不同地方。先把这些线索放在一起有助于规划下一步，但静态容量计算不能证明推理会成功。当前版本停留在发现与静态组装，真实 smoke probe 尚未接入。

<picture>
  <source media="(max-width: 640px) and (prefers-color-scheme: dark)" srcset="assets/presentation/process-mobile-dark.svg">
  <source media="(max-width: 640px)" srcset="assets/presentation/process-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="assets/presentation/process-dark.svg">
  <img src="assets/presentation/process-light.svg" width="960" alt="Two declared memory profiles">
</picture>

## 架构

drops 从固定组织列表查询 Hub 条目，hardware 探测可用硬件信息，config_db 读取打包的 YAML。build_probe_card 将它们合并并选择最小候选量化。probe_drop 当前直接返回 NOT_PROBED，report 将列表、硬件或 API 提供的卡片转为表格/JSON。

<picture>
  <source media="(max-width: 640px) and (prefers-color-scheme: dark)" srcset="assets/presentation/architecture-mobile-dark.svg">
  <source media="(max-width: 640px)" srcset="assets/presentation/architecture-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="assets/presentation/architecture-dark.svg">
  <img src="assets/presentation/architecture-light.svg" width="960" alt="Discovery and static candidate assembly">
</picture>

## 安装

需要 Python 3.12+。安装可能联网；先运行不访问 Hub、不探测机器、不启动模型的静态示例。

```bash
git clone https://github.com/SuperMarioYL/dropprobe.git
cd dropprobe
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

## 快速开始

```bash
python examples/presentation_demo.py
```

示例显式声明 8 GiB 与 2 GiB 两种 CPU RAM，候选 Q4 为 4 GiB、Q8 为 8 GiB。两种情况下都选最小候选 Q4；前者 runnable 字段为 true，后者为 null，但两者 probe_status 均为 not_probed，smoke_probe_ok 均为 null。true 在这里仅是静态容量提示。

## 用法

```bash
# 以下命令会查询 Hugging Face 并检测本机
dropprobe latest --list
dropprobe latest --list --window 14
dropprobe latest --list --cache-dir /path/to/model-cache --json
dropprobe --version
```

不带 --list 的 latest 也不会在当前版本运行推理；NOT_PROBED 路径会退回列表。窗口日期优先使用 Hub lastModified，因而“近期条目”不一定等于首次发布的新模型。

## 能力与集成

| 组成 | 当前支持 |
|---|---|
| Hub 查询 | 固定组织及别名列表 |
| 硬件 | NVML、ROCm 与 CPU/RAM/磁盘回退 |
| YAML DB | 候选量化、后端引用、工具状态声明 |
| Python API | Drop + HardwareProfile → ProbeCard |
| 输出 | 列表/硬件表与 JSON |

<picture>
  <source media="(max-width: 640px) and (prefers-color-scheme: dark)" srcset="assets/presentation/integrations-mobile-dark.svg">
  <source media="(max-width: 640px)" srcset="assets/presentation/integrations-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="assets/presentation/integrations-dark.svg">
  <img src="assets/presentation/integrations-light.svg" width="960" alt="Current data interfaces">
</picture>

## 配置与边界

--window 默认 7 天，CLI 接受 1–90；--cache-dir 用于选择磁盘空间检测位置。打包配置在 src/dropprobe/data/config_db.yaml，内容是维护者声明，不是实时后端验收。

静态 GPU 容量逻辑预留约 1.5 GiB；CPU 路径比较 RAM，不估计所有运行时开销。未检测到受支持 GPU 时可能归入 CPU，不代表机器没有其他加速器。Hub 请求失败可能得到空列表，不能据此断言没有更新。run_cmd 是未经本轮执行的文本模板，仍需核查实际后端参数。

## 运行记录

v0.1.0 的真实静态组装 API 输出。所有模型、后端和硬件值均为构造输入，不是下载、实际机器检测或推理成功记录。

[输入、命令和完整输出](docs/demo-results.json)

## 路线图

- [x] 近期条目查询和硬件画像。
- [x] 静态配置 DB、ProbeCard 组装和 JSON 输出。
- [ ] 真实模型下载/后端 smoke probe。
- [ ] 经实际运行验证的配置与命令记录。

当前没有固定“30 秒可运行”的保证。

## 开发与许可证

```bash
python -m pip install -e ".[test]"
python -m pytest
```

静态行为与 NOT_PROBED 契约见 [test_probe.py](tests/test_probe.py)。

[MIT](LICENSE) · [Issues](https://github.com/SuperMarioYL/dropprobe/issues)
