@echo off
setlocal
python "%~dp0stop_kvaser_capture.py" %*
exit /b %ERRORLEVEL%
