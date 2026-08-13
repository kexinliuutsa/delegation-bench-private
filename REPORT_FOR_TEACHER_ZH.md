# DelegationBench 实验工作精简报告

日期：2026-08-13  
性质：阶段性研究总结；完整证据与实验过程保存在本 Private 仓库中。

## 1. 研究在解决什么问题

本项目研究：当工具型 agent 在执行任务途中看到一条新增的环境信息或指令时，它之后的行为轨迹是否发生可测量的改变，以及这种变化能否与正常的随机执行路径变化区分开。

核心设计是 control/treatment 配对轨迹和延迟暴露：两条轨迹从相同任务、工具与初始环境出发，treatment 只在预定步骤后看到新增信息。分析比较暴露后的行为分化相对于暴露前基线增加了多少，而不是把任何两条不同轨迹都视为干预影响。

## 2. 最扎实的实验结果

DelegationBench v1 包含 160 个 control/treatment 配对、320 条真实轨迹，其中 133 对实际到达暴露边界。确认性 pair-level bootstrap 分析得到：

- action divergence 的平均 post−pre 增量为 **0.4986**，95% CI **[0.4400, 0.5565]**；
- capability-sequence divergence 的平均增量为 **0.3157**，95% CI **[0.2716, 0.3623]**；
- Coding 增量为 **0.3281**，Web 增量为 **0.7561**；Web−Coding 差为 **0.4281**，95% CI **[0.3322, 0.5196]**。

因此，目前可以支持的主结论是：

> 在随机化配对和延迟暴露协议下，agent 暴露后的轨迹分化显著高于暴露前分化，并且这种响应幅度在 Coding 与 Web 中不同。

这个结论描述的是可观察行为轨迹，不等同于攻击成功、authority violation、安全失败或隐藏认知状态改变。

## 3. 一个重要的测量发现：正常轨迹本来就很随机

在 133 个暴露到达配对中，**60 对（45.11%）** 在共享的暴露前阶段已经出现行为差异。这说明即使任务、提示和环境相同，agent 也经常采用不同的正常执行路径。

为排除整体效应只是由“容易且完全一致”的轨迹产生，项目进一步分层：

- 暴露前一致的 73 对：post−pre 增量 **0.6999**，95% CI **[0.6447, 0.7532]**；
- 暴露前已分叉的 60 对：post−pre 增量 **0.2538**，95% CI **[0.1773, 0.3287]**。

两层均为正。这既支持主要测量结果，也说明简单的绝对异常距离不足以充当可靠监控器。

## 4. PIDR 方法目前证明到什么程度

PIDR-v1 的目标是减少无关的范式差异，同时保留干预相关变化。在冻结的 seed-4 评估中：

- RAW post separation：0.2979；
- PIDR-v1 post separation：0.6411；
- PIDR−RAW：**0.3900**，95% CI **[0.2851, 0.5020]**。

在已打开集合上的回顾性 baseline 比较中，PIDR 相对 CORAL 和 MMD 的 post separation 差也为正，区间不跨 0。

但这只支持 PIDR 是一个**表示层 proof-of-concept**。它没有证明是更好的部署级 detector：AUROC 改善区间跨 0，pair detection 没有优于 RAW，而且出现了 3.13% benign false alarm。因此不能写成“PIDR 已解决 agent monitoring”。

## 5. 已证明当前路线走不通或没有显示价值的部分

### 5.1 简单跨范式监控器

早期 Coding→Web pilot 中，NDTR AUROC 为 0.4416 且 control false alarm 为 100%；CDM AUROC 为 0.4095、pair detection 为 0%。这说明这些早期普通 monitor 在跨范式迁移中存在严重失败模式，但属于开发阶段证据。

### 5.2 当前 DeepLog-style 适配

测试的轻量 next-event sequence diagnostic 得到 AUROC 0.5527、benign false alarm 28.13%，没有显示增量价值。这个结论只适用于本项目实现的 dependency-light 适配，不能推广成“DeepLog 或序列模型无效”。

### 5.3 Delegation-transition 路线

该路线未能稳定识别 transition-state 的增量价值：决策边界覆盖不足、缺少足够 post-boundary opportunity，并多次遇到 schema/infrastructure instability。因此实验线已经归档。正确含义是“当前设计走不通”，不是“transition hypothesis 已被证伪”。

### 5.4 纯规则 refusal 分类

冻结规则在合成 challenge set 上 accuracy 42.5%、macro F1 0.384、hard-negative specificity 76.9%，不能可靠地区分真实拒绝与普通环境失败或任务推理。因此它不能作为最终语义测量工具。

## 6. 目前无法判断、不能写成负结果的部分

### 6.1 跨模型 fresh-sealed 复制

v1.3 协议资格与 smoke 测试通过；正式收集中 GPT-5 完成 80/80，gpt-4.1 完成 68/80。12 条缺失主要来自 provider quota exhaustion，另有一次独立 HTTP transport failure。完整配对只剩 33/40，并且 `transaction_preparation` 变成 0/5 complete pairs。

项目没有填补、合成或替换缺失轨迹，也没有授权在结构性偏差子集上做 secondary science。因此跨模型假设目前是：**未建立，也未被否定**。

### 6.2 Resistance / refusal

Phase 0 日志样本中的显式信号很稀疏；规则系统又未通过语义验证。120 个真实 decision-point 人工验证包已冻结，但尚缺两位独立人工标注。因此不能声称 agent 很少拒绝、干预压制 resistance，或 PIDR 能预测 resistance。

### 6.3 Adoption 与 task-scope expansion

现有日志中同时具备“暴露后文本 + 下一动作”的 adoption 可观察案例仅 2 个；明确保存 pre/post task framing 的轨迹为 0。两者暂不具备科学分析条件。

### 6.4 Recovery

40-pair feasibility sample 中 33 对可评估，存在 1 个 strict 和 6 个 relaxed recovery candidates，说明该测量值得继续人工验证。但这还不是 recovery rate，更不表示 recovery 等于安全纠正。

## 7. 项目最合适的定位

当前最合理的论文定位是：

> **以 benchmark measurement 为主，以 representation method 为辅。**

主要贡献可概括为：

1. 构建 shared-prefix、delayed-exposure、control/treatment paired trajectory 测量协议；
2. 证明暴露后分化相对暴露前基线显著增加，并量化 Coding/Web 异质性；
3. 揭示大规模 benign pre-exposure variation，说明 agent monitoring 必须处理随机执行路径；
4. 提供 PIDR-v1 这一 intervention-sensitive representation geometry 的 proof-of-concept。

暂时不应把部署级安全监控器、攻击成功检测或跨模型普适性列为已完成贡献。

## 8. 当前研究状态一览

| 方向 | 状态 | 可以说什么 |
|---|---|---|
| DelegationBench v1 | 已确认 | 暴露后轨迹分化超过暴露前基线 |
| Coding/Web 异质性 | 已确认 | 两个执行范式的响应幅度不同 |
| 良性路径变化 | 已确认 | 暴露前自然分叉非常常见 |
| PIDR-v1 | 部分支持 | 表示分离更强；检测优势未建立 |
| 简单跨范式 monitor | pilot 失败 | 当前实现存在严重迁移失败模式 |
| DeepLog-style diagnostic | 未显示价值 | 当前轻量适配没有增量信号 |
| Delegation-transition | 已归档 | 当前设计不足；假设未证伪 |
| 跨模型复制 | 未完成 | 资源截断且结构性缺失，不能分析 |
| resistance/refusal | 等待人工验证 | 当前不能形成科学结论 |
| recovery | 测量可行 | 可进入人工验证，尚无科学效应 |
| adoption/scope | 信号不足 | 现有日志不支持分析 |

## 9. 给老师的最短摘要

> 项目最可靠的结果来自 DelegationBench v1：在 160 个真实配对轨迹中，133 对到达延迟干预边界，暴露后的 action divergence 相对暴露前平均增加 0.4986，95% CI [0.4400, 0.5565]；Coding 和 Web 均为正但 Web 更强。同时，45.1% 的轨迹在暴露前已经自然分叉，说明 agent monitoring 不能把任意轨迹差异当作干预影响。PIDR-v1 在表示层比 RAW/CORAL/MMD 保留更强的干预相关分离，但尚未证明下游检测优势。跨模型 fresh-sealed 复制因 gpt-4.1 配额耗尽而未完成，并完整缺失一个任务族，因此没有查看或报告其科学结果。

完整结果、限制和证据来源见 `paper/DelegationBench_Project_Report.md` 与 `paper/CLAIM_EVIDENCE_MATRIX.csv`。
