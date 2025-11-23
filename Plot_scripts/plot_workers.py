#!/usr/bin/env python3
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("results_workers.csv")
df = df.sort_values(["workers", "mode"])

modes = ["batch", "late", "latepro"]

def plot_metric(metric, ylabel, filename):
    plt.figure(figsize=(8,5))
    for mode in modes:
        sub = df[df["mode"] == mode]
        plt.plot(
            sub["workers"],
            sub[metric],
            marker="o",
            linewidth=2,
            label=mode
        )
    plt.xlabel("Number of Workers")
    plt.ylabel(ylabel)
    plt.title(f"{ylabel} vs Number of Workers")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()
    print("Saved", filename)

plot_metric("completion",  "Avg Completion Time (ms)", "workers_completion.png")
plot_metric("rpc",         "RPC per Job",              "workers_rpc.png")
plot_metric("task_wait",   "Task Wait (ms)",           "workers_wait.png")
plot_metric("task_resp",   "Task Response (ms)",       "workers_resp.png")
plot_metric("task_service","Task Service (ms)",        "workers_service.png")

print("All worker plots saved.")
