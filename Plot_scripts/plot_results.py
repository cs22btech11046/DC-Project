#!/usr/bin/env python3
import pandas as pd
import matplotlib.pyplot as plt

# -------------------------------------------------------------------
# Load CSV
# -------------------------------------------------------------------
df = pd.read_csv("results.csv")

# Ensure sorted
df = df.sort_values(["mode", "jobs"])

modes = ["batch", "late", "latepro"]
colors = {"batch": "blue", "late": "green", "latepro": "red"}

# -------------------------------------------------------------------
# Generic plot function
# -------------------------------------------------------------------
def plot_metric(df, metric, ylabel, filename):
    plt.figure(figsize=(8,5))

    for mode in modes:
        sub = df[df["mode"] == mode]
        plt.plot(
            sub["jobs"],
            sub[metric],
            marker="o",
            label=mode,
            linewidth=2
        )

    plt.xlabel("Number of Jobs", fontsize=12)
    plt.ylabel(ylabel, fontsize=12)
    plt.title(f"{ylabel} vs Number of Jobs", fontsize=14)
    plt.grid(True)
    plt.legend(title="Mode")
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()
    print(f"Saved {filename}")

# -------------------------------------------------------------------
# Produce all plots
# -------------------------------------------------------------------
plot_metric(df, "completion",  "Avg Completion Time (ms)", "multi_completion.png")
plot_metric(df, "rpc",         "RPC per Job",              "multi_rpc.png")
plot_metric(df, "task_wait",   "Task Wait (ms)",           "multi_wait.png")
plot_metric(df, "task_resp",   "Task Response (ms)",       "multi_resp.png")
plot_metric(df, "task_service","Task Service Time (ms)",   "multi_service.png")

print("All multi-mode plots generated.")
