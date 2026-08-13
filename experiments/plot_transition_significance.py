import matplotlib.pyplot as plt
import numpy as np


labels=[
    "Execute→\nIrreversible",
    "Modify→\nIrreversible",
    "Execute→\nExternal"
]


observed=[
    43,
    17,
    9
]


null=[
    21.918,
    35.778,
    3.672
]


x=np.arange(len(labels))

width=0.35


plt.figure(
    figsize=(8,5)
)


plt.bar(
    x-width/2,
    observed,
    width,
    label="Observed"
)


plt.bar(
    x+width/2,
    null,
    width,
    label="Permutation baseline"
)


plt.xticks(
    x,
    labels
)


plt.ylabel(
    "Transition count"
)


plt.title(
    "Capability Transition Patterns vs Permutation Baseline"
)


plt.legend()


plt.tight_layout()


plt.savefig(
    "../results/transition_significance.pdf"
)


print(
    "saved Figure"
)
