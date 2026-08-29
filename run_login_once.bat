@echo off
call "%USERPROFILE%\anaconda3\Scripts\activate.bat" nurture
cd /d "%~dp0"
python src\login_once.py
