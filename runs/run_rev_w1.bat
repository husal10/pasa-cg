@echo off
setlocal
rem Additional sweeps (results_rev), window 1: 21 runs.
rem Run from the pasa_cg_code folder. Finished cells are skipped, so it can be restarted.
if not exist results_rev mkdir results_rev
if not exist data\net_c1_rev_w1 xcopy /I /Y /Q data\net_c1_phase_symmetric data\net_c1_rev_w1 >nul

echo [w1 1/21] results_rev/R1_field/symmetric/low/phase_symmetric
python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level low --fault-pattern phase_symmetric --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R1_field/symmetric/low/phase_symmetric
if errorlevel 1 echo FAILED w1 run 1: python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level low --fault-pattern phase_symmetric --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R1_field/symmetric/low/phase_symmetric >> results_rev\failures_w1.txt

echo [w1 2/21] results_rev/R1_field/symmetric/medium/single_approach
python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R1_field/symmetric/medium/single_approach
if errorlevel 1 echo FAILED w1 run 2: python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R1_field/symmetric/medium/single_approach >> results_rev\failures_w1.txt

echo [w1 3/21] results_rev/R1_field/symmetric/medium/cross_phase
python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern cross_phase --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R1_field/symmetric/medium/cross_phase
if errorlevel 1 echo FAILED w1 run 3: python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern cross_phase --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R1_field/symmetric/medium/cross_phase >> results_rev\failures_w1.txt

echo [w1 4/21] results_rev/R1_field/symmetric/medium/phase_symmetric
python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern phase_symmetric --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R1_field/symmetric/medium/phase_symmetric
if errorlevel 1 echo FAILED w1 run 4: python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern phase_symmetric --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R1_field/symmetric/medium/phase_symmetric >> results_rev\failures_w1.txt

echo [w1 5/21] results_rev/R1_field/symmetric/medium/distributed
python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern distributed --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R1_field/symmetric/medium/distributed
if errorlevel 1 echo FAILED w1 run 5: python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern distributed --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R1_field/symmetric/medium/distributed >> results_rev\failures_w1.txt

echo [w1 6/21] results_rev/R1_field/symmetric/high/single_approach
python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern single_approach --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R1_field/symmetric/high/single_approach
if errorlevel 1 echo FAILED w1 run 6: python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern single_approach --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R1_field/symmetric/high/single_approach >> results_rev\failures_w1.txt

echo [w1 7/21] results_rev/R1_field/symmetric/high/cross_phase
python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern cross_phase --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R1_field/symmetric/high/cross_phase
if errorlevel 1 echo FAILED w1 run 7: python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern cross_phase --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R1_field/symmetric/high/cross_phase >> results_rev\failures_w1.txt

echo [w1 8/21] results_rev/R1_field/symmetric/high/phase_symmetric
python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern phase_symmetric --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R1_field/symmetric/high/phase_symmetric
if errorlevel 1 echo FAILED w1 run 8: python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern phase_symmetric --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R1_field/symmetric/high/phase_symmetric >> results_rev\failures_w1.txt

echo [w1 9/21] results_rev/R1_field/symmetric/high/distributed
python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern distributed --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R1_field/symmetric/high/distributed
if errorlevel 1 echo FAILED w1 run 9: python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern distributed --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R1_field/symmetric/high/distributed >> results_rev\failures_w1.txt

echo [w1 10/21] results_rev/R3_maxred60/symmetric/medium/phase_symmetric
python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern phase_symmetric --fault-severity high --controllers std_mp_q std_mp_recall pasa_cg_mp --fault-modes NONE HZ --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R3_maxred60/symmetric/medium/phase_symmetric --min-green 20 --max-red 60
if errorlevel 1 echo FAILED w1 run 10: python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern phase_symmetric --fault-severity high --controllers std_mp_q std_mp_recall pasa_cg_mp --fault-modes NONE HZ --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R3_maxred60/symmetric/medium/phase_symmetric --min-green 20 --max-red 60 >> results_rev\failures_w1.txt

echo [w1 11/21] results_rev/R3_maxred60/symmetric/high/phase_symmetric
python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern phase_symmetric --fault-severity high --controllers std_mp_q std_mp_recall pasa_cg_mp --fault-modes NONE HZ --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R3_maxred60/symmetric/high/phase_symmetric --min-green 20 --max-red 60
if errorlevel 1 echo FAILED w1 run 11: python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern phase_symmetric --fault-severity high --controllers std_mp_q std_mp_recall pasa_cg_mp --fault-modes NONE HZ --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R3_maxred60/symmetric/high/phase_symmetric --min-green 20 --max-red 60 >> results_rev\failures_w1.txt

echo [w1 12/21] results_rev/R3_maxred120/symmetric/medium/phase_symmetric
python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern phase_symmetric --fault-severity high --controllers std_mp_q std_mp_recall pasa_cg_mp --fault-modes NONE HZ --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R3_maxred120/symmetric/medium/phase_symmetric --min-green 20 --max-red 120
if errorlevel 1 echo FAILED w1 run 12: python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern phase_symmetric --fault-severity high --controllers std_mp_q std_mp_recall pasa_cg_mp --fault-modes NONE HZ --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R3_maxred120/symmetric/medium/phase_symmetric --min-green 20 --max-red 120 >> results_rev\failures_w1.txt

echo [w1 13/21] results_rev/R3_maxred120/symmetric/high/phase_symmetric
python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern phase_symmetric --fault-severity high --controllers std_mp_q std_mp_recall pasa_cg_mp --fault-modes NONE HZ --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R3_maxred120/symmetric/high/phase_symmetric --min-green 20 --max-red 120
if errorlevel 1 echo FAILED w1 run 13: python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern phase_symmetric --fault-severity high --controllers std_mp_q std_mp_recall pasa_cg_mp --fault-modes NONE HZ --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R3_maxred120/symmetric/high/phase_symmetric --min-green 20 --max-red 120 >> results_rev\failures_w1.txt

echo [w1 14/21] results_rev/R6_window/symmetric/medium/single_approach
python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers std_mp std_mp_q std_mp_recall std_mp_maxrecall webster_fallback_mp pasa_max_mp pasa_cg_mp --fault-modes HZ --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R6_window/symmetric/medium/single_approach --fault-start 600 --fault-end 2100
if errorlevel 1 echo FAILED w1 run 14: python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers std_mp std_mp_q std_mp_recall std_mp_maxrecall webster_fallback_mp pasa_max_mp pasa_cg_mp --fault-modes HZ --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R6_window/symmetric/medium/single_approach --fault-start 600 --fault-end 2100 >> results_rev\failures_w1.txt

echo [w1 15/21] results_rev/R6_window/symmetric/medium/phase_symmetric
python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern phase_symmetric --fault-severity high --controllers std_mp std_mp_q std_mp_recall std_mp_maxrecall webster_fallback_mp pasa_max_mp pasa_cg_mp --fault-modes HZ --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R6_window/symmetric/medium/phase_symmetric --fault-start 600 --fault-end 2100
if errorlevel 1 echo FAILED w1 run 15: python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern phase_symmetric --fault-severity high --controllers std_mp std_mp_q std_mp_recall std_mp_maxrecall webster_fallback_mp pasa_max_mp pasa_cg_mp --fault-modes HZ --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R6_window/symmetric/medium/phase_symmetric --fault-start 600 --fault-end 2100 >> results_rev\failures_w1.txt

echo [w1 16/21] results_rev/R6_window/symmetric/high/single_approach
python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern single_approach --fault-severity high --controllers std_mp std_mp_q std_mp_recall std_mp_maxrecall webster_fallback_mp pasa_max_mp pasa_cg_mp --fault-modes HZ --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R6_window/symmetric/high/single_approach --fault-start 600 --fault-end 2100
if errorlevel 1 echo FAILED w1 run 16: python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern single_approach --fault-severity high --controllers std_mp std_mp_q std_mp_recall std_mp_maxrecall webster_fallback_mp pasa_max_mp pasa_cg_mp --fault-modes HZ --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R6_window/symmetric/high/single_approach --fault-start 600 --fault-end 2100 >> results_rev\failures_w1.txt

echo [w1 17/21] results_rev/R6_window/symmetric/high/phase_symmetric
python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern phase_symmetric --fault-severity high --controllers std_mp std_mp_q std_mp_recall std_mp_maxrecall webster_fallback_mp pasa_max_mp pasa_cg_mp --fault-modes HZ --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R6_window/symmetric/high/phase_symmetric --fault-start 600 --fault-end 2100
if errorlevel 1 echo FAILED w1 run 17: python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern phase_symmetric --fault-severity high --controllers std_mp std_mp_q std_mp_recall std_mp_maxrecall webster_fallback_mp pasa_max_mp pasa_cg_mp --fault-modes HZ --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R6_window/symmetric/high/phase_symmetric --fault-start 600 --fault-end 2100 >> results_rev\failures_w1.txt

echo [w1 18/21] results_rev/R7_clip/symmetric/high/single_approach
python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern single_approach --fault-severity high --controllers pasa_cg_clip_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R7_clip/symmetric/high/single_approach
if errorlevel 1 echo FAILED w1 run 18: python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern single_approach --fault-severity high --controllers pasa_cg_clip_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R7_clip/symmetric/high/single_approach >> results_rev\failures_w1.txt

echo [w1 19/21] results_rev/R7_clip/symmetric/high/cross_phase
python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern cross_phase --fault-severity high --controllers pasa_cg_clip_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R7_clip/symmetric/high/cross_phase
if errorlevel 1 echo FAILED w1 run 19: python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern cross_phase --fault-severity high --controllers pasa_cg_clip_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R7_clip/symmetric/high/cross_phase >> results_rev\failures_w1.txt

echo [w1 20/21] results_rev/R7_clip/symmetric/high/phase_symmetric
python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern phase_symmetric --fault-severity high --controllers pasa_cg_clip_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R7_clip/symmetric/high/phase_symmetric
if errorlevel 1 echo FAILED w1 run 20: python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern phase_symmetric --fault-severity high --controllers pasa_cg_clip_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R7_clip/symmetric/high/phase_symmetric >> results_rev\failures_w1.txt

echo [w1 21/21] results_rev/R7_clip/symmetric/high/distributed
python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern distributed --fault-severity high --controllers pasa_cg_clip_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R7_clip/symmetric/high/distributed
if errorlevel 1 echo FAILED w1 run 21: python -m pasa_cg.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern distributed --fault-severity high --controllers pasa_cg_clip_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w1 --output-dir results_rev/R7_clip/symmetric/high/distributed >> results_rev\failures_w1.txt

echo Window 1 finished.
