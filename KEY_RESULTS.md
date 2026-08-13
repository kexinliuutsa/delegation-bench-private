# 结果备忘

这页不按实验编号写，只记录目前对项目的实际判断。详细统计和措辞边界仍以 `paper/CLAIM_EVIDENCE_MATRIX.csv` 为准。

## 已经比较确定的部分

### 暴露后确实出现了额外的轨迹变化

DelegationBench v1 有 160 组配对，133 组到达实际暴露位置。action divergence 的平均 post−pre 增量是 **0.4986**，95% CI **[0.4400, 0.5565]**。Coding 和 Web 中方向相同，但 Web 的幅度更大：Coding 为 0.3281，Web 为 0.7561。

这里测到的是行为轨迹变化，不是攻击成功率，也不是安全违规率。

### 正常执行路径的变化不能忽略

133 组可用配对中有 60 组在暴露前已经分叉，占 **45.1%**。即便只看这些已经分叉的轨迹，暴露后的额外增量仍是 0.2538，95% CI **[0.1773, 0.3287]**。

这也是 benchmark 最有用的地方：它让干预后的额外变化和 agent 自身的随机执行变化分开计算。

### PIDR 的表示结果有信号

在冻结测试中，PIDR 相对 RAW 的 post-separation 增量为 **0.3900**，95% CI **[0.2851, 0.5020]**。在后续回顾性比较中，它相对 CORAL 和 MMD 也保留了更强的干预后分离。

但检测结果没有同步改善，AUROC 差异没有确认，pair detection 也没有超过 RAW。因此我把 PIDR 看作表示方法原型，而不是完成的监控器。

## 做过但没有奏效的尝试

- 早期跨范式 NDTR/CDM 在 Coding→Web 上表现很差，还出现了极高的 false alarm。这条结果促使项目从普通异常检测转向配对测量。
- 当前轻量 DeepLog-style baseline 的 AUROC 是 0.5527，benign false alarm 是 28.13%，没有提供增量信号。这个结果只针对当前适配。
- 关键词 refusal rule 在 challenge set 上 accuracy 42.5%、macro F1 0.384，容易把环境问题错认成拒绝，不能作为正式测量工具。
- Delegation-transition 实验没有恢复出足够的边界和后续步骤，无法判断 transition state 是否比静态信息更有用。这条线已归档，但假设没有被数据否定。

## 现在还没有答案的问题

- **跨模型复现：**GPT-5 完成 80/80，gpt-4.1 完成 68/80。缺失使 `transaction_preparation` 没有任何完整配对，所以没有分析 sealed scientific outcomes。
- **PIDR 的实际监控价值：**表示分离更清楚，不等于 detector 更好；现有结果不足以支持部署层结论。
- **Resistance/refusal：**真实样本的人工标注尚未完成，不能根据规则的低命中率说 agent 很少拒绝。
- **Adoption 和 scope expansion：**日志没有留下足够的文字表面，现阶段无法可靠测量。
- **Recovery：**已有少量候选事件，适合继续做人类判断一致性检查，但还没有科学效应估计。

## 我会怎样介绍这个项目

DelegationBench 的主要贡献是一套配对、延迟暴露的轨迹测量方法。实验显示，agent 在看到新增环境信息后会产生超过正常执行波动的行为分化，同时也揭示了正常轨迹本身有很强的随机性。PIDR 是基于这一观察做的表示方法探索，目前有表示层结果，但还没有形成可靠的下游监控器。

继续阅读：[`REPORT_FOR_PEERS_ZH.md`](REPORT_FOR_PEERS_ZH.md)；完整版本见 [`paper/DelegationBench_Project_Report.md`](paper/DelegationBench_Project_Report.md)。
