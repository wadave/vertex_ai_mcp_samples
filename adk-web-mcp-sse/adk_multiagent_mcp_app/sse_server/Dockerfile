FROM python:3.11-slim-buster

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY weather_server.py .

EXPOSE 8000

CMD ["python", "weather_server.py"]
