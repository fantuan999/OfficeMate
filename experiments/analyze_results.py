import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

df = pd.read_csv("experiments/results/results.csv")
# print(df)

policies = ["lru", "lfu", "ttl", "semantic"]
alphas = [1.1, 1.5, 2.0]
thresholds = [0.75, 0.85, 0.95]

fig, axes = plt.subplots(1, 4, figsize=(18, 4))


# hit_rate
for i, policy in enumerate(policies):
    data = df[df["policy"] == policy]
    matrix = np.zeros((3, 3))

    for r, alpha in enumerate(alphas):
        for c, threshold in enumerate(thresholds):
            val = data[(data["alpha"] == alpha) & (data["threshold"] == threshold)]["hit_rate"].values[0]
            matrix[r][c] = val

    ax = axes[i]
    im = ax.imshow(matrix, vmin=0.85, vmax=1.0, cmap="YlGn")

    ax.set_title(policy.upper())
    ax.set_xticks(range(3))
    ax.set_xticklabels(thresholds)
    ax.set_yticks(range(3))
    ax.set_yticklabels(alphas)
    ax.set_xlabel("threshold")
    ax.set_ylabel("alpha")

    for r in range(3):
        for c in range(3):
            ax.text(c, r, f"{matrix[r][c]:.2f}", ha="center", va="center", fontsize=10)

# 在右侧单独留出空间给 colorbar，不占用子图空间
fig.subplots_adjust(right=0.88)
cbar_ax = fig.add_axes([0.91, 0.15, 0.02, 0.7])  # [left, bottom, width, height]
fig.colorbar(im, cax=cbar_ax, label="hit_rate")

plt.suptitle("Cache Hit Rate: alpha × threshold × policy")
plt.savefig("experiments/results/heatmap_hitrate.png", dpi=150, bbox_inches="tight")
plt.show()


# latency

x = np.arange(3)

fig2, axes2 = plt.subplots(1, 3, figsize=(15, 4))

for j, threshold in enumerate(thresholds):
    ax = axes2[j]
    for i, policy in enumerate(policies):
        data = df[(df["threshold"] == threshold) & (df["policy"] == policy)]
        data = data.sort_values("alpha")
        offset = (i - 1.5) * 0.2
        ax.bar(x + offset, data["avg_latency"], width=0.2, label=policy.upper())

    ax.set_title(f"threshold={threshold}")
    ax.set_xticks(x)
    ax.set_xticklabels(alphas)
    ax.set_xlabel("alpha")
    ax.set_ylabel("avg latency (s)")
    ax.legend()

plt.suptitle("Avg Latency by Policy and Alpha")
plt.tight_layout()
plt.savefig("experiments/results/latency_avg.png", dpi=150)
plt.show()


# P99
fig3, axes3 = plt.subplots(1, 3, figsize=(15, 4))

for j, threshold in enumerate(thresholds):
    ax = axes3[j]
    for i, policy in enumerate(policies):
        data = df[(df["threshold"] == threshold) & (df["policy"] == policy)]
        data = data.sort_values("alpha")
        offset = (i - 1.5) * 0.2
        ax.bar(x + offset, data["p99"], width=0.2, label=policy.upper())

    ax.set_title(f"threshold={threshold}")
    ax.set_xticks(x)
    ax.set_xticklabels(alphas)
    ax.set_xlabel("alpha")
    ax.set_ylabel("avg latency (s)")
    ax.legend()

plt.suptitle("P99 by Policy and Alpha")
plt.tight_layout()
plt.savefig("experiments/results/p99.png", dpi=150)
plt.show()