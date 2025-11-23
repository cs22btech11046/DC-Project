DECENTRALIZED DISTRIBUTED SCHEDULING EXPERIMENT
=========================================================

PROJECT OVERVIEW
----------------
This project implements a distributed banking system that uses the 

This project evaluates **three decentralized scheduling algorithms** using a
SimPy-based simulation:

1. Batch Scheduler
2. Late Binding Scheduler
3. Late Binding with Proactive Cancellation (LatePro)

These schedulers assign tasks to workers without any central coordinator.
Schedulers run independently, and all communication is simulated through
RPC-style events.

This README explains **only what is needed to run the experiments**.


EXPERIMENT PARAMETERS
----------------------

Common settings for all experiments:(simulated Job size distribution: Uniform)

Schedulers (SCHEDS): 5
Network delay (NDELAY): 2.0 ms simulated
Job size distribution: Uniform
jobsize_lo = 1 (minimum number of tasks a job can have)
jobsize_hi = 8 (maximum number of tasks a job can have) 


EXPERIMENT GROUPS
--------------------

Three experiment categories are provided. Each varies a single parameter while
keeping others fixed.

1. Probe Experiments

  Workers = 50
  Jobs = 300
  Probe values tested: 1, 2, 3, 4, 6, 8, 10

2. Workers Experiments

  Jobs = 300
  Probe = 2
  Workers tested: 5, 10, 20, 40, 80

3. Jobs Experiments

  Workers = 50
  Probe = 2
  Jobs tested: 50, 100, 150, 200, 400, 600, 800, 1000

Each experiment is run 10 times and averaged.

FILE STRUCTURE
------------------

simulation.py        Main simulator
worker.py            Worker implementation
batch.py             Batch scheduler
late.py              Late binding scheduler
late_pro.py          Late binding with cancellation
run_experiments_*    Shell scripts for each experiment group
plot_*.py            Plotting scripts


OUTPUT
-------------

Experiments generate CSV files with rows:
parameter,mode,completion,rpc,task_wait,task_resp,task_service

These CSV files are used to produce performance plots.

CONCLUSION
----------------

This simulation provides a simple, controlled environment for analyzing
Batch, Late, and LatePro decentralized scheduling algorithms under
different cluster and workload conditions.
