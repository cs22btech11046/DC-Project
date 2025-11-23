#!/bin/bash

WORKER_LIST=(5 10 20 40 80)
MODES=("batch" "late" "latepro")

SCHEDS=3
JOBS=300
PROBE=2
NDELAY=2.0
JOBSIZE="uniform"
SEED=42

OUTFILE="results_workers.csv"
echo "workers,mode,completion,rpc,task_wait,task_resp,task_service" > $OUTFILE

echo "=== Varying Number of Workers ==="

for MODE in "${MODES[@]}"; do
    echo "=== MODE: $MODE ==="

    for W in "${WORKER_LIST[@]}"; do
        echo "--- Workers = $W ---"

        tot_c=0; tot_rpc=0; tot_w=0; tot_r=0; tot_s=0;

        for RUN in {1..10}; do
            OUT=$(python3 simulation.py \
                --workers $W \
                --schedulers $SCHEDS \
                --jobs $JOBS \
                --mode $MODE \
                --probe $PROBE \
                --ndelay $NDELAY \
                --jobsize $JOBSIZE \
                --seed $((SEED+RUN)) )

            c=$(echo "$OUT" | grep "Avg completion" | awk '{print $3}')
            rpc=$(echo "$OUT" | grep "Avg RPC" | awk '{print $3}')
            w=$(echo "$OUT" | grep "Task wait" | awk '{print $4}')
            r=$(echo "$OUT" | grep "Task resp" | awk '{print $4}')
            s=$(echo "$OUT" | grep "Task service" | awk '{print $4}')

            tot_c=$(echo "$tot_c + $c" | bc)
            tot_rpc=$(echo "$tot_rpc + $rpc" | bc)
            tot_w=$(echo "$tot_w + $w" | bc)
            tot_r=$(echo "$tot_r + $r" | bc)
            tot_s=$(echo "$tot_s + $s" | bc)
        done

        avg_c=$(echo "scale=4; $tot_c/10" | bc)
        avg_rpc=$(echo "scale=4; $tot_rpc/10" | bc)
        avg_w=$(echo "scale=4; $tot_w/10" | bc)
        avg_r=$(echo "scale=4; $tot_r/10" | bc)
        avg_s=$(echo "scale=4; $tot_s/10" | bc)

        echo "$W,$MODE,$avg_c,$avg_rpc,$avg_w,$avg_r,$avg_s" >> $OUTFILE
    done
done

echo "Saved to $OUTFILE"
