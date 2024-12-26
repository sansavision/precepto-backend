# services/data_service/data_service.py
import asyncio
import jwt
import json
import os
import sys
import logging

# Adjust the path to include the parent directory for imports
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from common.nats_client import NATSClient
from common.models import TranscriptionMeta

logging.basicConfig(level=logging.INFO)

class DataService:
    JWT_SECRET =  os.environ.get('JWT_SECRET')
    JWT_ALGORITHM = 'HS256'
    SUBJECT = 'data.transcriptions.get'
    BUCKET = 'transcriptions'
    STREAM_NAME = 'precepto_data_service'
    STREAM_LISTEN_SUBJECT = ["precepto.data"]
    
    def __init__(self):
        # Setup logging
        self.logger = logging.getLogger(self.__class__.__name__)
        # Initialize NATS client
        self.nats_client = NATSClient()
        self.kv_transcriptions = None

    async def connect(self):
        try:
            await self.nats_client.connect()
            await self.nats_client.create_stream(self.STREAM_NAME, self.STREAM_LISTEN_SUBJECT)
            self.kv_transcriptions = await self.nats_client.setup_kv_bucket(self.BUCKET)
            self.nats_client.kv_transcriptions = self.kv_transcriptions
            self.logger.info(f"Connected to KV store '{self.BUCKET}'")
        except Exception as e:
            self.logger.error(f"Failed to connect and set up NATSClient: {e}")
            sys.exit(1)  # Exit if connection fails

    async def handle_get_transcriptions(self, msg):
        try:
            data = msg.data.decode('utf-8')
            self.logger.debug(f"Received data: {data}")
            data = json.loads(data)  # Expected format: {'access_token': '...'}
            access_token = data.get('access_token')

            if not access_token:
                raise jwt.InvalidTokenError('Access token missing')

            # Verify access token
            payload = jwt.decode(access_token, self.JWT_SECRET, algorithms=[self.JWT_ALGORITHM])

            if payload.get('type') != 'access':
                raise jwt.InvalidTokenError('Invalid token type')

            user = payload.get('user')
            user_id = user.get('id')

            # Fetch all transcriptions from KV store
            transcriptions = []
            keys_iter = await self.kv_transcriptions.keys()
            for key in keys_iter:
                entry = await self.kv_transcriptions.get(key)
                transcription = TranscriptionMeta.from_json(entry.value.decode('utf-8'))
                # Check if the transcription belongs to the user
                if transcription.created_by_id == user_id:
                    transcriptions.append(transcription.to_dict())
                    
            self.logger.info(f"Fetched {len(transcriptions)} transcriptions for user '{user_id}'")
            response = {
                'status': 'success',
                'transcriptions': transcriptions,
            }
            await msg.respond(json.dumps(response).encode('utf-8'))
            self.logger.info(f"Fetched {len(transcriptions)} transcriptions for user '{user_id}'")
        except jwt.ExpiredSignatureError:
            response = {'status': 'error', 'message': 'Access token expired.'}
            await msg.respond(json.dumps(response).encode('utf-8'))
            self.logger.warning("Access token expired.")
        except jwt.InvalidTokenError as e:
            response = {'status': 'error', 'message': 'Invalid access token.'}
            await msg.respond(json.dumps(response).encode('utf-8'))
            self.logger.warning(f"Invalid access token: {e}")
        except Exception as e:
            # Check if it's a 'no keys found' error
            error_message = str(e).lower()
            if 'no keys found' in error_message:
                # Respond with empty transcriptions
                response = {
                    'status': 'success',
                    'transcriptions': [],
                }
                await msg.respond(json.dumps(response).encode('utf-8'))
                self.logger.info(f"No transcriptions found for user '{user_id}'")
            else:
                self.logger.error(f"Get transcriptions error: {e}")
                response = {'status': 'error', 'message': 'Failed to get transcriptions.'}
                await msg.respond(json.dumps(response).encode('utf-8'))

    async def subscribe(self):
        await self.nats_client.nc.subscribe(self.SUBJECT, cb=self.handle_get_transcriptions)
        self.logger.info(f"Subscribed to subject '{self.SUBJECT}'")

    async def run(self):
        await self.connect()
        await self.subscribe()

        # Keep the service running
        try:
            self.logger.info("DataService is running. Press Ctrl+C to exit.")
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Shutting down DataService...")
            await self.close()

    async def close(self):
        await self.nats_client.close()
        self.logger.info("DataService has been shut down.")

if __name__ == '__main__':
    service = DataService()
    asyncio.run(service.run())


'''
python backend/data_service/data_service.py

'''