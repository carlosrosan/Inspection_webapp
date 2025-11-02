@echo off
cd C:\Users\Admin\Documents\Inspection_webapp
call conuar_env\Scripts\activate
cd C:\Users\Admin\Documents\Inspection_webapp\Conuar\conuar_webapp
python manage.py runserver
pause

