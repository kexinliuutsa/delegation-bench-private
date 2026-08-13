# DelegationBench（Private Research Repository）

这是 DelegationBench 的完整私有研究档案。仓库保留了冻结协议、实验脚本、原始轨迹、质量审计、失败记录与负结果，但为快速阅读提供了三个入口。

## 建议阅读顺序

1. [`REPORT_FOR_TEACHER_ZH.md`](REPORT_FOR_TEACHER_ZH.md) — 面向peers的中文精简报告
2. [`KEY_RESULTS.md`](KEY_RESULTS.md) — 一页式结论、边界与未完成事项
3. [`paper/DelegationBench_Project_Report.md`](paper/DelegationBench_Project_Report.md) — 完整项目报告

## 一句话结论

在 DelegationBench v1 的配对延迟暴露实验中，agent 暴露后的行为轨迹分化显著高于暴露前；但大量轨迹在暴露前已自然分叉，因此可靠测量必须显式控制良性随机路径变化。PIDR-v1 显示了表示层优势，但尚未证明下游检测优势。跨模型 fresh-sealed 复制因 gpt-4.1 配额耗尽和结构性缺失而未完成，不能解释为成功或失败的科学证据。

## 仓库结构

- `paper/`：完整报告、claim-evidence matrix、限制与归档说明
- `benchmarks/`：冻结协议、任务定义、分析计划
- `experiments/`：实验与审计脚本
- `results/`：完整结果、轨迹、QC 与失败记录
- `models/`：表示方法与规则基线
- `runners/`：采集及可观测性基础设施
- `tests/`：基础设施测试
- `docs/`：实验谱系、快照与敏感信息审计

## 当前状态

- 核心 benchmark 结论：已冻结并得到支持
- PIDR：表示层 proof-of-concept；部署级监控效用未建立
- 跨模型复制：未按预注册完成；假设既未确认也未证伪
- Delegation-transition：设计与基础设施不足，已归档；假设未证伪
- resistance/refusal：真实人工验证尚未完成
- recovery：测量可行，科学效应尚未分析
