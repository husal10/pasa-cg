@echo off
setlocal
rem Additional sweep (results_rev), window 5 (diagnosis delay): 15 runs. Run from pasa_itsc_code; finished cells are skipped.
if not exist results_rev mkdir results_rev

echo [w5 1/15] results_rev/R9_diagdelay300/symmetric/medium/phase_symmetric
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern phase_symmetric --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp --fault-modes HZ SH --n-seeds 10 --net-dir data/net_rev_w5 --output-dir results_rev/R9_diagdelay300/symmetric/medium/phase_symmetric --diag-delay 300
if errorlevel 1 echo FAILED w5 run 1: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern phase_symmetric --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp --fault-modes HZ SH --n-seeds 10 --net-dir data/net_rev_w5 --output-dir results_rev/R9_diagdelay300/symmetric/medium/phase_symmetric --diag-delay 300 >> results_rev\failures_w5.txt

echo [w5 2/15] results_rev/R9_diagdelay300/symmetric/medium/single_approach
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp --fault-modes HZ SH --n-seeds 10 --net-dir data/net_rev_w5 --output-dir results_rev/R9_diagdelay300/symmetric/medium/single_approach --diag-delay 300
if errorlevel 1 echo FAILED w5 run 2: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp --fault-modes HZ SH --n-seeds 10 --net-dir data/net_rev_w5 --output-dir results_rev/R9_diagdelay300/symmetric/medium/single_approach --diag-delay 300 >> results_rev\failures_w5.txt

echo [w5 3/15] results_rev/R9_diagdelay300/symmetric/high/phase_symmetric
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern phase_symmetric --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp --fault-modes HZ SH --n-seeds 10 --net-dir data/net_rev_w5 --output-dir results_rev/R9_diagdelay300/symmetric/high/phase_symmetric --diag-delay 300
if errorlevel 1 echo FAILED w5 run 3: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern phase_symmetric --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp --fault-modes HZ SH --n-seeds 10 --net-dir data/net_rev_w5 --output-dir results_rev/R9_diagdelay300/symmetric/high/phase_symmetric --diag-delay 300 >> results_rev\failures_w5.txt

echo [w5 4/15] results_rev/R9_diagdelay300/symmetric/high/single_approach
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern single_approach --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp --fault-modes HZ SH --n-seeds 10 --net-dir data/net_rev_w5 --output-dir results_rev/R9_diagdelay300/symmetric/high/single_approach --diag-delay 300
if errorlevel 1 echo FAILED w5 run 4: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern single_approach --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp --fault-modes HZ SH --n-seeds 10 --net-dir data/net_rev_w5 --output-dir results_rev/R9_diagdelay300/symmetric/high/single_approach --diag-delay 300 >> results_rev\failures_w5.txt

echo [w5 5/15] results_rev/R9_c1_diagdelay300/phase_symmetric
python -m pasa_itsc.main run-sweep --network cologne1 --demand-profile asymmetric --fault-pattern phase_symmetric --fault-severity high --emissions --controllers std_mp_maxrecall webster_fallback_mp --fault-modes HZ SH --n-seeds 10 --net-dir data/net_c1_rev_w5 --output-dir results_rev/R9_c1_diagdelay300/phase_symmetric --diag-delay 300
if errorlevel 1 echo FAILED w5 run 5: python -m pasa_itsc.main run-sweep --network cologne1 --demand-profile asymmetric --fault-pattern phase_symmetric --fault-severity high --emissions --controllers std_mp_maxrecall webster_fallback_mp --fault-modes HZ SH --n-seeds 10 --net-dir data/net_c1_rev_w5 --output-dir results_rev/R9_c1_diagdelay300/phase_symmetric --diag-delay 300 >> results_rev\failures_w5.txt

echo [w5 6/15] results_rev/R9_diagdelay900/symmetric/medium/phase_symmetric
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern phase_symmetric --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp --fault-modes HZ SH --n-seeds 10 --net-dir data/net_rev_w5 --output-dir results_rev/R9_diagdelay900/symmetric/medium/phase_symmetric --diag-delay 900
if errorlevel 1 echo FAILED w5 run 6: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern phase_symmetric --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp --fault-modes HZ SH --n-seeds 10 --net-dir data/net_rev_w5 --output-dir results_rev/R9_diagdelay900/symmetric/medium/phase_symmetric --diag-delay 900 >> results_rev\failures_w5.txt

echo [w5 7/15] results_rev/R9_diagdelay900/symmetric/medium/single_approach
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp --fault-modes HZ SH --n-seeds 10 --net-dir data/net_rev_w5 --output-dir results_rev/R9_diagdelay900/symmetric/medium/single_approach --diag-delay 900
if errorlevel 1 echo FAILED w5 run 7: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp --fault-modes HZ SH --n-seeds 10 --net-dir data/net_rev_w5 --output-dir results_rev/R9_diagdelay900/symmetric/medium/single_approach --diag-delay 900 >> results_rev\failures_w5.txt

echo [w5 8/15] results_rev/R9_diagdelay900/symmetric/high/phase_symmetric
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern phase_symmetric --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp --fault-modes HZ SH --n-seeds 10 --net-dir data/net_rev_w5 --output-dir results_rev/R9_diagdelay900/symmetric/high/phase_symmetric --diag-delay 900
if errorlevel 1 echo FAILED w5 run 8: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern phase_symmetric --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp --fault-modes HZ SH --n-seeds 10 --net-dir data/net_rev_w5 --output-dir results_rev/R9_diagdelay900/symmetric/high/phase_symmetric --diag-delay 900 >> results_rev\failures_w5.txt

echo [w5 9/15] results_rev/R9_diagdelay900/symmetric/high/single_approach
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern single_approach --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp --fault-modes HZ SH --n-seeds 10 --net-dir data/net_rev_w5 --output-dir results_rev/R9_diagdelay900/symmetric/high/single_approach --diag-delay 900
if errorlevel 1 echo FAILED w5 run 9: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern single_approach --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp --fault-modes HZ SH --n-seeds 10 --net-dir data/net_rev_w5 --output-dir results_rev/R9_diagdelay900/symmetric/high/single_approach --diag-delay 900 >> results_rev\failures_w5.txt

echo [w5 10/15] results_rev/R9_c1_diagdelay900/phase_symmetric
python -m pasa_itsc.main run-sweep --network cologne1 --demand-profile asymmetric --fault-pattern phase_symmetric --fault-severity high --emissions --controllers std_mp_maxrecall webster_fallback_mp --fault-modes HZ SH --n-seeds 10 --net-dir data/net_c1_rev_w5 --output-dir results_rev/R9_c1_diagdelay900/phase_symmetric --diag-delay 900
if errorlevel 1 echo FAILED w5 run 10: python -m pasa_itsc.main run-sweep --network cologne1 --demand-profile asymmetric --fault-pattern phase_symmetric --fault-severity high --emissions --controllers std_mp_maxrecall webster_fallback_mp --fault-modes HZ SH --n-seeds 10 --net-dir data/net_c1_rev_w5 --output-dir results_rev/R9_c1_diagdelay900/phase_symmetric --diag-delay 900 >> results_rev\failures_w5.txt

echo [w5 11/15] results_rev/R9_diagdelay1800/symmetric/medium/phase_symmetric
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern phase_symmetric --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp --fault-modes HZ SH --n-seeds 10 --net-dir data/net_rev_w5 --output-dir results_rev/R9_diagdelay1800/symmetric/medium/phase_symmetric --diag-delay 1800
if errorlevel 1 echo FAILED w5 run 11: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern phase_symmetric --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp --fault-modes HZ SH --n-seeds 10 --net-dir data/net_rev_w5 --output-dir results_rev/R9_diagdelay1800/symmetric/medium/phase_symmetric --diag-delay 1800 >> results_rev\failures_w5.txt

echo [w5 12/15] results_rev/R9_diagdelay1800/symmetric/medium/single_approach
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp --fault-modes HZ SH --n-seeds 10 --net-dir data/net_rev_w5 --output-dir results_rev/R9_diagdelay1800/symmetric/medium/single_approach --diag-delay 1800
if errorlevel 1 echo FAILED w5 run 12: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level medium --fault-pattern single_approach --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp --fault-modes HZ SH --n-seeds 10 --net-dir data/net_rev_w5 --output-dir results_rev/R9_diagdelay1800/symmetric/medium/single_approach --diag-delay 1800 >> results_rev\failures_w5.txt

echo [w5 13/15] results_rev/R9_diagdelay1800/symmetric/high/phase_symmetric
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern phase_symmetric --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp --fault-modes HZ SH --n-seeds 10 --net-dir data/net_rev_w5 --output-dir results_rev/R9_diagdelay1800/symmetric/high/phase_symmetric --diag-delay 1800
if errorlevel 1 echo FAILED w5 run 13: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern phase_symmetric --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp --fault-modes HZ SH --n-seeds 10 --net-dir data/net_rev_w5 --output-dir results_rev/R9_diagdelay1800/symmetric/high/phase_symmetric --diag-delay 1800 >> results_rev\failures_w5.txt

echo [w5 14/15] results_rev/R9_diagdelay1800/symmetric/high/single_approach
python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern single_approach --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp --fault-modes HZ SH --n-seeds 10 --net-dir data/net_rev_w5 --output-dir results_rev/R9_diagdelay1800/symmetric/high/single_approach --diag-delay 1800
if errorlevel 1 echo FAILED w5 run 14: python -m pasa_itsc.main run-sweep --network grid2x2 --demand-profile symmetric --demand-level high --fault-pattern single_approach --fault-severity high --controllers std_mp_maxrecall webster_fallback_mp --fault-modes HZ SH --n-seeds 10 --net-dir data/net_rev_w5 --output-dir results_rev/R9_diagdelay1800/symmetric/high/single_approach --diag-delay 1800 >> results_rev\failures_w5.txt

echo [w5 15/15] results_rev/R9_c1_diagdelay1800/phase_symmetric
python -m pasa_itsc.main run-sweep --network cologne1 --demand-profile asymmetric --fault-pattern phase_symmetric --fault-severity high --emissions --controllers std_mp_maxrecall webster_fallback_mp --fault-modes HZ SH --n-seeds 10 --net-dir data/net_c1_rev_w5 --output-dir results_rev/R9_c1_diagdelay1800/phase_symmetric --diag-delay 1800
if errorlevel 1 echo FAILED w5 run 15: python -m pasa_itsc.main run-sweep --network cologne1 --demand-profile asymmetric --fault-pattern phase_symmetric --fault-severity high --emissions --controllers std_mp_maxrecall webster_fallback_mp --fault-modes HZ SH --n-seeds 10 --net-dir data/net_c1_rev_w5 --output-dir results_rev/R9_c1_diagdelay1800/phase_symmetric --diag-delay 1800 >> results_rev\failures_w5.txt

echo Window 5 finished.
