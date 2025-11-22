#!/usr/bin/env python3
import socket, threading, time, random, argparse
from statistics import mean

############################################################
# GLOBALS
############################################################

done_events = {}      # (jobid, taskid) -> Event
lock = threading.Lock()
MY_IP = "127.0.0.1"   # scheduler IP (used for DONE callbacks)

############################################################
# DONE LISTENER THREAD
############################################################
def listen_done(port=9200):
    """Scheduler listens for DONE messages from workers."""
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", port))
    s.listen(200)
    print("[scheduler] Listening for DONE on port 9200")

    while True:
        conn, addr = s.accept()
        data = conn.recv(4096).decode().strip().split()
        conn.close()

        if not data:
            continue

        if data[0] == "DONE":
            jobid = data[1]
            taskid = data[2]

            # Find event safely
            with lock:
                evt = done_events.get((jobid, taskid))

            if evt is not None:
                evt.set()
            else:
                print(f"[scheduler] WARNING: DONE for unknown ({jobid}, {taskid})")


############################################################
# RPC UTILITY
############################################################
def rpc(ip, port, message):
    """Send a blocking RPC; returns (ok, reply_string)."""
    try:
        s = socket.socket()
        s.settimeout(1.0)
        s.connect((ip, port))
        s.sendall((message + "\n").encode())
        reply = s.recv(4096).decode().strip()
        s.close()
        return True, reply
    except:
        return False, ""


############################################################
# MAIN SCHEDULER LOGIC
############################################################
def run_scheduler(workers, mode="batch", jobs=100, m=3, d=2):

    results = {
        "wait": [],
        "service": [],
        "response": [],
        "rpc": []
    }

    for job in range(jobs):
        jobid = f"J{job}"

        # 10% heavy jobs
        heavy = (random.randint(1, 10) == 1)
        dur = 400 if heavy else 30

        start_time = time.time()

        # Prepare DONE wait events
        local_events = []
        for t in range(m):
            evt = threading.Event()
            with lock:
                done_events[(jobid, f"T{t}")] = evt
            local_events.append(evt)

        rpc_count = 0

        ###################################################################
        # 1. BATCH SAMPLING
        ###################################################################
        if mode == "batch":

            # Sample d*m workers (or all if fewer)
            sample = random.sample(workers, min(d*m, len(workers)))

            # PROBE phase
            loads = []
            for (ip, port) in sample:
                ok, rep = rpc(ip, port, "PROBE")
                rpc_count += 1
                q = int(rep.split()[1]) if ok and rep.startswith("Q") else 999999
                loads.append((q, (ip, port)))

            # Choose m least-loaded
            loads.sort()
            chosen = [w for (_, w) in loads[:m]]

            # ASSIGN phase (immediate execution)
            for t in range(m):
                ip, port = chosen[t]
                rpc(ip, port, f"ASSIGN {jobid} T{t} {dur} {MY_IP}")
                rpc_count += 1

        ###################################################################
        # 2. LATE BINDING & 3. LATE BINDING + PROACTIVE CANCELLATION
        ###################################################################
        elif mode in ("late", "latepro"):

            sample = random.sample(workers, min(d*m, len(workers)))
            reservations = []   # list of (rid, ip, port, taskid)

            # REQUEST phase (RESERVATIONS)
            for t, (ip, port) in enumerate(sample):
                taskid = f"T{t}"
                ok, rep = rpc(ip, port, f"REQUEST {jobid} {taskid} {dur} {MY_IP}")
                rpc_count += 1
                if ok and rep.startswith("RID"):
                    rid = rep.split()[1]
                    reservations.append((rid, ip, port, taskid))

            # CHOOSE m reservations
            chosen = reservations[:m]

            # ASSIGN_RID selected reservations
            for (rid, ip, port, taskid) in chosen:
                rpc(ip, port, f"ASSIGN_RID {rid}")
                rpc_count += 1

            # PROACTIVE CANCELLATION for leftover reservations
            if mode == "latepro":
                for (rid, ip, port, taskid) in reservations[m:]:
                    rpc(ip, port, f"CANCEL {rid}")
                    rpc_count += 1

        ###################################################################
        # WAIT FOR ALL TASKS TO COMPLETE
        ###################################################################
        for evt in local_events:
            evt.wait()

        end_time = time.time()
        completion = (end_time - start_time) * 1000

        results["response"].append(completion)
        results["service"].append(dur)
        results["wait"].append(completion - dur)
        results["rpc"].append(rpc_count)

    ###################################################################
    # PRINT FINAL SUMMARY FOR THIS MODE
    ###################################################################
    print(f"\n=== {mode.upper()} — RESULTS ===")
    print(f"Avg completion time: {mean(results['response']):.2f} ms")
    print(f"Avg wait time:        {mean(results['wait']):.2f} ms")
    print(f"Avg service time:     {mean(results['service']):.2f} ms")
    print(f"Avg RPC per job:      {mean(results['rpc']):.2f}")

    return results


############################################################
# ENTRY POINT
############################################################
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", required=True)
    parser.add_argument("--mode", choices=["batch","late","latepro"], required=True)
    parser.add_argument("--jobs", type=int, default=100)
    parser.add_argument("--tasks", type=int, default=3)
    parser.add_argument("--probe", type=int, default=2)
    args = parser.parse_args()

    # Parse workers list
    workers = []
    for w in args.workers.split(","):
        ip, port = w.split(":")
        workers.append((ip, int(port)))

    # Launch DONE listener
    threading.Thread(target=listen_done, daemon=True).start()
    time.sleep(0.2)

    # Run scheduler
    run_scheduler(workers, args.mode, args.jobs, args.tasks, args.probe)
