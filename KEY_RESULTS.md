# DelegationBench 核心结论速查

本页用于快速判断“项目已经证明什么、什么路线没有奏效、什么仍不能下结论”。数字和允许表述以 `paper/CLAIM_EVIDENCE_MATRIX.csv` 为准。

## 已得到支持

| 结论 | 关键证据 | 证据等级 |
|---|---|---|
| 延迟暴露后轨迹分化高于暴露前 | N=133；action post−pre = **0.4986**，95% CI **[0.4400, 0.5565]** | 确认性 |
| Coding 与 Web 响应幅度不同 | Coding 0.3281；Web 0.7561；差 **0.4281**，95% CI **[0.3322, 0.5196]** | 确认性 |
| 良性暴露前路径变化很常见 | 60/133，**45.11%** | 确认性 characterization |
| 已自然分叉的轨迹仍有额外暴露后变化 | N=60；增量 **0.2538**，95% CI **[0.1773, 0.3287]** | 确认性分层分析 |
| PIDR 保留更强的干预相关表示分离 | PIDR−RAW 0.3900；PIDR−CORAL 0.4113；PIDR−MMD 0.3756 | 方法 proof-of-concept；部分为回顾性 |

## 当前实现没有显示价值或路线走不通

| 项目 | 结果 | 正确解释 |
|---|---|---|
| 早期跨范式 NDTR/CDM | AUROC 低、false alarm 或 detection 严重失效 | 这些 pilot monitor 存在明显迁移失败模式 |
| DeepLog-style diagnostic | AUROC 0.5527；benign FA 28.13% | 当前轻量适配无增量价值，不代表所有序列模型无效 |
| 纯规则 refusal classifier | accuracy 42.5%；macro F1 0.384 | 规则不能作为最终语义测量工具 |
| Delegation-transition 当前设计 | 边界/机会覆盖不足，基础设施不稳定 | 当前设计无法识别增量价值；科学假设未证伪 |

## 尚不能判断

| 问题 | 为什么不能判断 | 禁止表述 |
|---|---|---|
| 是否跨模型复现 | GPT-5 80/80，gpt-4.1 68/80；一个任务族 0/5 完整配对 | “复制成功”或“复制失败” |
| PIDR 是否是更好的 detector | AUROC 差区间跨 0，detection 未改善且有 benign FA | “PIDR 解决了监控” |
| agent 是否很少拒绝或抵抗 | 日志信号稀疏、规则失败、人工 gold 未完成 | “agent 不拒绝”或“干预压制拒绝” |
| adoption acknowledgment | 可观察 text+next-action 案例仅 2 个 | adoption/style effect |
| task-scope expansion | 无明确同时保存 pre/post framing 的轨迹 | scope expansion effect |
| recovery 是否带来安全纠正 | 目前只有测量可行性和候选案例 | recovery 等于安全、正确或攻击识别 |

## 最安全的项目表述

> DelegationBench 提供了一套控制正常轨迹随机性的配对延迟暴露测量方法，并发现暴露后行为分化显著超过暴露前基线。PIDR-v1 是干预敏感表示的 proof-of-concept，但部署级监控效用和跨模型普适性尚未建立。

## 快速入口

- 教师版报告：[`REPORT_FOR_TEACHER_ZH.md`](REPORT_FOR_TEACHER_ZH.md)
- 完整报告：[`paper/DelegationBench_Project_Report.md`](paper/DelegationBench_Project_Report.md)
- Claim/evidence 矩阵：[`paper/CLAIM_EVIDENCE_MATRIX.csv`](paper/CLAIM_EVIDENCE_MATRIX.csv)
- 实验谱系：[`docs/EXPERIMENT_LINEAGE.md`](docs/EXPERIMENT_LINEAGE.md)
