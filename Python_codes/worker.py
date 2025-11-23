# worker.py
import simpy
import uuid
import random

def ms(x):
    return float(x)

class Worker:
    """
    Worker provides:
    - handle_probe() -> "Q <queue_len>"
    - handle_request(jobid, tid, sched) -> "RID <rid>"
    - handle_assign(jobid, tid, sched) -> "OK"
    - handle_assign_rid(rid) -> "OK" or "ERR"
    - handle_cancel(rid) -> "CANCELLED"
    """
    def __init__(self, env, wid, net_delay):
        self.env = env
        self.id = wid
        self.net = net_delay

        self.running = 0
        self.reservations = {}   # rid -> (jobid, tid, dur, sched, assigned_at)

        # metrics
        self.busy_time = 0.0
        self.task_metrics = []   # dicts: {jobid, tid, duration, start, end, wait, response}

    def sample_duration(self):
        # 90% short (30 ms), 10% long (400 ms)
        return random.choices([5, 50], weights=[0.9, 0.1])[0]

    def handle_probe(self):
        # The reported queue length is running + reserved
        return f"Q {self.running + len(self.reservations)}"

    def handle_request(self, jobid, tid, sched):
        rid = uuid.uuid4().hex[:8]
        dur = self.sample_duration()
        self.reservations[rid] = (jobid, tid, dur, sched, self.env.now)
        return f"RID {rid}"

    def handle_assign(self, jobid, tid, sched):
        dur = self.sample_duration()
        assigned_at = self.env.now
        self.running += 1
        # start execution
        self.env.process(self._exec(jobid, tid, dur, sched, assigned_at))
        return "OK"

    def handle_assign_rid(self, rid):
        if rid not in self.reservations:
            return "ERR"
        jobid, tid, dur, sched, assigned_at = self.reservations.pop(rid)
        self.running += 1
        self.env.process(self._exec(jobid, tid, dur, sched, assigned_at))
        return "OK"

    def handle_cancel(self, rid):
        self.reservations.pop(rid, None)
        return "CANCELLED"

    def _exec(self, jobid, tid, dur, sched, assigned_at):
        start = self.env.now
        wait_time = start - assigned_at
        yield self.env.timeout(ms(dur))
        end = self.env.now

        # update worker state and metrics
        self.running -= 1
        self.busy_time += (end - start)
        self.task_metrics.append({
            "jobid": jobid,
            "tid": tid,
            "duration": dur,
            "start": start,
            "end": end,
            "wait": wait_time,
            "response": end - assigned_at
        })

        # simulate network delay before notifying scheduler
        yield self.env.timeout(ms(self.net))
        # notify scheduler the task is done
        try:
            sched.notify_done(jobid, tid)
        except Exception:
            # scheduler might not exist or notify_done may differ
            pass
