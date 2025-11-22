#!/usr/bin/env python3
import subprocess, time, sys, os

WORKERS = 4
BASE = 9100

def start_workers():
    procs=[]
    for i in range(WORKERS):
        port = BASE+i
        p = subprocess.Popen([sys.executable,"worker.py",str(port)])
        procs.append(p)
    time.sleep(1)
    return procs

def stop_workers(procs):
    for p in procs:
        p.terminate()

def run(mode):
    worker_list=",".join([f"127.0.0.1:{BASE+i}" for i in range(WORKERS)])
    print(f"\nRunning mode = {mode}")
    subprocess.run([sys.executable,"scheduler.py","--workers",worker_list,
                    "--mode",mode,"--jobs","100"])

if __name__=="__main__":
    procs=start_workers()
    run("batch")
    run("late")
    run("latepro")
    stop_workers(procs)
