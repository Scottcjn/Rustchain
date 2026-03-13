@echo off
REM Evidence Collection Script for Issue #473: State Hash Validator
REM This script collects evidence of the validator working correctly

set PYTHON=C:\Python314\python.exe

echo ==============================================
echo State Hash Validator - Evidence Collection
echo ==============================================
echo.

REM Create evidence directory
if not exist evidence mkdir evidence

REM Test 1: Run unit tests
echo 1. Running unit tests...
%PYTHON% tests\test_state_hash_validator.py > evidence\test_results.txt 2>&1
echo    Unit tests completed

REM Test 2: Validate live RustChain node
echo 2. Validating live RustChain node...
%PYTHON% src\state_hash_validator.py --node https://rustchain.org --validate --output evidence\validation_result.json --format json 2>nul
echo    Live node validation completed

REM Test 3: Generate markdown report
echo 3. Generating markdown report...
%PYTHON% src\state_hash_validator.py --node https://rustchain.org --validate --output evidence\validation_report.md --format markdown 2>nul
echo    Markdown report generated

REM Test 4: Show validation summary
echo 4. Validation summary:
echo.
%PYTHON% src\state_hash_validator.py --node https://rustchain.org --validate 2>nul
echo.

REM Test 5: Collect version info
echo 5. Collecting version info...
%PYTHON% src\state_hash_validator.py --version > evidence\version.txt
echo    Version info collected

echo.
echo ==============================================
echo Evidence collection complete!
echo ==============================================
echo.
echo Evidence files:
echo   - evidence\test_results.txt       (unit test results)
echo   - evidence\validation_result.json (JSON validation result)
echo   - evidence\validation_report.md   (markdown report)
echo   - evidence\version.txt            (version info)
echo.
