#!/bin/bash

# Job sizes to test
JOB_LIST=(50 100 150 200 400 600 800 1000)

# Modes to test
MODES=("batch" "late" "latepro")

WORKERS=50
SCHEDS=5
PROBE=2
NDELAY=2.0
JOBSIZE="uniform"
SEED=42

OUTFILE="results.csv"

# Write CSV header
echo "jobs,mode,completion,rpc,task_wait,task_resp,task_service" > $OUTFILE

echo "=== Running experiment set for modes: batch, late, latepro ==="

# Loop over modes
for MODE in "${MODES[@]}"
do
    echo "==============================="
    echo "      MODE = $MODE"
    echo "==============================="

    # Loop over job sizes
    for J in "${JOB_LIST[@]}"
    do
        echo "--- Jobs = $J ---"

        total_completion=0
        total_rpc=0
        total_wait=0
        total_resp=0
        total_service=0

        util_sum=0
        imb_sum=0

        # 5 runs for averaging
        for RUN in {1..10}
        do
            echo "Run $RUN (jobs = $J, mode = $MODE)..."

            OUT=$(python3 simulation.py \
                --workers $WORKERS \
                --schedulers $SCHEDS \
                --jobs $J \
                --mode $MODE \
                --probe $PROBE \
                --ndelay $NDELAY \
                --jobsize $JOBSIZE \
                --seed $((SEED + RUN)) )

            # Extract metrics
            completion=$(echo "$OUT" | grep "Avg completion:" | awk '{print $3}')
            rpc=$(echo "$OUT" | grep "Avg RPC/job:" | awk '{print $3}')
            task_wait=$(echo "$OUT" | grep "Task wait" | awk '{print $4}')
            task_resp=$(echo "$OUT" | grep "Task resp" | awk '{print $4}')
            task_service=$(echo "$OUT" | grep "Task service" | awk '{print $4}')

            util=$(echo "$OUT" | grep "Worker util" | awk '{print $3}' | sed 's/%//')
            imb=$(echo "$OUT" | grep "imbalance:" | awk '{print $NF}')

            # Accumulate
            total_completion=$(echo "$total_completion + $completion" | bc)
            total_rpc=$(echo "$total_rpc + $rpc" | bc)
            total_wait=$(echo "$total_wait + $task_wait" | bc)
            total_resp=$(echo "$total_resp + $task_resp" | bc)
            total_service=$(echo "$total_service + $task_service" | bc)

            util_sum=$(echo "$util_sum + $util" | bc)
            imb_sum=$(echo "$imb_sum + $imb" | bc)
        done

        # Averages over 5 runs
        avg_completion=$(echo "scale=4; $total_completion / 5" | bc)
        avg_rpc=$(echo "scale=4; $total_rpc / 5" | bc)
        avg_wait=$(echo "scale=4; $total_wait / 5" | bc)
        avg_resp=$(echo "scale=4; $total_resp / 5" | bc)
        avg_service=$(echo "scale=4; $total_service / 5" | bc)

        avg_util=$(echo "scale=4; $util_sum / 5" | bc)
        avg_imb=$(echo "scale=4; $imb_sum / 5" | bc)

        # Append to CSV
        echo "$J,$MODE,$avg_completion,$avg_rpc,$avg_wait,$avg_resp,$avg_service" >> $OUTFILE

        echo "Worker util (avg): $avg_util%   imbalance (avg): $avg_imb"
        echo
    done
done

echo "=== All results saved to $OUTFILE ==="
