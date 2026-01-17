@echo off
cd C:\Users\USER\Documents\GitHub\Inspection_webapp
call conuar_env\Scripts\activate
cd C:\Users\USER\Documents\GitHub\Inspection_webapp\Conuar\conuar_webapp\etl
python3 backup_readings_clean_logs.py
pause

