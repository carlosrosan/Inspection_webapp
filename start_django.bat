@echo off
cd C:\Users\USER\Documents\GitHub\Inspection_webapp
call conuar_env\Scripts\activate
cd C:\Users\USER\Documents\GitHub\Inspection_webapp\Conuar\conuar_webapp
python3 manage.py runserver
pause



