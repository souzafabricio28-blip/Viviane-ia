@echo off
cd /d %~dp0
start Viviane pythonw.exe interface_viviane.py
if errorlevel 1 start Viviane python interface_viviane.py
