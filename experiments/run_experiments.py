import csv
import time
import redis
import config
from config import REDIS_HOST, REDIS_PORT
import services.cache_service as cache_mod
from experiments.workload_generator import WorkloadGenerator
from experiments.question_pool import QUESTIONS
from services.qa_service import ask
import numpy as np

ALPHAS = [1.1, 1.5, 2.0]
THRESHOLDS = [0.75, 0.85, 0.95]
POLICIES = ["lru", "lfu", "ttl", "semantic"]
N_QUERIES = 100

results = []

for alpha in ALPHAS:
    for threshold in THRESHOLDS:
        for policy in POLICIES:
            print(f"Running: alpha={alpha}, threshold={threshold}, policy={policy}")

            config.CACHE_SIMILARITY_THRESHOLD = threshold
            config.CACHE_EVICTION_POLICY = policy
            cache_mod.CACHE_SIMILARITY_THRESHOLD = threshold
            cache_mod.CACHE_EVICTION_POLICY = policy

            # clear Redis
            r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)
            r.flushdb()

            g = WorkloadGenerator()
            queries = g.generate_zipf(alpha=alpha, n_queries=N_QUERIES, questions=QUESTIONS)

            latencies = []
            hits = 0
            for q in queries:
                t0 = time.time()
                result = ask(q) # cache -> RAG -> similar + prompt -> LLM -> answer
                latencies.append(time.time() - t0)
                if result["cache_hit"]:
                    hits += 1
            
            hit_rate = hits / N_QUERIES
            p99 = np.percentile(latencies, 99)
            avg = np.mean(latencies)

            results.append([alpha, threshold, policy, hit_rate, p99, avg])

with open("experiments/results/results.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["alpha", "threshold", "policy", "hit_rate", "p99", "avg_latency"])
    writer.writerows(results)
print("Done. Results saved to experiments/results/results.csv")

