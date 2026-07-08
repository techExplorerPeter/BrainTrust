@echo off
setlocal
python "%~dp0capture_kvaser_asc.py" %*
exit /b %ERRORLEVEL%
