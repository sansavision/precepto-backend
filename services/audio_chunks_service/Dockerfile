# services/audio_chunks_service/Dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY --from=assets . ./common
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "audio_chunks_service.py"]
