import argparse
import simpy
import random
import statistics

from worker import Worker
from batch import BatchScheduler
from late import LateScheduler
from latepro import LateProScheduler


def ms(x):
    return float(x)


def make_scheduler_class(mode):
    if mode == "batch":
        return BatchScheduler
    elif mode == "late":
        return LateScheduler
    elif mode == "latepro":
        return LateProScheduler
    else:
        raise ValueError("unknown mode")


def make_sampler(kind, params):
    # returns a zero-arg function that samples tasks-per-job
    if kind == "mixed":
        def sampler():
            r = random.random()
            if r < 0.7:
                return random.randint(1, min(5, params.get("max", 100)))
            elif r < 0.9:
                return random.randint(6, min(20, params.get("max", 100)))
            else:
                return random.randint(21, min(200, params.get("max", 2000)))
        return sampler
    elif kind == "uniform":
        def sampler():
            return random.randint(params.get("lo", 1), params.get("hi", 10))
        return sampler
    elif kind == "powerlaw":
        choices = params.get("choices", [1,2,3,4,8,16,32,64,128])
        weights = params.get("weights", None)
        if weights is None:
            weights = [1.0/(i+1) for i in range(len(choices))]
        def sampler():
            return random.choices(choices, weights=weights)[0]
        return sampler
    else:
        def sampler():
            return int(params.get("fixed", 3))
        return sampler


def run_sim(num_workers, num_scheds, jobs, probe, ndelay, mode, jobsize_kind, js_params, seed=42):
    random.seed(seed)
    env = simpy.Environment()

    workers = [Worker(env, i, ndelay) for i in range(num_workers)]
    SchedulerClass = make_scheduler_class(mode)

    sampler = make_sampler(jobsize_kind, js_params)

    scheds = []
    for i in range(num_scheds):
        sch = SchedulerClass(env, f"S{i}", workers, ndelay, mode, jobs, probe, seed=i+seed)
        sch.m_job_sampler = sampler
        scheds.append(sch)

    # run long enough
    env.run(until=ms(jobs * js_params.get("max", 100) * 200 + 20000))

    # collect scheduler metrics
    S = [s.results() for s in scheds]

    avg_completion = statistics.mean([s["completion"] for s in S]) if S else 0.0
    avg_rpc_per_job = statistics.mean([s["rpc_per_job"] for s in S]) if S else 0.0

    # collect task metrics from workers
    all_tasks = []
    for w in workers:
        all_tasks.extend(w.task_metrics)

    task_wait = statistics.mean([t["wait"] for t in all_tasks]) if all_tasks else 0.0
    task_resp = statistics.mean([t["response"] for t in all_tasks]) if all_tasks else 0.0
    task_service = statistics.mean([t["duration"] for t in all_tasks]) if all_tasks else 0.0

    total_busy = sum([w.busy_time for w in workers])
    total_time = env.now * len(workers) if env.now > 0 else 1.0
    util = (total_busy / total_time) * 100.0

    qlens = [w.running + len(w.reservations) for w in workers]
    imbalance = (max(qlens) + 1) / (min(qlens) + 1) if workers else 1.0

    return {
        "avg_completion": avg_completion,
        "avg_rpc_per_job": avg_rpc_per_job,
        "task_wait": task_wait,
        "task_resp": task_resp,
        "task_service": task_service,
        "util": util,
        "imbalance": imbalance,
        "sim_time": env.now,
        "sched_results": S,
    }


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--workers', type=int, default=10)
    p.add_argument('--schedulers', type=int, default=3)
    p.add_argument('--jobs', type=int, default=200)
    p.add_argument('--probe', type=int, default=2)
    p.add_argument('--mode', choices=['batch','late','latepro'], default='batch')
    p.add_argument('--ndelay', type=float, default=1.0)
    p.add_argument('--jobsize', choices=['mixed','uniform','powerlaw','fixed'], default='mixed')
    p.add_argument('--jobsize_max', type=int, default=200)
    p.add_argument('--jobsize_lo', type=int, default=1)
    p.add_argument('--jobsize_hi', type=int, default=8)
    p.add_argument('--seed', type=int, default=42)
    args = p.parse_args()

    js_params = {"max": args.jobsize_max, "lo": args.jobsize_lo, "hi": args.jobsize_hi}

    print('\n=== Running Sparrow multi-module simulation ===')
    print(f'Workers: {args.workers}  Schedulers: {args.schedulers}  Jobs: {args.jobs}  Mode: {args.mode}  Probe: {args.probe}')

    out = run_sim(
        args.workers,
        args.schedulers,
        args.jobs,
        args.probe,
        args.ndelay,
        args.mode,
        args.jobsize,
        js_params,
        args.seed
    )

    print('\n=== RESULTS ===')
    print(f"Avg completion: {out['avg_completion']:.2f} ms")
    print(f"Avg RPC/job:    {out['avg_rpc_per_job']:.2f}")
    print(f"Task wait (avg): {out['task_wait']:.2f} ms")
    print(f"Task resp (avg): {out['task_resp']:.2f} ms")
    print(f"Task service (avg): {out['task_service']:.2f} ms")
    print(f"Worker util: {out['util']:.2f}%  imbalance: {out['imbalance']:.2f}")
