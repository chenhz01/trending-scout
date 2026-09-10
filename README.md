# trending-scout — GitHub Trending 对抗性审核引擎

> 求合作脱敏版 · 文档 License: CC BY-NC-ND 4.0 · 代码暂不开源（合作版另议）
> 本文公开引擎架构与方法论（L1 层）+ 运行示例（L2 层）。画像调参配方、行业模板包、LLM 深审提示词库仅在商业合作中交付（L3 层）。

---

## 一句话定位

> **Trending 榜单只告诉你"什么火"，不告诉你"是不是真的、对你有没有用"。trending-scout 对每个上榜仓库做对抗性核实与画像评级，输出可决策的审核日报。**

## 为什么现有工具不够

GitHub Trending 日报类工具（采集→AI 摘要→推送）是红海，但它们全部缺三层：

1. **证伪核实层**：榜单名称/描述/star 数会被转载渠道以讹传讹——没人做逐仓回访核错
2. **画像评级层**：通用"五大维度"评分回答不了"对我的业务是 P0 还是噪音"
3. **元缺口层**：输出"这是什么"，不输出"你的能力体系缺什么、怎么借力"

## 引擎架构（L1 公开层）

```
Stage 1   采集      github.com/trending 解析（owner/repo、描述、star、日增、语言）
Stage 2   核实      API-first 逐仓核实：REST API 一次拿全 star/license/pushed_at/archived
                    五硬指标；网页解析降级为兜底路径（对抗性证伪）
Stage 2.5 风险标记  许可证风险（无许可证/自定义协议/(A)LGPL/GPL 传染）+ 停更检测
Stage 3   评级      profile.json 画像打分：业务线关键词加权 → P0/P1/P2 + 风险词标记
Stage 3.5 板块信号  跨仓统计画像命中分布：同品类 ≥3 仓上榜 → 赛道级集体信号
Stage 4   渲染      暗色 HTML 日报（P0绿/P1金/P2灰/风险红标签），支持 degraded 显式降级
```

## v2.1 更新（2026-09-10 · 红蓝对攻 180 补丁蒸馏落地）

- **许可证三态输出**（P23+P70）：明确合规 / 需人工复核 / 明确高风险——不做法律意见，优先降低误报
- **维护风险信号**（P34）：停更 ≠ 风险，按开放 issue 数区分「疑似废弃」与「可能稳定完成」
- **信号成熟度**（P3）：`experimental → validated(4期) → production(12期)`，未验证信号显式标注"不用于商业决策"
- **校准库种子**（P76+P79）：每次运行信号历史落盘 `calibration.jsonl`（历史数据+校准=护城河），已通过 `.gitignore` 排除出开源仓——开源核心、闭源历史库

## v2.0 更新（2026-09-10）

- **API-first 核实**：放弃网页正则解析 star 数（脆弱、易碎），改走 GitHub REST API 单请求取证；网页解析保留为限流兜底
- **许可证风险层**：`null`（无许可证，只能借思想）/ `NOASSERTION`（自定义协议，集成前必须人工读原文）/ copyleft 传染许可自动标红
- **停更检测**：`pushed_at` 超 180 天（可调 `--stale-days`）标记停更风险
- **板块信号检测**：单仓评级回答"对我有没有用"，板块信号回答"榜单集体在押注什么"——审核从逐仓升级到赛道层

设计原则：
- **零依赖**：纯 Python 标准库，单文件，3.8+ 可跑（与 agent-memory-doctor 同一工程纪律）
- **降级不编造**：抓取/核实失败显式标 `DEGRADED`，exit code 2，绝不补造数据
- **礼貌爬取**：逐仓回访 0.4s 间隔，只读公开页

## 快速开始

> 🎬 **Live demo**: a scheduled GitHub Action runs this engine daily (18:00 UTC+8) on the sanitized example profile and commits reports to [`reports/`](reports/) — the daily artifacts double as public proof-of-run.

```bash
python scout.py                          # top10 + 逐仓核实
python scout.py --limit 15 --no-verify   # 快速模式
python scout.py --since weekly           # 周榜
```

编辑 `profile.json` 定义你自己的业务画像（业务线 + 关键词 + 权重 + 风险词）。

## 运行示例（L2 层）

真实输出（2026-09-08，top8）：`8/8 核实通过 · P0×3 / P1×4 / P2×1`，画像命中最高的三个仓与当日人工深度审核结论一致（视频渲染引擎 / Agent harness / 营销 skill 库）——引擎评级与专家级人工审核收敛，是本引擎的验收标准之一。

## 深度示例：对抗性核实如何抓错

榜单页解析出的主锚点带 `data-hydro-*` 属性，naive 正则会抓到 `owner/repo/stargazers` 子页链接（我们第一版就踩了）。核实层逐仓回访后：404 页 → 标记"名称可疑"；star 漂移 >25% → 以实时数为准并标注 drift。**每一层都会攻击上一层的输出**——这是与"摘要搬运工"的本质区别。

## 合作解锁（L3 层）

> **Technical collaboration prospectus (anti-distillation edition): [docs/COLLABORATION.md](docs/COLLABORATION.md)** — verified capabilities, partner layer, and our five-measure anti-distillation policy (tiered disclosure / canary watermarks / non-production example params / contract-level output shape / license terms).

- 画像调参配方：按行业定制的业务线关键词库与权重矩阵
- LLM 深审提示词库：逐仓"学什么/怎么超越/风险合规"的对抗性审讯模板
- 行业模板包 + 历史评级数据库 + 多源扩展（HN/ProductHunt/Reddit）

## 联系方式

hcac4735@agent.qq.com ｜ 或直接提 Issue

---

*由「正明系统」设计并在生产环境每日运行。转载请保留本声明与 License。*
