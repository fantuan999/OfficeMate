import numpy as np
import matplotlib.pyplot as plt
from collections import Counter

class WorkloadGenerator:
    def __init__(self):
        pass


    def generate_zipf(self, alpha, n_queries, questions):
        """生成 Zipf 分布的查询序列"""
        # 决定提问什么问题
        n_unique = len(questions)
        array = np.random.zipf(alpha, n_queries)
        array = np.clip(array, 1, n_unique)
        array = array-1
        return [questions[i] for i in array]


    def generate_poisson(self, rate, duration):
        """生成 Poisson 到达过程"""
        time = 0
        array = []
        while (time < duration):
            interval = np.random.exponential(1/rate)
            time += interval
            if (time < duration):
                array.append(time)
        return array


    def generate_burst(self, normal_rate, burst_rate, burst_duration, total_duration):
        """生成突发流量"""
        # todo: 后期多次burst
        normal_duration = (total_duration - burst_duration) / 2
        array_norm1 = np.array(self.generate_poisson(normal_rate, normal_duration))
        array_burst = np.array(self.generate_poisson(burst_rate, burst_duration)) + normal_duration
        array_norm2 = np.array(self.generate_poisson(normal_rate, normal_duration)) + normal_duration + burst_duration
        return np.concatenate([array_norm1, array_burst, array_norm2]).tolist()


if __name__ == "__main__":
    
    g = WorkloadGenerator()
    questions = [f"问题{i}" for i in range(50)]  # 50个虚拟问题
    
    # ── 图1：Zipf 分布 ─────────────────────────────
    trace = g.generate_zipf(alpha=1.5, n_queries=1000, questions=questions)
    counts = Counter(trace)
    x = range(len(questions))
    y = [counts.get(questions[i], 0) for i in x]

    plt.figure(figsize=(10, 3))
    plt.bar(x, y)
    plt.xlabel("Question Index")
    plt.ylabel("Query Count")
    plt.title("Zipf Distribution (alpha=1.5)")
    plt.tight_layout()
    plt.savefig("experiments/results/zipf.png")
    plt.show()

    # ── Plot 2: Poisson Arrival ────────────────────
    timestamps = g.generate_poisson(rate=2, duration=60)
    plt.figure(figsize=(10, 3))
    plt.hist(timestamps, bins=60)
    plt.xlabel("Time (s)")
    plt.ylabel("Request Count")
    plt.title("Poisson Arrival Process (rate=2/s)")
    plt.tight_layout()
    plt.savefig("experiments/results/poisson.png")
    plt.show()

    # ── Plot 3: Burst ──────────────────────────────
    burst_ts = g.generate_burst(normal_rate=1, burst_rate=10,
                                burst_duration=10, total_duration=60)
    plt.figure(figsize=(10, 3))
    plt.hist(burst_ts, bins=60)
    plt.xlabel("Time (s)")
    plt.ylabel("Request Count")
    plt.title("Burst Traffic (normal=1/s, burst=10/s, burst_duration=10s)")
    plt.tight_layout()
    plt.savefig("experiments/results/burst.png")
    plt.show()