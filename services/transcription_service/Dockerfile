# transcription_service/Dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY --from=assets . ./common
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "transcription_service.py"]
