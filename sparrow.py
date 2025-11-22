import simpy
import random
import statistics
import argparse
import uuid


def ms(x):
    return float(x)


# ============================================================
# WORKER (Unknown task durations — Sparrow model)
# ============================================================
class Worker:
    def __init__(self, env, wid, net_delay):
        self.env = env
        self.id = wid
        self.net = net_delay

        self.running = 0
        self.reservations = {}

        # Metrics
        self.busy_time = 0
        self.last_start_time = None
        self.task_metrics = []     # (jobid, tid, dur, start, end, wait)

    # 90% short (30 ms), 10% long (400 ms)
    def sample_duration(self):
        return random.choices([30, 400], [0.9, 0.1])[0]

    # ---------------------------------------------------------
    # RPC handlers
    # ---------------------------------------------------------
    def handle_probe(self):
        return f"Q {self.running + len(self.reservations)}"

    def handle_assign(self, jobid, tid, sched):
        dur = self.sample_duration()
        self.running += 1
        self.env.process(self._exec(jobid, tid, dur, sched, assigned_at=self.env.now))
        return "OK"

    def handle_request(self, jobid, tid, sched):
        rid = uuid.uuid4().hex[:8]
        dur = self.sample_duration()
        self.reservations[rid] = (jobid, tid, dur, sched, self.env.now)
        return f"RID {rid}"

    def handle_assign_rid(self, rid):
        if rid not in self.reservations:
            return "ERR"

        jobid, tid, dur, sched, req_time = self.reservations.pop(rid)
        self.running += 1

        self.env.process(
            self._exec(jobid, tid, dur, sched, assigned_at=req_time)
        )
        return "OK"

    def handle_cancel(self, rid):
        self.reservations.pop(rid, None)
        return "CANCELLED"

    # ---------------------------------------------------------
    # Task execution with detailed metrics
    # ---------------------------------------------------------
    def _exec(self, jobid, tid, dur, sched, assigned_at):
        start = self.env.now
        wait_time = start - assigned_at

        self.last_start_time = start

        yield self.env.timeout(ms(dur))
        end = self.env.now

        self.running -= 1

        # Busy time metric
        self.busy_time += (end - start)

        # Save task metrics
        self.task_metrics.append({
            "jobid": jobid,
            "tid": tid,
            "duration": dur,
            "start": start,
            "end": end,
            "wait": wait_time,
            "response": end - assigned_at
        })

        yield self.env.timeout(ms(self.net))
        sched.notify_done(jobid, tid)


# ============================================================
# SCHEDULER
# ============================================================
class Scheduler:
    def __init__(self, env, name, workers, ndelay,
                 mode, jobs, m, d):
        self.env = env
        self.name = name
        self.workers = workers
        self.nd = ndelay
        self.mode = mode

        self.jobs = jobs
        self.tasks = m
        self.d = d

        # RPC metrics
        self.rpc = 0
        self.rpc_probe_count = 0
        self.rpc_assign_count = 0
        self.rpc_request_count = 0
        self.rpc_cancel_count = 0
        self.rpc_assign_rid_count = 0

        # Reservations
        self.reservations_created = 0
        self.reservations_used = 0
        self.reservations_wasted = 0

        # Job events
        self.jobinfo = {}
        self.wait_events = {}  # (jobid, tid) → Event

        env.process(self.run())

    # -------------------------------------------------------
    # Network RPC wrappers
    # -------------------------------------------------------
    def rpc_probe(self, w):
        self.rpc += 1
        self.rpc_probe_count += 1
        yield self.env.timeout(ms(self.nd))
        rep = w.handle_probe()
        yield self.env.timeout(ms(self.nd))
        return rep

    def rpc_assign(self, w, jobid, tid):
        self.rpc += 1
        self.rpc_assign_count += 1
        yield self.env.timeout(ms(self.nd))
        rep = w.handle_assign(jobid, tid, self)
        yield self.env.timeout(ms(self.nd))
        return rep

    def rpc_request(self, w, jobid, tid):
        self.rpc += 1
        self.rpc_request_count += 1
        yield self.env.timeout(ms(self.nd))
        rep = w.handle_request(jobid, tid, self)
        self.reservations_created += 1
        yield self.env.timeout(ms(self.nd))
        return rep

    def rpc_assign_rid(self, w, rid):
        self.rpc += 1
        self.rpc_assign_rid_count += 1
        self.reservations_used += 1
        yield self.env.timeout(ms(self.nd))
        rep = w.handle_assign_rid(rid)
        yield self.env.timeout(ms(self.nd))
        return rep

    def rpc_cancel(self, w, rid):
        self.rpc += 1
        self.rpc_cancel_count += 1
        self.reservations_wasted += 1
        yield self.env.timeout(ms(self.nd))
        rep = w.handle_cancel(rid)
        yield self.env.timeout(ms(self.nd))
        return rep

    # -------------------------------------------------------
    # Worker callback
    # -------------------------------------------------------
    def notify_done(self, jobid, tid):
        ev = self.wait_events[(jobid, tid)]
        if not ev.triggered:
            ev.succeed()

    # -------------------------------------------------------
    # Scheduler main loop
    # -------------------------------------------------------
    def run(self):

        for j in range(self.jobs):
            jobid = f"{self.name}-J{j}"
            start_time = self.env.now
            self.jobinfo[jobid] = {"start": start_time}

            # Wait events for all tasks
            evs = []
            for t in range(self.tasks):
                e = simpy.Event(self.env)
                self.wait_events[(jobid, f"T{t}")] = e
                evs.append(e)

            # ------------------------------------------------
            # BATCH SAMPLING
            # ------------------------------------------------
            if self.mode == "batch":
                sample_n = min(len(self.workers), self.d * self.tasks)
                sampled = random.sample(self.workers, sample_n)

                reqs = [self.env.process(self.rpc_probe(w)) for w in sampled]
                all_ev = yield simpy.AllOf(self.env, reqs)
                results = list(all_ev.values())

                qlist = []
                for i, rep in enumerate(results):
                    q = int(rep.split()[1])
                    qlist.append((q, sampled[i]))

                qlist.sort(key=lambda x: x[0])
                chosen = [w for (q, w) in qlist[:self.tasks]]

                assigns = [
                    self.env.process(self.rpc_assign(w, jobid, f"T{t}"))
                    for t, w in enumerate(chosen)
                ]
                yield simpy.AllOf(self.env, assigns)

            # ------------------------------------------------
            # LATE BINDING + LatePro
            # ------------------------------------------------
            else:
                sample_n = min(len(self.workers), self.d * self.tasks)
                sampled = random.sample(self.workers, sample_n)

                reqs = [
                    self.env.process(self.rpc_request(w, jobid, f"T{i}"))
                    for i, w in enumerate(sampled)
                ]

                all_ev = yield simpy.AllOf(self.env, reqs)
                results = list(all_ev.values())

                reservations = []
                for i, rep in enumerate(results):
                    if rep.startswith("RID"):
                        rid = rep.split()[1]
                        reservations.append((rid, sampled[i]))

                chosen = reservations[:self.tasks]

                assigns = [
                    self.env.process(self.rpc_assign_rid(w, rid))
                    for (rid, w) in chosen
                ]
                yield simpy.AllOf(self.env, assigns)

                # CANCEL UNUSED
                if self.mode == "latepro":
                    unused = reservations[self.tasks:]
                    cancels = [
                        self.env.process(self.rpc_cancel(w, rid))
                        for (rid, w) in unused
                    ]
                    if cancels:
                        yield simpy.AllOf(self.env, cancels)

            # ------------------------------------------------
            # Wait until all tasks finish
            # ------------------------------------------------
            yield simpy.AllOf(self.env, evs)
            self.jobinfo[jobid]["done"] = self.env.now

    # -------------------------------------------------------
    # Extract job metrics
    # -------------------------------------------------------
    def results(self):
        comp = []
        for jobid, info in self.jobinfo.items():
            comp.append(info["done"] - info["start"])

        return {
            "completion": statistics.mean(comp),
            "rpc": self.rpc / len(comp),
            "rpcs_total": self.rpc,
            "probe": self.rpc_probe_count,
            "assign": self.rpc_assign_count,
            "req": self.rpc_request_count,
            "assign_rid": self.rpc_assign_rid_count,
            "cancel": self.rpc_cancel_count,
            "reserv_created": self.reservations_created,
            "reserv_used": self.reservations_used,
            "reserv_wasted": self.reservations_wasted
        }


# ============================================================
# RUN SIMULATION
# ============================================================
def run_sim(workers, schedulers, jobs, m, d, nd, mode, seed):
    random.seed(seed)
    env = simpy.Environment()

    wlist = [Worker(env, i, nd) for i in range(workers)]
    slist = [
        Scheduler(env, f"S{i}", wlist, nd, mode,
                  jobs, m, d)
        for i in range(schedulers)
    ]

    env.run(until=ms(jobs * m * 600 + 20000))

    # Gather scheduler metrics
    S = [s.results() for s in slist]

    # Gather worker metrics
    all_tasks = []
    for w in wlist:
        all_tasks.extend(w.task_metrics)

    # Compute metrics
    return {
        "completion": statistics.mean([x["completion"] for x in S]),
        "rpc": statistics.mean([x["rpc"] for x in S]),

        # RPC breakdown
        "probe": sum([x["probe"] for x in S]),
        "assign": sum([x["assign"] for x in S]),
        "request": sum([x["req"] for x in S]),
        "assign_rid": sum([x["assign_rid"] for x in S]),
        "cancel": sum([x["cancel"] for x in S]),

        # Reservation metrics
        "reserv_created": sum([x["reserv_created"] for x in S]),
        "reserv_used": sum([x["reserv_used"] for x in S]),
        "reserv_wasted": sum([x["reserv_wasted"] for x in S]),

        # Task metrics
        "task_wait": statistics.mean([t["wait"] for t in all_tasks]),
        "task_resp": statistics.mean([t["response"] for t in all_tasks]),
        "task_service": statistics.mean([t["duration"] for t in all_tasks]),
    }


# ============================================================
# CLI
# ============================================================
if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--workers", type=int, default=10)
    p.add_argument("--schedulers", type=int, default=3)
    p.add_argument("--jobs", type=int, default=50)
    p.add_argument("--tasks", type=int, default=3)
    p.add_argument("--probe", type=int, default=2)
    p.add_argument("--mode", choices=["batch", "late", "latepro"], default="batch")
    p.add_argument("--ndelay", type=float, default=1.0)
    p.add_argument("--seed", type=int, default=42)
    a = p.parse_args()

    print("\n===================================================")
    print("               SPARROW SIMULATION")
    print("===================================================")
    print(f"Workers            : {a.workers}")
    print(f"Schedulers         : {a.schedulers}")
    print(f"Jobs               : {a.jobs}")
    print(f"Tasks per Job      : {a.tasks}")
    print(f"Probe Ratio (d)    : {a.probe}")
    print(f"Mode               : {a.mode}")
    print(f"Network Delay      : {a.ndelay} ms")
    print(f"Seed               : {a.seed}")
    print("===================================================\n")

    r = run_sim(a.workers, a.schedulers, a.jobs,
                a.tasks, a.probe, a.ndelay,
                a.mode, a.seed)

    print("=============== RESULTS =================")
    print(f"Avg Job Completion Time  : {r['completion']:.2f} ms")
    print(f"Avg RPC per Job          : {r['rpc']:.2f}\n")

    print(f"Task Wait Time (avg)     : {r['task_wait']:.2f} ms")
    print(f"Task Response Time (avg) : {r['task_resp']:.2f} ms")
    print(f"Task Service Time (avg)  : {r['task_service']:.2f} ms\n")

    print("RPC BREAKDOWN:")
    print(f"  Probes                 : {r['probe']}")
    print(f"  Requests               : {r['request']}")
    print(f"  Assign                 : {r['assign']}")
    print(f"  Assign RID             : {r['assign_rid']}")
    print(f"  Cancel                 : {r['cancel']}\n")

    print("RESERVATION METRICS:")
    print(f"  Created                : {r['reserv_created']}")
    print(f"  Used                   : {r['reserv_used']}")
    print(f"  Wasted                 : {r['reserv_wasted']}")
    print("==========================================")
