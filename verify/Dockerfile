FROM python:3.11-slim

WORKDIR /verify
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY verify.py .

CMD ["python", "verify.py"]
