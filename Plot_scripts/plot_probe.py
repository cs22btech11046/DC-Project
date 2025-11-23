#!/usr/bin/env python3
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("results_probe.csv")
df = df.sort_values(["probe", "mode"])

modes = ["batch", "late", "latepro"]
colors = {"batch": "blue", "late": "green", "latepro": "red"}

def plot_metric(metric, ylabel, filename):
    plt.figure(figsize=(8,5))
    for mode in modes:
        sub = df[df["mode"] == mode]
        plt.plot(
            sub["probe"],
            sub[metric],
            marker="o",
            linewidth=2,
            label=mode
        )
    plt.xlabel("Probe Ratio (d)")
    plt.ylabel(ylabel)
    plt.title(f"{ylabel} vs Probe Ratio")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()
    print("Saved", filename)

plot_metric("completion",  "Avg Completion Time (ms)", "probe_completion.png")
plot_metric("rpc",         "RPC per Job",              "probe_rpc.png")
plot_metric("task_wait",   "Task Wait (ms)",           "probe_wait.png")
plot_metric("task_resp",   "Task Response (ms)",       "probe_resp.png")
plot_metric("task_service","Task Service (ms)",        "probe_service.png")

print("All probe plots saved.")
