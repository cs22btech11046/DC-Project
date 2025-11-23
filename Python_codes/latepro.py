import simpy
import random
import statistics

def ms(x):
    return float(x)

class LateProScheduler:
    """
    LatePro: like LateScheduler but cancels unused reservations (proactive cancellation).
    """
    def __init__(self, env, name, workers, ndelay, mode, jobs, probe, seed=None):
        self.env = env
        self.name = name
        self.workers = workers
        self.nd = ndelay
        self.mode = mode
        self.jobs = jobs
        self.d = probe

        # counters
        self.rpc_total = 0
        self.rpc_probe_count = 0
        self.rpc_assign_count = 0
        self.rpc_request_count = 0
        self.rpc_assign_rid_count = 0
        self.rpc_cancel_count = 0

        self.res_created = 0
        self.res_used = 0
        self.res_wasted = 0

        self.jobinfo = {}
        self.wait_events = {}

        self.m_job_sampler = lambda: 3

        if seed is not None:
            random.seed(seed + hash(self.name))

        env.process(self.run())

    # RPC wrappers
    def rpc_probe(self, w):
        self.rpc_total += 1; self.rpc_probe_count += 1
        yield self.env.timeout(ms(self.nd))
        rep = w.handle_probe()
        yield self.env.timeout(ms(self.nd))
        return rep

    def rpc_assign(self, w, jobid, tid):
        self.rpc_total += 1; self.rpc_assign_count += 1
        yield self.env.timeout(ms(self.nd))
        rep = w.handle_assign(jobid, tid, self)
        yield self.env.timeout(ms(self.nd))
        return rep

    def rpc_request(self, w, jobid, tid):
        self.rpc_total += 1; self.rpc_request_count += 1
        yield self.env.timeout(ms(self.nd))
        rep = w.handle_request(jobid, tid, self)
        self.res_created += 1
        yield self.env.timeout(ms(self.nd))
        return rep

    def rpc_assign_rid(self, w, rid):
        self.rpc_total += 1; self.rpc_assign_rid_count += 1
        self.res_used += 1
        yield self.env.timeout(ms(self.nd))
        rep = w.handle_assign_rid(rid)
        yield self.env.timeout(ms(self.nd))
        return rep

    def rpc_cancel(self, w, rid):
        self.rpc_total += 1; self.rpc_cancel_count += 1
        self.res_wasted += 1
        yield self.env.timeout(ms(self.nd))
        rep = w.handle_cancel(rid)
        yield self.env.timeout(ms(self.nd))
        return rep

    def notify_done(self, jobid, tid):
        ev = self.wait_events.get((jobid, tid))
        if ev and not ev.triggered:
            ev.succeed()

    def run(self):
        for j in range(self.jobs):
            jobid = f"{self.name}-J{j}"
            self.jobinfo[jobid] = {"start": self.env.now}

            m_job = max(1, int(self.m_job_sampler()))
            self.jobinfo[jobid]["tasks"] = m_job

            evs = []
            for t in range(m_job):
                e = simpy.Event(self.env)
                self.wait_events[(jobid, f"T{t}")] = e
                evs.append(e)

            sample_n = min(len(self.workers), max(1, int(self.d * m_job)))
            sampled = random.sample(self.workers, sample_n)

            # request reservations
            reqs = [self.env.process(self.rpc_request(w, jobid, f"T{i}")) for i, w in enumerate(sampled)]
            all_ev = yield simpy.AllOf(self.env, reqs)
            req_results = list(all_ev.values())

            reservations = []
            for i, rep in enumerate(req_results):
                if isinstance(rep, str) and rep.startswith("RID"):
                    rid = rep.split()[1]
                    reservations.append((rid, sampled[i]))

            # choose up to m_job reservations
            chosen = reservations[:m_job]
            self.res_used += len(chosen)

            assigns = [self.env.process(self.rpc_assign_rid(w, rid)) for (rid, w) in chosen]
            if assigns:
                yield simpy.AllOf(self.env, assigns)

            # cancel unused reservations proactively
            unused = reservations[m_job:]
            if unused:
                cancels = [self.env.process(self.rpc_cancel(w, rid)) for (rid, w) in unused]
                yield simpy.AllOf(self.env, cancels)

            # if not enough reservations assigned, fallback to probe+assign
            if len(chosen) < m_job:
                need = m_job - len(chosen)
                sample2_n = min(len(self.workers), max(1, int(self.d * m_job)))
                sampled2 = random.sample(self.workers, sample2_n)
                probes2 = [self.env.process(self.rpc_probe(w)) for w in sampled2]
                all_ev2 = yield simpy.AllOf(self.env, probes2)
                probe_results2 = list(all_ev2.values())

                qlist2 = []
                for i, rep in enumerate(probe_results2):
                    try:
                        q = int(rep.split()[1])
                    except Exception:
                        q = 0
                    qlist2.append((q, sampled2[i]))
                qlist2.sort(key=lambda x: x[0])

                chosen_workers2 = [qlist2[i % len(qlist2)][1] for i in range(need)]
                assigns2 = [self.env.process(self.rpc_assign(w, jobid, f"T{len(chosen)+t}")) for t, w in enumerate(chosen_workers2)]
                if assigns2:
                    yield simpy.AllOf(self.env, assigns2)

            yield simpy.AllOf(self.env, evs)
            self.jobinfo[jobid]["done"] = self.env.now

    def results(self):
        comps = [info["done"] - info["start"] for jobid, info in self.jobinfo.items() if "done" in info]
        avg = statistics.mean(comps) if comps else 0.0

        p95 = p99 = 0.0
        if comps:
            if len(comps) >= 100:
                p95 = statistics.quantiles(comps, n=100)[94]
                p99 = statistics.quantiles(comps, n=100)[98]
            else:
                p95 = statistics.quantiles(comps, n=100)[min(94, len(comps)-1)]
                p99 = statistics.quantiles(comps, n=100)[min(98, len(comps)-1)]

        return {
            "completion": avg,
            "p95": p95,
            "p99": p99,
            "rpc_per_job": (self.rpc_total / len(comps)) if comps else 0.0,
            "rpc_total": self.rpc_total,
            "probe": self.rpc_probe_count,
            "assign": self.rpc_assign_count,
            "request": self.rpc_request_count,
            "assign_rid": self.rpc_assign_rid_count,
            "cancel": self.rpc_cancel_count,
            "reserv_created": self.res_created,
            "reserv_used": self.res_used,
            "reserv_wasted": self.res_wasted,
            "tasks_avg": statistics.mean([info["tasks"] for info in self.jobinfo.values()]) if self.jobinfo else 0.0
        }
