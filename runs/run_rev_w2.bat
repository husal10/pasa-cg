@echo off
setlocal
rem Additional sweeps (results_rev), window 2: 27 runs.
rem Run from the pasa_itsc_code folder. Finished cells are skipped, so it can be restarted.
if not exist results_rev mkdir results_rev
if not exist data\net_c1_rev_w2 xcopy /I /Y /Q data\net_c1_phase_symmetric data\net_c1_rev_w2 >nul

echo [w2 1/27] results_rev/R1_field/asymmetric/low/phase_symmetric
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile asymmetric --demand-level low --fault-pattern phase_symmetric --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R1_field/asymmetric/low/phase_symmetric
if errorlevel 1 echo FAILED w2 run 1: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile asymmetric --demand-level low --fault-pattern phase_symmetric --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R1_field/asymmetric/low/phase_symmetric >> results_rev\failures_w2.txt

echo [w2 2/27] results_rev/R1_field/asymmetric/medium/single_approach
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile asymmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R1_field/asymmetric/medium/single_approach
if errorlevel 1 echo FAILED w2 run 2: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile asymmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R1_field/asymmetric/medium/single_approach >> results_rev\failures_w2.txt

echo [w2 3/27] results_rev/R1_field/asymmetric/medium/cross_phase
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile asymmetric --demand-level medium --fault-pattern cross_phase --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R1_field/asymmetric/medium/cross_phase
if errorlevel 1 echo FAILED w2 run 3: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile asymmetric --demand-level medium --fault-pattern cross_phase --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R1_field/asymmetric/medium/cross_phase >> results_rev\failures_w2.txt

echo [w2 4/27] results_rev/R1_field/asymmetric/medium/phase_symmetric
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile asymmetric --demand-level medium --fault-pattern phase_symmetric --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R1_field/asymmetric/medium/phase_symmetric
if errorlevel 1 echo FAILED w2 run 4: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile asymmetric --demand-level medium --fault-pattern phase_symmetric --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R1_field/asymmetric/medium/phase_symmetric >> results_rev\failures_w2.txt

echo [w2 5/27] results_rev/R1_field/asymmetric/medium/distributed
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile asymmetric --demand-level medium --fault-pattern distributed --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R1_field/asymmetric/medium/distributed
if errorlevel 1 echo FAILED w2 run 5: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile asymmetric --demand-level medium --fault-pattern distributed --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R1_field/asymmetric/medium/distributed >> results_rev\failures_w2.txt

echo [w2 6/27] results_rev/R1_field/asymmetric/high/single_approach
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile asymmetric --demand-level high --fault-pattern single_approach --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R1_field/asymmetric/high/single_approach
if errorlevel 1 echo FAILED w2 run 6: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile asymmetric --demand-level high --fault-pattern single_approach --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R1_field/asymmetric/high/single_approach >> results_rev\failures_w2.txt

echo [w2 7/27] results_rev/R1_field/asymmetric/high/cross_phase
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile asymmetric --demand-level high --fault-pattern cross_phase --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R1_field/asymmetric/high/cross_phase
if errorlevel 1 echo FAILED w2 run 7: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile asymmetric --demand-level high --fault-pattern cross_phase --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R1_field/asymmetric/high/cross_phase >> results_rev\failures_w2.txt

echo [w2 8/27] results_rev/R1_field/asymmetric/high/phase_symmetric
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile asymmetric --demand-level high --fault-pattern phase_symmetric --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R1_field/asymmetric/high/phase_symmetric
if errorlevel 1 echo FAILED w2 run 8: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile asymmetric --demand-level high --fault-pattern phase_symmetric --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R1_field/asymmetric/high/phase_symmetric >> results_rev\failures_w2.txt

echo [w2 9/27] results_rev/R1_field/asymmetric/high/distributed
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile asymmetric --demand-level high --fault-pattern distributed --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R1_field/asymmetric/high/distributed
if errorlevel 1 echo FAILED w2 run 9: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile asymmetric --demand-level high --fault-pattern distributed --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R1_field/asymmetric/high/distributed >> results_rev\failures_w2.txt

echo [w2 10/27] results_rev/R4_plan_scale050/symmetric/medium/single_approach
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R4_plan_scale050/symmetric/medium/single_approach --plan-scale 0.5
if errorlevel 1 echo FAILED w2 run 10: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R4_plan_scale050/symmetric/medium/single_approach --plan-scale 0.5 >> results_rev\failures_w2.txt

echo [w2 11/27] results_rev/R4_plan_scale050/symmetric/high/single_approach
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern single_approach --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R4_plan_scale050/symmetric/high/single_approach --plan-scale 0.5
if errorlevel 1 echo FAILED w2 run 11: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern single_approach --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R4_plan_scale050/symmetric/high/single_approach --plan-scale 0.5 >> results_rev\failures_w2.txt

echo [w2 12/27] results_rev/R4_plan_scale080/symmetric/medium/single_approach
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R4_plan_scale080/symmetric/medium/single_approach --plan-scale 0.8
if errorlevel 1 echo FAILED w2 run 12: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R4_plan_scale080/symmetric/medium/single_approach --plan-scale 0.8 >> results_rev\failures_w2.txt

echo [w2 13/27] results_rev/R4_plan_scale080/symmetric/high/single_approach
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern single_approach --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R4_plan_scale080/symmetric/high/single_approach --plan-scale 0.8
if errorlevel 1 echo FAILED w2 run 13: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern single_approach --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R4_plan_scale080/symmetric/high/single_approach --plan-scale 0.8 >> results_rev\failures_w2.txt

echo [w2 14/27] results_rev/R4_plan_scale125/symmetric/medium/single_approach
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R4_plan_scale125/symmetric/medium/single_approach --plan-scale 1.25
if errorlevel 1 echo FAILED w2 run 14: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R4_plan_scale125/symmetric/medium/single_approach --plan-scale 1.25 >> results_rev\failures_w2.txt

echo [w2 15/27] results_rev/R4_plan_scale125/symmetric/high/single_approach
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern single_approach --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R4_plan_scale125/symmetric/high/single_approach --plan-scale 1.25
if errorlevel 1 echo FAILED w2 run 15: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern single_approach --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R4_plan_scale125/symmetric/high/single_approach --plan-scale 1.25 >> results_rev\failures_w2.txt

echo [w2 16/27] results_rev/R4_plan_scale200/symmetric/medium/single_approach
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R4_plan_scale200/symmetric/medium/single_approach --plan-scale 2.0
if errorlevel 1 echo FAILED w2 run 16: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R4_plan_scale200/symmetric/medium/single_approach --plan-scale 2.0 >> results_rev\failures_w2.txt

echo [w2 17/27] results_rev/R4_plan_scale200/symmetric/high/single_approach
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern single_approach --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R4_plan_scale200/symmetric/high/single_approach --plan-scale 2.0
if errorlevel 1 echo FAILED w2 run 17: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern single_approach --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R4_plan_scale200/symmetric/high/single_approach --plan-scale 2.0 >> results_rev\failures_w2.txt

echo [w2 18/27] results_rev/R4_plan_armnoise030/symmetric/medium/single_approach
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R4_plan_armnoise030/symmetric/medium/single_approach --plan-noise 0.3
if errorlevel 1 echo FAILED w2 run 18: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R4_plan_armnoise030/symmetric/medium/single_approach --plan-noise 0.3 >> results_rev\failures_w2.txt

echo [w2 19/27] results_rev/R4_plan_armnoise030/symmetric/high/single_approach
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern single_approach --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R4_plan_armnoise030/symmetric/high/single_approach --plan-noise 0.3
if errorlevel 1 echo FAILED w2 run 19: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern single_approach --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R4_plan_armnoise030/symmetric/high/single_approach --plan-noise 0.3 >> results_rev\failures_w2.txt

echo [w2 20/27] results_rev/R7_clip/asymmetric/high/single_approach
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile asymmetric --demand-level high --fault-pattern single_approach --fault-severity high --controllers pasa_cg_clip_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R7_clip/asymmetric/high/single_approach
if errorlevel 1 echo FAILED w2 run 20: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile asymmetric --demand-level high --fault-pattern single_approach --fault-severity high --controllers pasa_cg_clip_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R7_clip/asymmetric/high/single_approach >> results_rev\failures_w2.txt

echo [w2 21/27] results_rev/R7_clip/asymmetric/high/cross_phase
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile asymmetric --demand-level high --fault-pattern cross_phase --fault-severity high --controllers pasa_cg_clip_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R7_clip/asymmetric/high/cross_phase
if errorlevel 1 echo FAILED w2 run 21: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile asymmetric --demand-level high --fault-pattern cross_phase --fault-severity high --controllers pasa_cg_clip_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R7_clip/asymmetric/high/cross_phase >> results_rev\failures_w2.txt

echo [w2 22/27] results_rev/R7_clip/asymmetric/high/phase_symmetric
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile asymmetric --demand-level high --fault-pattern phase_symmetric --fault-severity high --controllers pasa_cg_clip_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R7_clip/asymmetric/high/phase_symmetric
if errorlevel 1 echo FAILED w2 run 22: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile asymmetric --demand-level high --fault-pattern phase_symmetric --fault-severity high --controllers pasa_cg_clip_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R7_clip/asymmetric/high/phase_symmetric >> results_rev\failures_w2.txt

echo [w2 23/27] results_rev/R7_clip/asymmetric/high/distributed
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile asymmetric --demand-level high --fault-pattern distributed --fault-severity high --controllers pasa_cg_clip_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R7_clip/asymmetric/high/distributed
if errorlevel 1 echo FAILED w2 run 23: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile asymmetric --demand-level high --fault-pattern distributed --fault-severity high --controllers pasa_cg_clip_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w2 --output-dir results_rev/R7_clip/asymmetric/high/distributed >> results_rev\failures_w2.txt

echo [w2 24/27] results_rev/R8_c1_field/single_approach
python -m pasa_itsc.main run-sweep --network cologne1 --demand-profile asymmetric --fault-pattern single_approach --fault-severity high --emissions --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_c1_rev_w2 --output-dir results_rev/R8_c1_field/single_approach
if errorlevel 1 echo FAILED w2 run 24: python -m pasa_itsc.main run-sweep --network cologne1 --demand-profile asymmetric --fault-pattern single_approach --fault-severity high --emissions --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_c1_rev_w2 --output-dir results_rev/R8_c1_field/single_approach >> results_rev\failures_w2.txt

echo [w2 25/27] results_rev/R8_c1_field/cross_phase
python -m pasa_itsc.main run-sweep --network cologne1 --demand-profile asymmetric --fault-pattern cross_phase --fault-severity high --emissions --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_c1_rev_w2 --output-dir results_rev/R8_c1_field/cross_phase
if errorlevel 1 echo FAILED w2 run 25: python -m pasa_itsc.main run-sweep --network cologne1 --demand-profile asymmetric --fault-pattern cross_phase --fault-severity high --emissions --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_c1_rev_w2 --output-dir results_rev/R8_c1_field/cross_phase >> results_rev\failures_w2.txt

echo [w2 26/27] results_rev/R8_c1_field/phase_symmetric
python -m pasa_itsc.main run-sweep --network cologne1 --demand-profile asymmetric --fault-pattern phase_symmetric --fault-severity high --emissions --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_c1_rev_w2 --output-dir results_rev/R8_c1_field/phase_symmetric
if errorlevel 1 echo FAILED w2 run 26: python -m pasa_itsc.main run-sweep --network cologne1 --demand-profile asymmetric --fault-pattern phase_symmetric --fault-severity high --emissions --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_c1_rev_w2 --output-dir results_rev/R8_c1_field/phase_symmetric >> results_rev\failures_w2.txt

echo [w2 27/27] results_rev/R8_c1_field/distributed
python -m pasa_itsc.main run-sweep --network cologne1 --demand-profile asymmetric --fault-pattern distributed --fault-severity high --emissions --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_c1_rev_w2 --output-dir results_rev/R8_c1_field/distributed
if errorlevel 1 echo FAILED w2 run 27: python -m pasa_itsc.main run-sweep --network cologne1 --demand-profile asymmetric --fault-pattern distributed --fault-severity high --emissions --controllers std_mp_maxrecall webster_fallback_mp oracle_cg_mp --fault-modes HZ SL GN ID DR --n-seeds 10 --net-dir data/net_c1_rev_w2 --output-dir results_rev/R8_c1_field/distributed >> results_rev\failures_w2.txt

echo Window 2 finished.
