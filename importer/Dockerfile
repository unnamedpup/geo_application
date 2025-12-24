FROM python:3.12-slim

WORKDIR /work

RUN pip install --no-cache-dir requests psycopg[binary]==3.2.9

COPY import_overpass.py /work/import_overpass.py

CMD ["python", "/work/import_overpass.py"]