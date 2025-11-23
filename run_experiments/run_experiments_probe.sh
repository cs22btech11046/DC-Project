#!/bin/bash

# Probe ratios to test
PROBES=(1 2 3 4 6 8 10)

MODES=("batch" "late" "latepro")
WORKERS=50
SCHEDS=5
JOBS=300
NDELAY=2.0
JOBSIZE="uniform"
SEED=42

OUTFILE="results_probe.csv"
echo "probe,mode,completion,rpc,task_wait,task_resp,task_service" > $OUTFILE

echo "=== Varying Probe Ratio ==="

for MODE in "${MODES[@]}"; do
    echo "=== MODE: $MODE ==="

    for P in "${PROBES[@]}"; do
        echo "--- Probe = $P ---"

        total_c=0; total_rpc=0; total_w=0; total_r=0; total_s=0;

        for RUN in {1..10}; do
            OUT=$(python3 simulation.py \
                --workers $WORKERS \
                --schedulers $SCHEDS \
                --jobs $JOBS \
                --mode $MODE \
                --probe $P \
                --ndelay $NDELAY \
                --jobsize $JOBSIZE \
                --seed $((SEED+RUN)) )

            c=$(echo "$OUT" | grep "Avg completion" | awk '{print $3}')
            rpc=$(echo "$OUT" | grep "Avg RPC" | awk '{print $3}')
            w=$(echo "$OUT" | grep "Task wait" | awk '{print $4}')
            r=$(echo "$OUT" | grep "Task resp" | awk '{print $4}')
            s=$(echo "$OUT" | grep "Task service" | awk '{print $4}')

            total_c=$(echo "$total_c + $c" | bc)
            total_rpc=$(echo "$total_rpc + $rpc" | bc)
            total_w=$(echo "$total_w + $w" | bc)
            total_r=$(echo "$total_r + $r" | bc)
            total_s=$(echo "$total_s + $s" | bc)
        done

        avg_c=$(echo "scale=4; $total_c/10" | bc)
        avg_rpc=$(echo "scale=4; $total_rpc/10" | bc)
        avg_w=$(echo "scale=4; $total_w/10" | bc)
        avg_r=$(echo "scale=4; $total_r/10" | bc)
        avg_s=$(echo "scale=4; $total_s/10" | bc)

        echo "$P,$MODE,$avg_c,$avg_rpc,$avg_w,$avg_r,$avg_s" >> $OUTFILE
    done
done

echo "Saved to $OUTFILE"
