import matplotlib.pyplot as plt
import numpy as np


labels = [
    "Execute\n→\nIrreversible",
    "Modify\n→\nIrreversible",
    "Execute\n→\nExternal"
]


observed = [
    43,
    17,
    9
]


null = [
    22.012,
    35.79,
    3.65
]


lower = [
    15,
    27,
    1
]


upper = [
    30,
    45,
    7
]


yerr = [
    [
        null[i] - lower[i]
        for i in range(3)
    ],
    [
        upper[i] - null[i]
        for i in range(3)
    ]
]


x = np.arange(len(labels))


plt.figure(
    figsize=(7,4)
)


plt.bar(
    x - 0.18,
    observed,
    width=0.36,
    label="Observed"
)


plt.bar(
    x + 0.18,
    null,
    width=0.36,
    yerr=yerr,
    capsize=5,
    label="Permutation Null"
)


plt.xticks(
    x,
    labels
)


plt.ylabel(
    "Transition Count"
)


plt.legend()


plt.tight_layout()


plt.savefig(
    "../results/figure2_transition.png",
    dpi=300
)


print(
    "saved figure2"
)
