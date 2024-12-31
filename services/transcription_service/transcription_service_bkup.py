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
        # self.transcriber = pipeline("automatic-speech-recognition", "NbAiLabBeta/nb-whisper-large", device="cuda")
        self.transcriber = pipeline("automatic-speech-recognition", model="NbAiLab/nb-whisper-large-distil-turbo-beta")

        if not os.path.exists(self.TRANSCRIPTIONS_PATH):
            os.makedirs(self.TRANSCRIPTIONS_PATH)
        if not os.path.exists(self.AUDIO_CHUNKS_PATH):
            os.makedirs(self.AUDIO_CHUNKS_PATH)

    async def connect(self):
        try:
            await self.nats_client.connect()
            # Initialize KV store for transcriptions
            # self.nats_client.kv_transcriptions = await self.nats_client.setup_kv_bucket('transcriptions')
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
            payload = await self.token_validator.validate_access_token(data.get('access_token'))
            user_id = payload['user']['id']
            transcription_id = data.get('transcription_id')
            # transcription_id = template_data.get('id')
            transcription = await transcript_read(self.client, id=transcription_id)
            # transcription_meta = TranscriptionMeta.from_json(msg.data.decode())
            # recording_id = transcription_meta.id
            recording_id = transcription_id
            self.logger.info(f"Processing transcription for recording ID: {recording_id}")

            # Combined audio file path
            combined_audio_path = os.path.join(self.AUDIO_CHUNKS_PATH, f"{recording_id}_combined.webm")
            # wav_audio_path = os.path.join(self.AUDIO_CHUNKS_PATH, f"{recording_id}_combined.wav")
            mp3_audio_path = os.path.join(self.AUDIO_CHUNKS_PATH, f"{recording_id}_combined.mp3")

            if not os.path.exists(combined_audio_path):
                self.logger.error(f"Combined audio file not found: {combined_audio_path}")
                return

            # Convert to WAV format
            # self.convert_to_wav(combined_audio_path, wav_audio_path)

            # Convert to MP3 format
            self.convert_to_mp3(combined_audio_path, mp3_audio_path)


            # Transcribe audio
            # result = self.transcriber(wav_audio_path, chunk_length_s=28, return_timestamps=True, generate_kwargs={'num_beams': 5, 'task': 'transcribe', 'language': 'no'})
            result_mp3 = self.transcriber(mp3_audio_path, chunk_length_s=28, return_timestamps=True, generate_kwargs={'num_beams': 5, 'task': 'transcribe', 'language': 'no'})
            # segments, info  = self.transcriber.transcribe(mp3_audio_path, word_timestamps=True, chunk_length=28, batch_size=16, beam_size=5, language='no', task='transcribe')

            # print(info)
            # for segment in segments:
            #     print("[%.2fs -> %.2fs] %s" % (segment.start, segment.end, segment.text))

            # result_mp3 = self.transcriber(wav_audio_path, chunk_length_s=28, return_timestamps=True, generate_kwargs={'num_beams': 5, 'task': 'transcribe', 'language': 'no'})
            # print(result_mp3)
            # transcription_text = result['text']
            # transcription_text_mp3 = result_mp3['text']
            transcription_text = result_mp3['text']

            # Update transcription meta
            # transcription_meta.transcript = transcription_text
            # transcription_meta.status = 'not_signed'
            # transcription_meta.backend_status = 'transcription_service'
            # transcription_meta.updated_at = datetime.datetime.now(timezone.utc).isoformat()
            await transcript_update(self.client, 
                                    id=transcription_id, 
                                    transcript=transcription_text, 
                                    status='not_signed',  
                                    backend_status='transcription_service', 
                                    backend_updated_at=datetime.datetime.now(timezone.utc))

            # Save transcription
            # transcription_file = os.path.join(self.TRANSCRIPTIONS_PATH, f"{recording_id}.txt")
            # transcription_file_mp3 = os.path.join(self.TRANSCRIPTIONS_PATH, f"{recording_id}_mp3.txt")

            # self.save_transcription(recording_id, result)
            # self.save_transcription_mp3(recording_id, result_mp3)
            # self.save_transcription_with_timestamps(recording_id, result)
            # self.save_transcription_with_timestamps_mp3(recording_id, result_mp3)

            # with open(transcription_file, 'w') as f:
            #     f.write(transcription_text)
            # with open(transcription_file_mp3, 'w') as f:
            #     f.write(transcription_text_mp3)

            # Update KV store
            # await self.nats_client.kv_put(self.nats_client.kv_transcriptions, recording_id, transcription_meta.to_json())
            # updated_transcription = await transcript_read(self.client, id=transcription_id)

            # Notify summarization service
            await self.nats_client.publish('transcription.completed', json.dumps({"transcription_id":transcription_id}).encode())
            # await self.nats_client.publish('transcription.completed', transcription_meta.to_json())
            self.logger.info(f"Transcription completed for recording ID: {recording_id}")

            # Optionally, delete combined audio files
            # os.remove(combined_audio_path)
            # os.remove(wav_audio_path)

        except Exception as e:
            self.logger.error(f"Error processing recording {recording_id}: {e}")

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
            await self.nats_client.subscribe('recording.combined', self.handle_completed_recording)
            self.logger.info("Subscribed to 'recording.combined' subject")
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