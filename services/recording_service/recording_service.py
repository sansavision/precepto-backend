# services/recording_service/recording_service.py

import asyncio
import json
import os
import sys
import time
import logging

# Adjust the path to include the parent directory for imports
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from common.nats_client import NATSClient
# from common.models import TranscriptionMeta
from common.queries.transcriptions.transcript_read_async_edgeql import transcript_read, TranscriptReadResult as TranscriptionMeta
from common.queries.transcriptions.transcript_update_async_edgeql import transcript_update
from common.queries.transcriptions.transcript_delete_async_edgeql import transcript_delete
from common.edgedb_client import EdgedbClient, DataclassEncoder

logging.basicConfig(level=logging.INFO)

class RecordingService:
    CHUNK_STORAGE_PATH = 'audio_chunks'
    SUBJECT_AUDIO_CHUNKS = 'audio.chunks'
    STREAM_NAME = 'AUDIO_CHUNKS_STREAM'
    STREAM_LISTEN_SUBJECT = ["audio.chunks"]

    def __init__(self):
        # Setup logging
        self.logger = logging.getLogger(self.__class__.__name__)
        self.db = EdgedbClient()
        self.client = self.db.client

        # Ensure chunk storage path exists
        if not os.path.exists(self.CHUNK_STORAGE_PATH):
            os.makedirs(self.CHUNK_STORAGE_PATH)
            self.logger.info(f"Created directory for audio chunks at '{self.CHUNK_STORAGE_PATH}'")

        # Initialize NATS client
        self.nats_client = NATSClient()

    async def connect(self):
        try:
            await self.nats_client.connect()
            await self.nats_client.create_stream(self.STREAM_NAME, self.STREAM_LISTEN_SUBJECT)
            self.logger.info(f"Connected to stream '{self.STREAM_NAME}' with subjects {self.STREAM_LISTEN_SUBJECT}")

        except Exception as e:
            self.logger.error(f"Failed to connect and set up NATSClient: {e}")
            sys.exit(1)  # Exit if connection fails

    async def handle_audio_chunk(self, msg):
        recording_id = msg.headers.get('Recording-ID')
        if not recording_id:
            self.logger.error("Recording ID missing in headers")
            return

        chunk_filename = f"{recording_id}_{int(time.time() * 1000)}.webm"
        chunk_path = os.path.join(self.CHUNK_STORAGE_PATH, chunk_filename)
        try:
            with open(chunk_path, 'wb') as f:
                f.write(msg.data)
            self.logger.info(f"Saved audio chunk: {chunk_filename}")
        except Exception as e:
            self.logger.error(f"Failed to save audio chunk '{chunk_filename}': {e}")

    # async def handle_kv_transcription_put(self, msg):
    #     kv_key = msg.headers.get('KV-Key')
    #     if kv_key:
    #         try:
    #             value = msg.data.decode('utf-8')
    #             await self.nats_client.kv_put(self.nats_client.kv_transcriptions, kv_key, value)
    #             self.logger.info(f"Updated KV store with key: {kv_key}")
    #         except Exception as e:
    #             self.logger.error(f"Failed to put KV entry for key '{kv_key}': {e}")
    #     else:
    #         self.logger.warning("KV-Key header missing in message")

    async def handle_recording_completed(self, msg):
        data = json.loads(msg.data.decode('utf-8'))
        access_token = data.get('access_token')

        # Validate token and extract user information
        payload = await self.token_validator.validate_access_token(access_token)
        user_id = payload['user']['id']
        transcript_id = data['transcription_id']
        try:
            # transcription_meta = TranscriptionMeta.from_json(msg.data.decode())
            await transcript_read(self.client, transcript_id)
            recording_id = transcript_id
            self.logger.info(f"Combining audio chunks for recording ID: {recording_id}")

            # Locate and combine audio chunks
            chunk_files = [f for f in os.listdir(self.CHUNK_STORAGE_PATH) if f.startswith(recording_id)]
            chunk_files.sort()  # Ensure correct order

            if not chunk_files:
                self.logger.error(f"No audio chunks found for recording ID: {recording_id}")
                return

            combined_audio_path = os.path.join(self.CHUNK_STORAGE_PATH, f"{recording_id}_combined.webm")
            with open(combined_audio_path, 'wb') as outfile:
                for fname in chunk_files:
                    with open(os.path.join(self.CHUNK_STORAGE_PATH, fname), 'rb') as infile:
                        outfile.write(infile.read())

            self.logger.info(f"Combined audio saved at: {combined_audio_path}")

            # Optionally, delete individual chunks
            for fname in chunk_files:
                os.remove(os.path.join(self.CHUNK_STORAGE_PATH, fname))

            # Update transcription meta status
            # transcription_meta.status = 'processing'
            # transcription_meta.backend_status = 'transcription_service'
            # await self.nats_client.kv_put(self.nats_client.kv_transcriptions, recording_id, transcription_meta.to_json())
            await transcript_update(self.client, transcript_id, status='processing ', backend_status='transcription_service')

            # Notify the transcription service
            await self.nats_client.publish('recording.combined',  json.dump({'transcription_id': transcript_id}))

        except Exception as e:
            self.logger.error(f"Error combining audio chunks for recording ID {recording_id}: {e}")

    # **New Functionality: Handle Transcription Deletion**
    async def handle_transcription_delete(self, msg):
        # kv_key = msg.headers.get('KV-Key')
        # if not kv_key:
        #     self.logger.error("KV-Key header missing in transcription.delete message")
        #     return
        data = json.loads(msg.data.decode('utf-8'))
        access_token = data.get('access_token')

        # Validate token and extract user information
        payload = await self.token_validator.validate_access_token(access_token)
        user_id = payload['user']['id']
        transcript_id = data['transcription_id']
        try:
            # Delete transcription metadata from KV store
            # await self.nats_client.kv_delete(self.nats_client.kv_transcriptions, kv_key)
            await transcript_delete(self.client, data['transcription_id'])
            self.logger.info(f"Deleted transcription metadata with key: {transcript_id}")

            # Delete associated audio chunks and combined audio files
            # Delete individual audio chunks
            chunk_files = [f for f in os.listdir(self.CHUNK_STORAGE_PATH) if f.startswith(transcript_id)]
            for fname in chunk_files:
                os.remove(os.path.join(self.CHUNK_STORAGE_PATH, fname))
            self.logger.info(f"Deleted audio chunks for transcription ID: {transcript_id}")

            # Delete combined audio file if exists
            combined_audio_path = os.path.join(self.CHUNK_STORAGE_PATH, f"{transcript_id}_combined.webm")
            if os.path.exists(combined_audio_path):
                os.remove(combined_audio_path)
                self.logger.info(f"Deleted combined audio file for transcription ID: {transcript_id}")


        except Exception as e:
            self.logger.error(f"Error deleting transcription {transcript_id}: {e}")

    async def subscribe(self):
        await self.nats_client.subscribe(self.SUBJECT_AUDIO_CHUNKS, self.handle_audio_chunk)
        # await self.nats_client.subscribe(self.SUBJECT_KV_TRANSCRIPTIONS_PUT, self.handle_kv_transcription_put)
        await self.nats_client.subscribe('recording.completed', self.handle_recording_completed)
        # Subscribe to 'transcription.delete' subject
        await self.nats_client.subscribe('transcription.delete', self.handle_transcription_delete)
        self.logger.info(f"Subscribed to subjects '{self.SUBJECT_AUDIO_CHUNKS}', 'recording.completed', and 'transcription.delete'")

    async def run(self):
        await self.connect()
        await self.subscribe()

        # Keep the service running
        try:
            self.logger.info("RecordingService is running. Press Ctrl+C to exit.")
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Shutting down RecordingService...")
            await self.close()

    async def close(self):
        try:
            await self.nats_client.close()
            self.logger.info("RecordingService has been shut down.")
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")

if __name__ == '__main__':
    service = RecordingService()
    asyncio.run(service.run())


'''
 
python backend/recording_service/recording_service.py
'''