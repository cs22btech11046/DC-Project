DECENTRALIZED DISTRIBUTED SCHEDULING EXPERIMENT
================================================

PROJECT OVERVIEW
----------------
This project implements and evaluates three decentralized scheduling
techniques inspired by the Sparrow scheduler:

1. batch_scheduler.cpp  
     - Implements batch sampling (d × m choices)
     - Schedules tasks immediately based on probes

2. late_binding.cpp  
     - Implements late binding (workers request tasks only when ready)
     - Reduces stale decisions caused by queue-length races

3. late_binding_with_pro.cpp  
     - Late binding + proactive cancellation
     - Cancels unused reservations to avoid wasted worker time

Workers execute tasks and provide queue-length information to schedulers
through lightweight TCP RPC messages.

Each scheduler measures:
- Average wait time
- Average service time
- Average response time
- Average RPC calls per job
- Behavior with 90% short jobs and 10% heavy jobs

The experiment is fully **decentralized**, using 3 independent schedulers
running in parallel across 3 laptops, each probing and assigning tasks to 6
distributed worker nodes. There is **no central coordinator**, and schedulers
do not share global load state.


CLUSTER SETUP
-------------
The experiment uses 9 VMs distributed across 3 laptops.

Laptop 1:
  - Scheduler A: 10.96.1.131
  - Worker nodes: 10.96.1.135, 10.96.1.136

Laptop 2:
  - Scheduler B: 10.96.1.142
  - Worker nodes: 10.96.1.145, 10.96.1.137

Laptop 3:
  - Scheduler C: 10.96.1.156
  - Worker nodes: 10.96.1.161, 10.96.1.157

Total:
  - 3 Schedulers (decentralized)
  - 6 Worker nodes
  - 9 VMs


PREREQUISITES
-------------
- g++ with C++17 support
- Ubuntu 20.04 (or similar Linux environment)
- SSH access across all VMs
- All worker nodes reachable on TCP port 9100
- No additional libraries — pure C++ sockets are used


INSTALLATION
------------
1. Install build tools:
   sudo apt update
   sudo apt install g++ build-essential

2. Copy files:
   - On scheduler VMs:
       batch_scheduler.cpp
       late_binding.cpp
       late_binding_with_pro.cpp
       worker.cpp  (optional)
   - On worker VMs:
       worker.cpp only

   Example:
   scp *.cpp ubuntu@10.96.1.131:~/
   scp worker.cpp ubuntu@10.96.1.135:~/
   scp worker.cpp ubuntu@10.96.1.145:~/

3. Compile:

   Workers:
       g++ -std=c++17 worker.cpp -pthread -o worker

   Scheduler VMs:
       g++ -std=c++17 batch_scheduler.cpp -o batch
       g++ -std=c++17 late_binding.cpp -o lb
       g++ -std=c++17 late_binding_with_pro.cpp -o lb_pro


FILE STRUCTURE
--------------
worker.cpp
    Worker node program:
    - Responds to PROBE / ASSIGN / REQUEST / CANCEL
    - Maintains queue length with atomic counters
    - Simulates task execution using sleeping threads

batch_scheduler.cpp
    Decentralized scheduler using batch sampling
    - Probes all workers for queue length
    - Assigns tasks immediately
    - Measures wait/service/response times and RPC counts

late_binding.cpp
    Late binding scheduler
    - Workers request tasks when they become free
    - Reduces load imbalance and stale probes
    - Records performance metrics

late_binding_with_pro.cpp
    Late binding + proactive cancellation
    - After issuing requests, cancels extra reservations
    - Designed for high-load scenarios
    - Measures RPC overhead and timing improvements


RUNNING THE EXPERIMENT
----------------------

STEP 1 — Start all 6 workers (on their respective VMs):
   ./worker 9100

Make sure each worker displays:
   [worker] Listening on 9100


STEP 2 — Edit each scheduler file to include the full worker list:

vector<Worker> workers = {
    {"10.96.1.135", 9100},
    {"10.96.1.136", 9100},
    {"10.96.1.145", 9100},
    {"10.96.1.137", 9100},
    {"10.96.1.161", 9100},
    {"10.96.1.157", 9100}
};

This ensures all schedulers see the same workers (membership),
but they do NOT share worker load information (state).


STEP 3 — Run all 3 schedulers simultaneously on their respective VMs:

Scheduler A (10.96.1.131):
   ./batch    > A_batch.log
   ./lb       > A_lb.log
   ./lb_pro   > A_lbpro.log

Scheduler B (10.96.1.142):
   ./batch    > B_batch.log
   ./lb       > B_lb.log
   ./lb_pro   > B_lbpro.log

Scheduler C (10.96.1.156):
   ./batch    > C_batch.log
   ./lb       > C_lb.log
   ./lb_pro   > C_lbpro.log

Each scheduler runs locally and independently.


STEP 4 — Collect Logs
---------------------
Each scheduler prints:

- Average wait time per job
- Average service time per job
- Average response time per job
- Average RPC calls per job
- Job mixture: 90% short tasks, 10% heavy tasks

Final analysis can average these metrics across all 3 scheduler logs.


HOW THE WORKLOAD IS GENERATED
-----------------------------
Inside each scheduler source file:

- Jobs are generated locally at the scheduler
- 90% of jobs are short (≈ 30 ms)
- 10% of jobs are heavy (≈ 400 ms)
- Each job is broken into multiple tasks (parallel job model)
- Tasks are dispatched to distributed workers

Schedulers do NOT receive jobs from external systems.


NOTES
-----
- Knowing worker IPs is NOT global knowledge.
  Only worker addresses (membership) are stored—not dynamic state.

- Decentralization comes from:
  - 3 schedulers running independently
  - No shared state
  - No centralized authority
  - No global load table

- You may increase the number of jobs by modifying the scheduler files:
     int jobs = 100;

- You can adjust worker count by editing the vector<Worker> list.


CONCLUSION
----------
This distributed experiment evaluates three decentralized scheduling
algorithms under a real multi-VM cluster. It reproduces the qualitative
behavior seen in the Sparrow paper, including improvements from
late binding and proactive cancellation, while remaining simple to deploy
in virtualized environments such as OpenStack.
