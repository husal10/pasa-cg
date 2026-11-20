@echo off
setlocal
rem Additional sweeps (results_rev), window 4: 20 runs.
rem Run from the pasa_itsc_code folder. Finished cells are skipped, so it can be restarted.
if not exist results_rev mkdir results_rev
if not exist data\net_c1_rev_w4 xcopy /I /Y /Q data\net_c1_phase_symmetric data\net_c1_rev_w4 >nul

echo [w4 1/20] results_rev/R5_cg_hlo2/symmetric/medium/phase_symmetric
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern phase_symmetric --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R5_cg_hlo2/symmetric/medium/phase_symmetric --cg-param h_lo=2
if errorlevel 1 echo FAILED w4 run 1: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern phase_symmetric --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R5_cg_hlo2/symmetric/medium/phase_symmetric --cg-param h_lo=2 >> results_rev\failures_w4.txt

echo [w4 2/20] results_rev/R5_cg_hlo2/symmetric/medium/single_approach
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R5_cg_hlo2/symmetric/medium/single_approach --cg-param h_lo=2
if errorlevel 1 echo FAILED w4 run 2: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R5_cg_hlo2/symmetric/medium/single_approach --cg-param h_lo=2 >> results_rev\failures_w4.txt

echo [w4 3/20] results_rev/R5_cg_hlo8/symmetric/medium/phase_symmetric
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern phase_symmetric --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R5_cg_hlo8/symmetric/medium/phase_symmetric --cg-param h_lo=8
if errorlevel 1 echo FAILED w4 run 3: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern phase_symmetric --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R5_cg_hlo8/symmetric/medium/phase_symmetric --cg-param h_lo=8 >> results_rev\failures_w4.txt

echo [w4 4/20] results_rev/R5_cg_hlo8/symmetric/medium/single_approach
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R5_cg_hlo8/symmetric/medium/single_approach --cg-param h_lo=8
if errorlevel 1 echo FAILED w4 run 4: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R5_cg_hlo8/symmetric/medium/single_approach --cg-param h_lo=8 >> results_rev\failures_w4.txt

echo [w4 5/20] results_rev/R5_cg_klo03/symmetric/medium/phase_symmetric
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern phase_symmetric --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R5_cg_klo03/symmetric/medium/phase_symmetric --cg-param k_lo=0.3
if errorlevel 1 echo FAILED w4 run 5: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern phase_symmetric --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R5_cg_klo03/symmetric/medium/phase_symmetric --cg-param k_lo=0.3 >> results_rev\failures_w4.txt

echo [w4 6/20] results_rev/R5_cg_klo03/symmetric/medium/single_approach
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R5_cg_klo03/symmetric/medium/single_approach --cg-param k_lo=0.3
if errorlevel 1 echo FAILED w4 run 6: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R5_cg_klo03/symmetric/medium/single_approach --cg-param k_lo=0.3 >> results_rev\failures_w4.txt

echo [w4 7/20] results_rev/R5_cg_klo07/symmetric/medium/phase_symmetric
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern phase_symmetric --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R5_cg_klo07/symmetric/medium/phase_symmetric --cg-param k_lo=0.7
if errorlevel 1 echo FAILED w4 run 7: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern phase_symmetric --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R5_cg_klo07/symmetric/medium/phase_symmetric --cg-param k_lo=0.7 >> results_rev\failures_w4.txt

echo [w4 8/20] results_rev/R5_cg_klo07/symmetric/medium/single_approach
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R5_cg_klo07/symmetric/medium/single_approach --cg-param k_lo=0.7
if errorlevel 1 echo FAILED w4 run 8: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R5_cg_klo07/symmetric/medium/single_approach --cg-param k_lo=0.7 >> results_rev\failures_w4.txt

echo [w4 9/20] results_rev/R5_cg_hhi2/symmetric/medium/phase_symmetric
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern phase_symmetric --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R5_cg_hhi2/symmetric/medium/phase_symmetric --cg-param h_hi=2
if errorlevel 1 echo FAILED w4 run 9: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern phase_symmetric --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R5_cg_hhi2/symmetric/medium/phase_symmetric --cg-param h_hi=2 >> results_rev\failures_w4.txt

echo [w4 10/20] results_rev/R5_cg_hhi2/symmetric/medium/single_approach
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R5_cg_hhi2/symmetric/medium/single_approach --cg-param h_hi=2
if errorlevel 1 echo FAILED w4 run 10: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R5_cg_hhi2/symmetric/medium/single_approach --cg-param h_hi=2 >> results_rev\failures_w4.txt

echo [w4 11/20] results_rev/R5_cg_hhi5/symmetric/medium/phase_symmetric
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern phase_symmetric --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R5_cg_hhi5/symmetric/medium/phase_symmetric --cg-param h_hi=5
if errorlevel 1 echo FAILED w4 run 11: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern phase_symmetric --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R5_cg_hhi5/symmetric/medium/phase_symmetric --cg-param h_hi=5 >> results_rev\failures_w4.txt

echo [w4 12/20] results_rev/R5_cg_hhi5/symmetric/medium/single_approach
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R5_cg_hhi5/symmetric/medium/single_approach --cg-param h_hi=5
if errorlevel 1 echo FAILED w4 run 12: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R5_cg_hhi5/symmetric/medium/single_approach --cg-param h_hi=5 >> results_rev\failures_w4.txt

echo [w4 13/20] results_rev/R5_cg_khi025/symmetric/medium/phase_symmetric
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern phase_symmetric --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R5_cg_khi025/symmetric/medium/phase_symmetric --cg-param k_hi=0.25
if errorlevel 1 echo FAILED w4 run 13: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern phase_symmetric --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R5_cg_khi025/symmetric/medium/phase_symmetric --cg-param k_hi=0.25 >> results_rev\failures_w4.txt

echo [w4 14/20] results_rev/R5_cg_khi025/symmetric/medium/single_approach
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R5_cg_khi025/symmetric/medium/single_approach --cg-param k_hi=0.25
if errorlevel 1 echo FAILED w4 run 14: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R5_cg_khi025/symmetric/medium/single_approach --cg-param k_hi=0.25 >> results_rev\failures_w4.txt

echo [w4 15/20] results_rev/R5_cg_khi10/symmetric/medium/phase_symmetric
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern phase_symmetric --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R5_cg_khi10/symmetric/medium/phase_symmetric --cg-param k_hi=1.0
if errorlevel 1 echo FAILED w4 run 15: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern phase_symmetric --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R5_cg_khi10/symmetric/medium/phase_symmetric --cg-param k_hi=1.0 >> results_rev\failures_w4.txt

echo [w4 16/20] results_rev/R5_cg_khi10/symmetric/medium/single_approach
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R5_cg_khi10/symmetric/medium/single_approach --cg-param k_hi=1.0
if errorlevel 1 echo FAILED w4 run 16: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers pasa_cg_mp --fault-modes NONE HZ SL GN ID DR --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R5_cg_khi10/symmetric/medium/single_approach --cg-param k_hi=1.0 >> results_rev\failures_w4.txt

echo [w4 17/20] results_rev/R6_newfaults/symmetric/medium/single_approach
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers std_mp std_mp_q std_mp_recall std_mp_maxrecall webster_fallback_mp pasa_max_mp pasa_cg_mp --fault-modes SH ND GA --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R6_newfaults/symmetric/medium/single_approach
if errorlevel 1 echo FAILED w4 run 17: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers std_mp std_mp_q std_mp_recall std_mp_maxrecall webster_fallback_mp pasa_max_mp pasa_cg_mp --fault-modes SH ND GA --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R6_newfaults/symmetric/medium/single_approach >> results_rev\failures_w4.txt

echo [w4 18/20] results_rev/R6_newfaults/symmetric/medium/phase_symmetric
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern phase_symmetric --fault-severity high --controllers std_mp std_mp_q std_mp_recall std_mp_maxrecall webster_fallback_mp pasa_max_mp pasa_cg_mp --fault-modes SH ND GA --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R6_newfaults/symmetric/medium/phase_symmetric
if errorlevel 1 echo FAILED w4 run 18: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern phase_symmetric --fault-severity high --controllers std_mp std_mp_q std_mp_recall std_mp_maxrecall webster_fallback_mp pasa_max_mp pasa_cg_mp --fault-modes SH ND GA --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R6_newfaults/symmetric/medium/phase_symmetric >> results_rev\failures_w4.txt

echo [w4 19/20] results_rev/R6_newfaults/symmetric/high/single_approach
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern single_approach --fault-severity high --controllers std_mp std_mp_q std_mp_recall std_mp_maxrecall webster_fallback_mp pasa_max_mp pasa_cg_mp --fault-modes SH ND GA --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R6_newfaults/symmetric/high/single_approach
if errorlevel 1 echo FAILED w4 run 19: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern single_approach --fault-severity high --controllers std_mp std_mp_q std_mp_recall std_mp_maxrecall webster_fallback_mp pasa_max_mp pasa_cg_mp --fault-modes SH ND GA --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R6_newfaults/symmetric/high/single_approach >> results_rev\failures_w4.txt

echo [w4 20/20] results_rev/R6_newfaults/symmetric/high/phase_symmetric
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern phase_symmetric --fault-severity high --controllers std_mp std_mp_q std_mp_recall std_mp_maxrecall webster_fallback_mp pasa_max_mp pasa_cg_mp --fault-modes SH ND GA --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R6_newfaults/symmetric/high/phase_symmetric
if errorlevel 1 echo FAILED w4 run 20: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern phase_symmetric --fault-severity high --controllers std_mp std_mp_q std_mp_recall std_mp_maxrecall webster_fallback_mp pasa_max_mp pasa_cg_mp --fault-modes SH ND GA --n-seeds 10 --net-dir data/net_rev_w4 --output-dir results_rev/R6_newfaults/symmetric/high/phase_symmetric >> results_rev\failures_w4.txt

echo Window 4 finished.
