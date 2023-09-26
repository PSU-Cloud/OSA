FROM python:3.9

WORKDIR /locust

COPY requirements.txt .
COPY annealing_service_account.json .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .
ENTRYPOINT ["python3","main.py"]
