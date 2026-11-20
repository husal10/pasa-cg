@echo off
setlocal

set SEEDS=10
set NET=data/net

for %%D in (low medium high) do (
    for %%P in (single_approach phase_symmetric distributed) do (
        echo.
        echo ===== demand=%%D  pattern=%%P =====
        python -m pasa_cg.main run-sweep ^
            --demand-level %%D ^
            --fault-pattern %%P ^
            --output-dir results/%%D/%%P ^
            --n-seeds %SEEDS% ^
            --net-dir %NET% ^
            --no-skip
        if errorlevel 1 (
            echo ERROR on %%D/%%P - stopping.
            exit /b 1
        )
    )
)

echo.
echo ===== All 9 sweeps complete - generating figures =====
python -m pasa_cg.main plot ^
    --results results/medium/single_approach/all_results.json ^
    --out-dir figures/grid2x2

echo Done.