# services/transcription_service/transcription_service.py

import asyncio
import datetime
from datetime import timezone
import json
import logging
import os
import sys
import subprocess
from faster_whisper import BatchedInferencePipeline, WhisperModel
# Adjust the path to include the parent directory for imports
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from common.nats_client import NATSClient
from common.edgedb_client import EdgedbClient, DataclassEncoder
from common.queries.transcriptions.transcript_read_async_edgeql import transcript_read, TranscriptReadResult as TranscriptionMeta
from common.queries.transcriptions.transcript_update_async_edgeql import  transcript_update
# from common.models import TranscriptionMeta


from transformers import pipeline

logging.basicConfig(level=logging.INFO)

logging.getLogger("faster_whisper").setLevel(logging.DEBUG)

class TranscriptionService:
    TRANSCRIPTIONS_PATH = 'transcriptions'
    AUDIO_CHUNKS_PATH = 'audio_chunks'

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.nats_client = NATSClient()
        self.db = EdgedbClient()
        self.client = self.db.client
        # self.transcriber = pipeline('automatic-speech-recognition', model='openai/whisper-base')
        # WhisperModel("deepdml/faster-whisper-large-v3-turbo-ct2", device="cuda", compute_type="float16")
        # model_path = os.path.join('models', 'whisper', 'models', 'whisper-large-v3-ct2', 'model.bin')
        # self.model = WhisperModel(model_path, device="cuda", compute_type="int8")
        # self.model =  WhisperModel("deepdml/faster-whisper-large-v3-turbo-ct2", device="cuda", compute_type="float16")
        # self.model =  WhisperModel("ctranslate2-4you/distil-whisper-large-v3-ct2-float16", device="cuda", compute_type="float16")
        # self.model =  WhisperModel("NbAiLab/nb-whisper-large-distil-turbo-beta", device="cuda", compute_type="float16")
        # self.transcriber = BatchedInferencePipeline(model=self.model)
        # self.transcriber = pipeline("automatic-speech-recognition", "NbAiLabBeta/nb-whisper-medium", device="cuda")
        self.transcriber = pipeline("automatic-speech-recognition", model="NbAiLab/nb-whisper-large-distil-turbo-beta")
        self.object_store = None

        if not os.path.exists(self.TRANSCRIPTIONS_PATH):
            os.makedirs(self.TRANSCRIPTIONS_PATH)
        if not os.path.exists(self.AUDIO_CHUNKS_PATH):
            os.makedirs(self.AUDIO_CHUNKS_PATH)

    async def connect(self):
        try:
            await self.nats_client.connect()
            # Initialize object store
            js = self.nats_client.nc.jetstream()
            try:
                self.object_store = await js.object_store('audio-recordings')
            except:
                self.object_store = await js.create_object_store('audio-recordings')
            self.logger.info("Connected to NATS 'transcriptions'")
        except Exception as e:
            self.logger.error(f"Failed to connect to NATS: {e}")
            raise

    def convert_to_wav(self, input_path, output_path):
        command = ['ffmpeg', '-y', '-i', input_path, '-ar', '16000', '-ac', '1', output_path]
        try:
            subprocess.run(command, check=True)
            self.logger.info(f"Converted {input_path} to {output_path}")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to convert audio file: {e}")
            raise

    def convert_to_mp3(self, input_path, output_path):
        command = ['ffmpeg', '-y', '-i', input_path, '-codec:a', 'libmp3lame', '-qscale:a', '2', output_path]
        try:
            subprocess.run(command, check=True)
            self.logger.info(f"Converted {input_path} to {output_path}")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to convert audio file to MP3: {e}")
            raise

    async def handle_completed_recording(self, msg):
        try:
            data = json.loads(msg.data.decode())
            transcription_id = data.get('transcription_id')
            transcription = await transcript_read(self.client, id=transcription_id)
            recording_id = transcription_id
            self.logger.info(f"Processing transcription for recording ID: {recording_id}")

            # Get audio from object store
            try:
                obj = await self.object_store.get(f"{recording_id}/combined.mp3")
                if not obj:
                    self.logger.error(f"Audio file not found in object store for recording {recording_id}")
                    return
                
                # Save temporarily
                temp_mp3_path = os.path.join(self.AUDIO_CHUNKS_PATH, f"{recording_id}_combined.mp3")
                with open(temp_mp3_path, 'wb') as f:
                    f.write(obj.data)

                # Transcribe audio
                result_mp3 = self.transcriber(temp_mp3_path, chunk_length_s=28, return_timestamps=True, 
                                          generate_kwargs={'num_beams': 5, 'task': 'transcribe', 'language': 'no'})
                transcription_text = result_mp3['text']
                self.save_transcription_mp3(recording_id, result_mp3)
                # Clean up temporary file
                # os.remove(temp_mp3_path)

                # Update transcription in database
                await transcript_update(self.client, 
                                     id=transcription_id, 
                                     name=transcription.name,
                                     transcript=transcription_text, 
                                     status='not_signed',  
                                     backend_status='transcription_service', 
                                     next_backend_step='summarization_service',
                                     template_id=transcription.template.id,
                                     backend_updated_at=datetime.datetime.now(timezone.utc))

                # Notify summarization service
                await self.nats_client.publish('transcription.completed', 
                                            json.dumps({"transcription_id":transcription_id}))
                # await self.nats_client.publish('transcription.completed', 
                #                             json.dumps({"transcription_id":transcription_id}).encode())
                self.logger.info(f"Transcription completed for recording ID: {recording_id}")

            except Exception as e:
                self.logger.error(f"Error accessing object store: {e}")
                raise

        except Exception as e:
            self.logger.error(f"Error processing recording {recording_id}: {e}")
            raise

    async def handle_transcribe(self, msg):
        try:
            data = json.loads(msg.data.decode())
            payload = await self.token_validator.validate_access_token(data.get('access_token'))
            user_id = payload['user']['id']
            audio_data = data.get('audio_data')
            
            # Save temporary audio file
            temp_audio_path = os.path.join(self.AUDIO_CHUNKS_PATH, f"temp_{user_id}.webm")
            with open(temp_audio_path, 'wb') as f:
                f.write(audio_data)

            # Convert to MP3
            temp_mp3_path = os.path.join(self.AUDIO_CHUNKS_PATH, f"temp_{user_id}.mp3")
            self.convert_to_mp3(temp_audio_path, temp_mp3_path)

            # Transcribe
            result = self.transcriber(temp_mp3_path, chunk_length_s=28, return_timestamps=True, 
                                    generate_kwargs={'num_beams': 5, 'task': 'transcribe', 'language': 'no'})
            
            # Clean up temporary files
            os.remove(temp_audio_path)
            os.remove(temp_mp3_path)

            # Send response
            await msg.respond(json.dumps({
                'status': 'success',
                'transcript': result['text']
            }).encode())

        except Exception as e:
            self.logger.error(f"Error handling transcribe request: {e}")
            await msg.respond(json.dumps({
                'status': 'error',
                'message': str(e)
            }).encode())

    def save_transcription(self, recording_id, transcription_results):
        transcription_text =  transcription_results['text']
        transcription_file = os.path.join(self.TRANSCRIPTIONS_PATH, f"{recording_id}.txt")
        with open(transcription_file, 'w') as f:
            f.write(transcription_text)
    
    def save_transcription_with_timestamps(self, recording_id, transcription_results):
        transcription_file = os.path.join(self.TRANSCRIPTIONS_PATH, f"{recording_id}_timestamps.txt")
        with open(transcription_file, 'w') as f:
            for chunk in transcription_results['chunks']:
                start_time, end_time = chunk['timestamp']
                transcribed_text = chunk['text']
                f.write(f"{start_time}-{end_time}: {transcribed_text}\n")

    def save_transcription_mp3(self, recording_id, transcription_results):
        transcription_text =  transcription_results['text']
        transcription_file = os.path.join(self.TRANSCRIPTIONS_PATH, f"{recording_id}_mp3.txt")
        with open(transcription_file, 'w') as f:
            f.write(transcription_text)
    
    def save_transcription_with_timestamps_mp3(self, recording_id, transcription_results):
        transcription_file = os.path.join(self.TRANSCRIPTIONS_PATH, f"{recording_id}_timestamps_mp3.txt")
        with open(transcription_file, 'w') as f:
            for chunk in transcription_results['chunks']:
                start_time, end_time = chunk['timestamp']
                transcribed_text = chunk['text']
                f.write(f"{start_time}-{end_time}: {transcribed_text}\n")
    async def subscribe(self):
        try:
            await self.nats_client.subscribe('recording.completed', self.handle_completed_recording)
            await self.nats_client.subscribe('transcribe', self.handle_transcribe)
            self.logger.info("Subscribed to 'recording.completed' and 'transcribe' subjects")
        except Exception as e:
            self.logger.error(f"Subscription error: {e}")
            raise

    async def run(self):
        await self.connect()
        await self.subscribe()

        try:
            self.logger.info("TranscriptionService is running.")
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Shutting down TranscriptionService...")
            await self.close()

    async def close(self):
        await self.nats_client.close()
        self.logger.info("TranscriptionService has been shut down.")

if __name__ == '__main__':
    service = TranscriptionService()
    asyncio.run(service.run())
    # asyncio.run(service.handle_completed_recording1("2ab35891-e791-4c41-afe8-2c96962db6ae"))


'''

python backend/transcription_service/transcription_service.py
'''