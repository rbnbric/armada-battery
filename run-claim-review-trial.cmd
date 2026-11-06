@echo off
cd /d "%~dp0"
docker inspect -f "{{.State.Running}}" battery-integrated-battery-interop-1 | findstr /C:"true" >nul
if errorlevel 1 exit /b 1
docker cp interop\Battery\Interop\AgentOperation.cls battery-integrated-battery-interop-1:/home/irisowner/dev/interop/Battery/Interop/AgentOperation.cls
if errorlevel 1 exit /b 1
docker cp interop\Battery\Interop\CaseAPI.cls battery-integrated-battery-interop-1:/home/irisowner/dev/interop/Battery/Interop/CaseAPI.cls
if errorlevel 1 exit /b 1
docker exec -i battery-integrated-battery-interop-1 iris session IRIS < interop\tests\full-review-compile.script > full-review-compile.log 2>&1
findstr /C:"FULL_REVIEW_COMPILE_OK" full-review-compile.log >nul
if errorlevel 1 exit /b 1
docker exec -i battery-integrated-battery-interop-1 iris session IRIS < interop\tests\claim-review-run.script > claim-review-run.log 2>&1
findstr /C:"CLAIM_REVIEW_END" claim-review-run.log >nul
if errorlevel 1 exit /b 1
findstr /C:"<INVALID" /C:"<UNDEFINED" /C:"CLAIM_REVIEW_ERROR=" claim-review-run.log >nul
if not errorlevel 1 exit /b 1
exit /b 0
