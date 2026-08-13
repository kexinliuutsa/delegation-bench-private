# DelegationBench：阶段性实验记录

这份短报告是给组内讨论用的。它不按实验编号逐项罗列，而是说明项目为什么这样做、目前看到什么，以及哪些问题还卡着。

## 从哪里开始

我一开始想判断，agent 在执行任务时遇到后来出现的环境信息，会不会改变之后的行为。最直接的办法是比较有干预和无干预的两条轨迹，但实际跑起来后很快遇到一个问题：即使输入完全相同，agent 也会因为采样和工具选择走不同路径。这样一来，“轨迹不同”本身不是足够的证据。

DelegationBench 因此采用配对和延迟暴露设计。control 与 treatment 从同一个任务、工具和初始环境开始，treatment 到预定步骤后才看到额外信息。分析时先测暴露前两条轨迹本来有多不一样，再看暴露后增加了多少。

## Benchmark 的主要结果

v1 数据包含 160 组配对、320 条真实轨迹，其中 133 组执行到了暴露位置。action divergence 在暴露前平均为 0.2199，暴露后为 0.7186，post−pre 增量是 **0.4986**，95% CI **[0.4400, 0.5565]**。capability-sequence divergence 也得到相同方向的结果，增量为 **0.3157**，95% CI **[0.2716, 0.3623]**。

Coding 和 Web 都有正增量，但 Web 更大：

| | N | 平均 post−pre action delta | 95% CI |
|---|---:|---:|---:|
| Coding | 80 | 0.3281 | [0.2607, 0.3921] |
| Web | 53 | 0.7561 | [0.6875, 0.8192] |

我暂时把它解释为任务环境之间存在响应幅度差异，而不是 Web 更“不安全”。现有指标只描述行为序列变化，没有对行为后果做安全判定。

另一个值得单独报告的结果是，133 组中有 60 组在暴露前就已经分叉，占 **45.1%**。把样本按暴露前是否一致分开后，两组的 post−pre 增量仍然都是正的：pre-identical 组为 0.6999，pre-diverged 组为 0.2538。后者说明主要结果并不只来自那些本来就高度稳定的任务。

## PIDR 的进展

PIDR 的出发点是，把与 Coding/Web 范式有关但与干预无关的变化压低，同时保留干预后的变化。在冻结的 seed-4 测试中，RAW 的 post separation 是 0.2979，PIDR 是 0.6411；PIDR−RAW 为 **0.3900**，95% CI **[0.2851, 0.5020]**。在后来已经打开的数据上，PIDR 相对 CORAL 和 MMD 的表示分离也更强。

问题是表示空间里的优势还没有变成稳定的检测优势。PIDR 的 AUROC 改善区间跨 0，pair detection 没有超过 RAW，还出现了 3.13% 的 benign false alarm。所以 PIDR 目前比较像一个证明思路可行的 representation prototype，离实用 monitor 还有距离。

## 几条没有走通的路线

早期我试过直接做跨范式 monitor。Coding→Web 时，NDTR 的 AUROC 是 0.4416，而且 control false alarm 达到 100%；CDM 的 AUROC 是 0.4095，pair detection 为 0。这些 pilot 结果很差，但也帮助确认了问题不只是训练一个普通异常分类器。

轻量 DeepLog-style sequence baseline 也没有带来增益，AUROC 为 0.5527，benign false alarm 为 28.13%。这只说明当前适配不合适，还不足以否定更完整的序列模型。

Delegation-transition 方向最后没有得到可解释的结果。可恢复的决策边界太少，不少轨迹在边界后没有继续执行，期间还发生过多次 schema 和 runner 问题。数据不足以比较 transition state 和静态检查的增量价值，所以我停止继续堆实验，把这条线归档了。

我也检查过能否从轨迹里测 refusal。关键词规则的 challenge-set accuracy 只有 42.5%，macro F1 为 0.384，主要问题是会把“文件打不开”或“包无法导入”误判成 agent 拒绝。这个结果说明后续必须依赖带语境的人工标注，而不是继续调关键词。

## 跨模型复制为什么停在收集阶段

跨模型实验在 v1.3 前经历了几轮 sampler、timing 和 runner 修正，最后的 16-pair smoke 已经通过。正式 fresh-sealed 收集中，GPT-5 完成了 80/80 条轨迹，gpt-4.1 在 68/80 时遇到 API credit exhaustion。

如果缺失只是少量随机任务，还可以考虑做明确标注的 complete-case sensitivity。但这里 40 个 pair 只剩 33 个完整，而且 `transaction_preparation` 整个任务族变成 0/5。这个子集已经不再代表原来冻结的设计。因此我保留了所有收集和失败记录，没有填补轨迹，也没有查看这批 sealed data 的科学表现。

所以跨模型实验的状态是“资源原因导致未完成”，不是 positive result，也不是 negative result。

## 轨迹里还能测什么

现有日志对不同问题的支持程度差异很大。Resistance/refusal 需要两位人工标注者，目前只准备好了 120 个真实 decision points 的盲标包。Adoption 同时需要暴露后的文字和下一动作，实际只有 2 个合适案例。Scope expansion 需要暴露前后都有明确的任务表述，目前一个都没有。

Recovery 相对更有希望。40 组可行性样本里有 33 组可判断，算法找到了 1 个 strict 和 6 个 relaxed recovery candidates。下一步应先让人检查这些候选是否真的表示“重新回到原任务进程”，而不是直接计算 recovery rate。

## 目前的项目定位

我现在更愿意把它看作一个 measurement-first 项目。主要成果是 DelegationBench 的配对轨迹设计，以及对正常路径变化和干预后额外变化的量化。PIDR 是从这个测量问题延伸出来的方法实验。

如果继续推进，最值得做的是补齐跨模型数据、完成 resistance 人工标注，以及验证 recovery 定义。部署级 monitor 和跨模型普适性暂时都不应该写成已经完成的贡献。

完整数字和每项结论对应的证据可以在 `paper/CLAIM_EVIDENCE_MATRIX.csv` 中查到；实验过程则保留在 `results/` 和 `docs/EXPERIMENT_LINEAGE.md`。
