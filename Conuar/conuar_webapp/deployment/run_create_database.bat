@echo off
echo Activating virtual environment and running create_database.py...
cd /d "C:\Users\USER\Documents\GitHub\Inspection_webapp\Conuar\conuar_webapp"
call "C:\Users\USER\Documents\GitHub\Inspection_webapp\conuar_env\Scripts\activate.bat"
python create_database.py
pause

