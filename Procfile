web: python manage.py migrate && python manage.py seed_demo --if-empty && gunicorn breathe_esg.wsgi:application --bind 0.0.0.0:$PORT
