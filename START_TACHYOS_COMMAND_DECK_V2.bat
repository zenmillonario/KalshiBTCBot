@echo off
setlocal
cd /d "%~dp0"
echo ============================================================
echo TACHYOS COMMAND DECK V2 - READ ONLY
echo ============================================================
python -m streamlit run tachyos_command_deck_v2.py
pause
