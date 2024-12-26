# Audio Recording, Transcription, and Summarization Service

## Overview

This project provides an audio recording application with transcription and summarization capabilities using microservices architecture. The communication between services is handled by NATS with JetStream for message durability.

## Services

- **Frontend:** A React application allowing users to record audio, pause, resume, and mark recordings as complete.
- **Recording Service:** Receives audio chunks and stores them durably.
- **Transcription Service:** Transcribes completed recordings using Hugging Face Whisper.
- **Summarization Service:** Summarizes transcriptions using Hugging Face Llama 3B and applies user-defined templates.
- **NATS Server:** Message broker and KV store.

## Technologies

- **Frontend:** Vite, React, TypeScript, `nats.ws`
- **Backend:** Python, AsyncIO, NATS Python client, Hugging Face Transformers
- **Messaging:** NATS with JetStream
- **Containerization:** Docker, Docker Compose

## Setup Instructions

### Prerequisites

- Docker and Docker Compose installed on your machine.

### Running the Services

1. **Clone the repository:**

   ```bash
   git clone https://github.com/your-repo/audio-transcription-service.git
   cd audio-transcription-service
