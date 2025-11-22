#!/usr/bin/env python3
import sys, socket, threading, time, uuid

running_tasks = 0
reservations = {}
lock = threading.Lock()

def send_done(sched_ip, jobid, taskid):
    """Notify scheduler that a task is finished."""
    try:
        s = socket.socket()
        s.connect((sched_ip, 9200))
        s.sendall(f"DONE {jobid} {taskid}\n".encode())
        s.close()
    except:
        pass

def run_task(duration, jobid, taskid, sched_ip):
    global running_tasks
    with lock:
        running_tasks += 1

    time.sleep(duration / 1000.0)

    with lock:
        running_tasks -= 1

    send_done(sched_ip, jobid, taskid)

def client_handler(conn, addr):
    global reservations
    try:
        data = conn.recv(4096).decode().strip().split()
        if not data:
            conn.close()
            return

        cmd = data[0]

        if cmd == "PROBE":
            with lock:
                q = running_tasks + len(reservations)
            conn.sendall(f"Q {q}\n".encode())

        elif cmd == "ASSIGN":
            jobid, taskid, dur = data[1], data[2], int(data[3])
            sched_ip = data[4]
            threading.Thread(target=run_task,
                             args=(dur, jobid, taskid, sched_ip),
                             daemon=True).start()
            conn.sendall(b"STARTED\n")

        elif cmd == "REQUEST":
            jobid, taskid, dur = data[1], data[2], int(data[3])
            sched_ip = data[4]
            rid = uuid.uuid4().hex[:8]
            with lock:
                reservations[rid] = (jobid, taskid, dur, sched_ip)
            conn.sendall(f"RID {rid}\n".encode())

        elif cmd == "ASSIGN_RID":
            rid = data[1]
            with lock:
                if rid not in reservations:
                    conn.sendall(b"ERR\n")
                    return
                jobid, taskid, dur, sched_ip = reservations.pop(rid)

            threading.Thread(target=run_task,
                             args=(dur, jobid, taskid, sched_ip),
                             daemon=True).start()
            conn.sendall(b"STARTED\n")

        elif cmd == "CANCEL":
            rid = data[1]
            with lock:
                reservations.pop(rid, None)
            conn.sendall(b"CANCELLED\n")

    except:
        pass

    conn.close()


def serve(port):
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", port))
    s.listen(64)

    print(f"[worker] Listening on {port}")
    sys.stdout.flush()

    while True:
        conn, addr = s.accept()
        threading.Thread(target=client_handler,
                         args=(conn, addr), daemon=True).start()


if __name__ == "__main__":
    port = int(sys.argv[1])
    serve(port)
