# DelegationBench

这是我在 agent 行为测量方向上的实验仓库。核心问题是：agent 执行任务时遇到后来出现的环境信息，后续行为会发生多大变化；这种变化又该怎样和正常的执行随机性区分。

仓库是 private 版本，所以不仅保留最终结果，也保留协议演变、失败实验、收集故障和质量检查。第一次看不需要从实验编号顺着读，下面三个文件已经把主线整理出来：

- [`REPORT_FOR_PEERS_ZH.md`](REPORT_FOR_PEERS_ZH.md)：目前的短报告
- [`KEY_RESULTS.md`](KEY_RESULTS.md)：关键数字，以及哪些问题还没有答案
- [`paper/DelegationBench_Project_Report.md`](paper/DelegationBench_Project_Report.md)：相对完整的研究总结

## 项目现在做到哪里了

DelegationBench v1 的主要结果已经固定下来。在 160 组 control/treatment 配对中，133 组到达了延迟暴露位置。暴露后的 action divergence 相对暴露前平均增加 0.4986（95% CI [0.4400, 0.5565]）。另一个对后续方法设计很重要的现象是，45.1% 的配对在暴露前就已经自然分叉。这意味着 agent 监控不能把两条轨迹不同直接当成干预效应。

PIDR-v1 在表示空间中保留了更强的干预后分离，不过还没有带来明确的检测收益。跨模型实验的协议和 smoke test 都完成了，但正式收集时 gpt-4.1 的 API credit 耗尽，最后又缺掉了一个完整任务族，所以没有对那批 sealed data 做科学分析。

## 文件在哪里

- `benchmarks/`：任务、协议和冻结的分析设置
- `experiments/`：实验与审计脚本
- `results/`：轨迹、统计结果和 QC 记录
- `models/`：PIDR、baseline 和行为规则
- `runners/`：轨迹采集与 proposal persistence
- `paper/`：完整报告、claim-evidence matrix 和归档说明
- `docs/`：实验编号索引与仓库审计

实验很多，主要是因为采集协议、暴露时机和 runner 可观测性经过了多轮修正。想追溯某条结论时，可以先查 [`paper/CLAIM_EVIDENCE_MATRIX.csv`](paper/CLAIM_EVIDENCE_MATRIX.csv)，再按 [`docs/EXPERIMENT_LINEAGE.md`](docs/EXPERIMENT_LINEAGE.md) 找到对应实验。
