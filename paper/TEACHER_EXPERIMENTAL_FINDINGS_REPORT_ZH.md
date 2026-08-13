# DelegationBench 项目阶段性实验结论报告

日期：2026-08-13  
项目目录：`authority-evolution`  
报告原则：只汇总当前实验文件能够支持的结论；严格区分确认性证据、回顾性/探索性证据、测量可行性结果以及尚不能成立的主张。

## 一、执行摘要

目前最可靠的贡献是一个关于智能体受延迟环境信息影响的**配对轨迹测量结果**，而不是一个已经证明有效的安全监控器。

在 DelegationBench v1 的 160 个 control/treatment 对、320 条真实轨迹中，有 133 对到达实际暴露边界。确认性分析表明：

1. 暴露后的 action divergence 显著高于暴露前，平均增量为 **0.4986**，95% CI **[0.4400, 0.5565]**。
2. 该效应在 Coding 和 Web 中都为正，但 Web 的幅度更大。Coding 增量为 **0.3281**，Web 为 **0.7561**；Web−Coding 交互差为 **0.4281**，95% CI **[0.3322, 0.5196]**。
3. 共享暴露前阶段仍有明显的良性路径变化：**60/133（45.11%）** 的配对在暴露前已经出现行为差异。因此，不能把任意轨迹差异直接解释为干预影响。
4. 即使在暴露前已经分叉的配对中，post−pre 增量仍为正：**0.2538**，95% CI **[0.1773, 0.3287]**。在暴露前完全一致的配对中，增量也为正，95% CI **[0.6447, 0.7532]**。

PIDR-v1 提供了一个**表示层 proof-of-concept**：在已打开的 seed-4 回顾性比较中，它比 RAW、CORAL 和 MMD 保留了更强的干预相关 post-exposure separation。但该优势没有转化为被统计确认的下游检测改善；因此当前不能声称 PIDR 是更好的监控器。

真正的跨模型 fresh-sealed 复制尚未完成。GPT-5 收集完成 80/80，gpt-4.1 仅完成 68/80；缺失造成 `transaction_preparation` 在完整配对中变为 0/5，因此不允许用现有不完整样本开展 secondary scientific analysis。

## 二、证据等级

| 等级 | 含义 | 当前内容 |
|---|---|---|
| A：确认性、冻结结论 | 按预先协议、pair-level bootstrap 得到，可作为报告主结论 | Experiment 70 / 70.1 四条 benchmark 结论 |
| B：已打开集合上的回顾性证据 | 有明确比较和区间，但不是独立 confirmatory test | Experiment 75 的 PIDR vs CORAL/MMD |
| C：探索性或 pilot | 可用于动机和局限，不能作为论文主结论 | 早期 monitor、跨域失败、异质性描述、旧环境影响实验 |
| D：测量/基础设施结论 | 说明什么可以测、什么暂时不能测 | refusal、recovery、fresh-sealed QC |
| E：不支持或未测试 | 必须明确排除 | PIDR 检测优势、通用跨模型泛化、transition 增量价值等 |

## 三、当前可支持的核心科学结论

### 3.1 延迟环境干预与暴露后轨迹分化相关

主分析使用 133 个实际到达暴露边界的完整配对，以 pair 为 bootstrap 单位，共 10,000 次重采样。

| 指标 | 暴露前 | 暴露后 | post−pre | 95% CI |
|---|---:|---:|---:|---:|
| Action divergence | 0.2199 | 0.7186 | **0.4986** | **[0.4400, 0.5565]** |
| Capability-sequence divergence | — | — | **0.3157** | **[0.2716, 0.3623]** |

允许表述：

> 在随机化配对、延迟暴露协议下，agent 的暴露后轨迹分化显著高于暴露前分化。

不能表述：

- 攻击成功率上升；
- agent 违反了 authority；
- 内部认知状态发生了已被识别的因果改变；
- 所有 action divergence 都是不安全行为。

### 3.2 Coding 与 Web 的响应幅度存在异质性

| 范式 | 暴露到达配对 N | 平均 post−pre action delta | 95% CI |
|---|---:|---:|---:|
| Coding | 80 | **0.3281** | **[0.2607, 0.3921]** |
| Web | 53 | **0.7561** | **[0.6875, 0.8192]** |

Web−Coding 差为 **0.4281**，95% CI **[0.3322, 0.5196]**。

允许表述：不同执行范式中的干预相关响应幅度不同。不能把这个结果推广为“Web agent 普遍更不安全”或“范式身份产生某种普适机制”。

### 3.3 轨迹本身存在大量良性随机分叉

在 133 个暴露到达配对中，60 对在共享的暴露前区域已经出现行为分叉，比例为 **45.11%**。该变化没有集中到单一 task、seed、style 或 exposure-step；但 scheduled step 5 的 pre-divergence rate 较高（78.38%），应作为结构性敏感性报告。

这支持两个重要判断：

- agent 轨迹具有高随机性，单纯“control 和 treatment 不同”不是充分的干预证据；
- 测量应比较 post-exposure divergence 相对于 pre-exposure baseline 的增量，而不是只看绝对 post distance。

### 3.4 干预相关效应在 pre-identical 和 pre-diverged 两层都存在

| 暴露前分层 | N | 平均 post−pre action delta | 95% CI |
|---|---:|---:|---:|
| PRE_IDENTICAL | 73 | **0.6999** | **[0.6447, 0.7532]** |
| PRE_DIVERGED | 60 | **0.2538** | **[0.1773, 0.3287]** |

因此，整体结果并非仅由暴露前完全一致的“容易样本”驱动；在已有良性分叉的轨迹上仍能观察到额外的暴露后变化。

## 四、PIDR-v1：支持到什么程度

### 4.1 支持：PIDR 保留更强的干预相关表示分离

Experiment 72 的冻结 seed-4 结果中，24 个 exposure-reached pairs 显示：

- RAW post separation：0.2979；
- PIDR-v1 post separation：0.6411；
- PIDR−RAW：**0.3900**，95% CI **[0.2851, 0.5020]**。

范式 probe accuracy 从 RAW 的 0.9959 降至 PIDR 的 0.8975，说明表示中的 paradigm identity 信息有所减少。但 PIDR 的 absolute pre-benign distance 并未改善，反而增加，因此不能声称它对所有 benign paths 实现了完整 alignment。

### 4.2 回顾性 published-baseline 比较

Seed 4 在 Experiment 72 已经打开，所以 Experiment 75 只能称为 **previously opened evaluation set 上的 retrospective published-baseline comparison**。

| 方法 | Pre-benign distance | Post separation | Monitor AUROC | Benign FA | Pair detection |
|---|---:|---:|---:|---:|---:|
| RAW | 0.9156 | 0.2979 | 0.8154 | 0% | 40.63% |
| CORAL | 0.8644 | 0.2812 | 0.8066 | 0% | 37.50% |
| MMD | 0.8269 | 0.3157 | 0.8027 | 0% | 34.38% |
| PIDR-v1 | 0.9349 | **0.6411** | 0.8584 | **3.13%** | **34.38%** |

关键 pair-bootstrap 比较：

- PIDR−CORAL post separation：**0.4113**，95% CI **[0.3022, 0.5340]**；
- PIDR−MMD post separation：**0.3756**，95% CI **[0.2659, 0.4952]**；
- PIDR−CORAL AUROC：0.0508，区间跨 0；
- PIDR−MMD AUROC：0.0548，区间跨 0。

结论是：

> PIDR-v1 在这个已打开集合上呈现 selective intervention-sensitive representation geometry；它比通用 CORAL/MMD alignment 更好地保留干预相关分离。

但必须同时写：

> 该表示优势没有转化为更好的下游检测。PIDR detection 为 34.38%，低于 RAW 的 40.63%，并且 PIDR 是唯一出现非零 benign false alarm（3.13%）的方法。AUROC 差异没有被统计确认。因此，PIDR-v1 目前是表示层 proof-of-concept，下游监控效用尚未建立。

### 4.3 DeepLog 结果的正确定位

测试的是 dependency-light DeepLog-style recurrent-history diagnostic，不是 faithful DeepLog reproduction。其 AUROC 为 0.5527，benign false alarm 为 28.13%，没有显示增量价值。

允许表述：轻量 next-event sequence diagnostic 没有显示增量信号。不能表述：DeepLog 无效，或现代序列模型无法解释该现象。

## 五、早期探索性结果：只能作为动机或局限

### 5.1 早期监控器的跨域泛化失败

早期 v0 pilot 中，Coding→Web：

- NDTR AUROC 0.4416，control false alarm 100%；
- CDM AUROC 0.4095，pair detection 0%。

Web→Coding 还存在 task-router support 缺陷，full-target coverage 仅 25%。这些结果支持“普通 trajectory monitor 在跨范式转移中存在严重 failure modes”这一研究动机，但它们是 pilot/development evidence，不能当作 v1 的确认性跨域结论。

### 5.2 早期环境影响与 adoption 结果

旧的 48-pair coding 环境影响数据中，操作性 adoption 只在 multi-step style 出现 6/12，其他 style 为 0/12。由于这些 adoption 标签是早期、狭窄的操作性规则，而且后续 Experiment 82C 发现显式 acknowledgment text 极稀少，因此不应把它写成可靠的 style effect 或攻击成功结论。

### 5.3 探索性异质性

现有 task family、intervention style、exposure step 的分析是 descriptive main-effect summary。不能据此声称某个 style 因果地产生更大 drift。

## 六、当前不能支持的主张

### 6.1 跨模型 fresh-sealed replication 尚未完成

基础设施资格验证在 Experiment 81.8 中通过，但真正 fresh-sealed collection 的现状是：

- GPT-5：80/80 trajectories；
- gpt-4.1：68/80 trajectories；
- 缺失：12，其中 11 个为 quota exhaustion，1 个为独立 HTTP transport failure；
- 完整配对：33/40；
- numerical effective N：33 overall、20 Coding、13 Web，虽然超过硬阈值；
- 但 `transaction_preparation` 为 **0/5 complete pairs**。

因此 quota-truncated secondary analysis 被判定为 **QUOTA_TRUNCATED_SECONDARY_ANALYSIS_NOT_AUTHORIZED / QUOTA_TRUNCATED_TOO_BIASED**。不能查看或报告该 fresh-sealed cohort 的 post-pre effect、PIDR/CORAL/MMD、AUROC 等科学结果。

目前不能声称：

- 核心效应已复制到 gpt-4.1；
- PIDR 的表示优势在全新 sealed cohort 中复现；
- 结果不是 GPT-5 特有；
- 结果具有 provider/model-family independence。

即便未来 GPT-5 与 gpt-4.1 均成功，它们仍属于同一 provider/model ecosystem，只能支持 `NOT_UNIQUE_TO_GPT5`，不能支持 architecture-independent 或 model-family-independent。

### 6.2 Delegation-transition 实验线已归档，但假设没有被证伪

最终状态：`ACTIVE_EXPERIMENTAL_WORK = false`。

归档原因是：仅恢复 12 个 contract-defined boundaries，B0/B1 的 trajectory-level decision coverage 不足，Experiment 79.1 没有 post-boundary opportunity，static-vs-transition incremental value 不可识别，并多次遭遇 infrastructure/schema instability。

正确表述：

> Delegation-transition hypothesis 没有被证伪。当前设计提供的信息不足以识别 transition-state 的增量价值，而继续复制的基础设施成本过高，因此归档。

不能表述：DTM 失败、static checking 已被证明充分、transition state 没有价值。

### 6.3 Resistance/refusal 尚不能成为科学结论

- Phase 0：40 个样本中规则没有找到 non-CONTINUE candidate，状态为 `REFUSAL_SIGNAL_TOO_SPARSE`；
- Rule challenge：accuracy 42.5%，macro F1 0.384，hard-negative specificity 76.9%，状态为 `RULE_SPECIFICITY_INSUFFICIENT`；
- Human-grounded validation：已冻结 120 个真实 decision points，但尚无两位独立人工标注者，状态为 `WAITING_FOR_HUMAN_ANNOTATIONS`。

因此不能声称 agent 很少拒绝、干预压制 resistance、PIDR 预测 resistance，或某种 style 降低 resistance。

### 6.4 Recovery 有测量可行性，但还不是科学效应

Experiment 82C Phase 0 的 40-pair 样本中：33 对可评估，1 个 strict recovery candidate、6 个 relaxed candidate、7 个 unresolved。状态为 `RECOVERY_MEASUREMENT_FEASIBLE`。

这只说明 recovery 定义值得进一步人工验证，不表示 recovery rate 已被估计，也不表示 recovery 等于安全纠正。

Adoption acknowledgment 只有 2 个 text+next-action cases，信号过稀；task-scope change 有 0 条轨迹同时保存明确 pre/post framing，无法分析。

## 七、项目当前最合适的定位

建议将论文/汇报定位为：

> **Benchmark measurement 为主，representation method 为辅。**

主要贡献：

1. 一个具备 shared-prefix、delayed exposure、control/treatment paired trajectories 的 DelegationBench 测量协议；
2. 证明 post-exposure divergence 超过 pre-exposure divergence，并量化 Coding/Web 异质性；
3. 揭示大量 benign pre-exposure variation，说明 agent trajectory monitoring 必须显式处理 stochastic execution paths；
4. PIDR-v1 作为 selective invariance / intervention-sensitive geometry 的表示层 proof-of-concept。

暂时不应将“部署级监控器”或“跨模型普适性”作为贡献。

## 八、建议下一步

按优先级排序：

1. **恢复 API credit 后，仅补跑 12 个缺失的 gpt-4.1 jobs**。必须使用 frozen missing-only resume，不得重跑已完成轨迹。完整 160/160 后重新进行 QC，再单独启动 confirmatory analysis。
2. **完成两位独立人工 resistance annotation**。先评估 taxonomy 的 human-human kappa，再决定是否验证 LLM/hybrid judge；不能跳过人工 gold。
3. **对 recovery measurement 做人工验证**。验证 strict/relaxed 定义是否与人类对“回到原任务进程”的判断一致，然后再考虑 Phase 1 retrospective analysis。
4. 如继续方法线，优先做 faithful/reference sequence baseline 和真正跨 provider model family 的复制，而不是立即开发 PIDR-v2。

## 九、给老师的一段简短表述

> 当前最扎实的结果是：在 160 个真实 control/treatment 配对轨迹构成的 DelegationBench v1 中，133 对实际到达延迟干预边界。暴露后的 action divergence 相对暴露前平均增加 0.4986，95% CI [0.4400, 0.5565]；该效应在 Coding 和 Web 中均为正，但 Web 更强。同时，45.1% 的配对在暴露前就存在良性路径分叉，说明不能用简单异常检测直接区分干预影响。PIDR-v1 在已打开的回顾性集合上比 CORAL/MMD 保留更强的干预相关表示分离，但尚未带来统计确认的检测改善。目前 fresh-sealed 跨模型复制因 gpt-4.1 API quota 导致 12 条轨迹缺失而未完成，且缺失完整消除了一个 task family，因此没有查看或报告该集合的科学结果。

## 十、主要证据文件

- `results/delegation_bench_v1/confirmatory/benchmark_findings_frozen.json`
- `paper/CLAIM_EVIDENCE_MATRIX.csv`
- `results/delegation_bench_v1/pre_exposure_variation/PRE_EXPOSURE_VARIATION_REPORT.md`
- `results/delegation_bench_v1/pidr_v1_sealed_test/sealed_test_summary.json`
- `results/delegation_bench_v1/published_baselines/representation_existing_evaluation_results.csv`
- `results/delegation_bench_v1/published_baselines/representation_bootstrap_comparisons.csv`
- `paper/EXPERIMENT75_LANGUAGE_CORRECTION.md`
- `paper/archive/DELEGATION_TRANSITION_FINAL_STATUS.md`
- `results/delegation_bench_crossmodel_v13/fresh_sealed/quota_truncation_audit/authorization_decision.json`
- `results/delegation_bench_v1/post_exposure_behavior_phase0/phase0_decision.json`

## 附录：主要实验状态总表

| 实验 | 当前状态 | 可以支持什么 | 不能支持什么 |
|---|---|---|---|
| 70 | BENCHMARK_LEVEL_CONFIRMATORY_FINDINGS_FROZEN | post-exposure divergence 增加；Coding/Web 异质性 | attack success、authority violation |
| 70.1 | PRE_VARIATION_CONSISTENT_WITH_BENIGN_STOCHASTICITY | 良性 pre-exposure variation；两种 pre-strata 中增量均为正 | pre-divergence 等于协议失败 |
| 72 | PIDR_V1_SEALED_TEST_COMPLETE | PIDR post separation 增加、paradigm probe 降低 | 下游监控改善、完整 benign alignment |
| 75 | RETROSPECTIVE_PUBLISHED_BASELINE_COMPARISON | PIDR 比 CORAL/MMD 保留更强 post separation | 独立 confirmatory baseline 结论、PIDR 检测优势 |
| 75 sequence diagnostic | NO_INCREMENTAL_SEQUENCE_BASELINE_VALUE | 轻量 next-event diagnostic 未显示增量价值 | faithful DeepLog 无效、现代 sequence modeling 无效 |
| Delegation-transition | ARCHIVED；hypothesis not falsified | 当前设计无法识别 transition-state 增量价值 | DTM 失败、static checking 已充分 |
| 81.8 | READY_FOR_NEW_FRESH_SEALED_COHORT_DESIGN | v1.3 runner、exposure 与 QC protocol 通过 smoke | 科学跨模型复制 |
| 81.10 | FRESH_SEALED_COLLECTION_INCOMPLETE | GPT-5 80/80、gpt-4.1 68/80 的收集事实 | 任何 fresh-sealed 科学结果 |
| 81.10Q | SECONDARY ANALYSIS NOT AUTHORIZED | quota-truncated subset 存在结构性偏差 | complete-case secondary science |
| 82A Phase 0 | REFUSAL_SIGNAL_TOO_SPARSE | 当前日志中的 refusal candidate 很稀疏 | agent 很少拒绝 |
| 82A.1 | RULE_SPECIFICITY_INSUFFICIENT | rule classifier 不能作为最终语义测量工具 | 真实数据上的可靠 refusal rate |
| 82A.2 | WAITING_FOR_HUMAN_ANNOTATIONS | human-grounded validation package 已冻结 | resistance 科学分析 |
| 82C Phase 0 | RECOVERY_MEASUREMENT_FEASIBLE | recovery 值得进入人工测量验证 | recovery rate 或安全纠正效应 |
| 82C adoption/scope | SIGNAL/TEXT TOO SPARSE | 现有日志不足以测量 | adoption、scope expansion 科学结论 |
