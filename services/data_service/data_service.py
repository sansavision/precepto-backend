# services/data_service/data_service.py
import asyncio
import json
import os
import sys
import logging
from typing import List

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from common.nats_client import NATSClient
# from common.models import TranscriptionMeta
from common.queries.transcriptions.transcript_read_async_edgeql import  transcript_read,TranscriptReadResult as TranscriptionMeta
from common.queries.transcriptions.transcript_read_all_async_edgeql import transcript_read_all
from common.queries.transcriptions.transcript_create_async_edgeql import transcript_create
from common.queries.transcriptions.transcript_update_async_edgeql import transcript_update 
from common.queries.transcriptions.transcript_delete_async_edgeql import transcript_delete 
from common.edgedb_client import EdgedbClient, DataclassEncoder
from common.token_utils import TokenValidator

logging.basicConfig(level=logging.INFO)


if os.environ.get('PROD_MODE',"false") == 'false':
    # only in dev
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=os.path.join(os.path.pardir,".env"))

class DataService:
    SUBJECT = 'data.transcriptions.get'
    SUBJECT_CREATE = 'data.transcriptions.create'
    SUBJECT_UPDATE = 'data.transcriptions.update'
    SUBJECT_DELETE = 'data.transcriptions.delete'
    STREAM_NAME = 'precepto_data_service'
    STREAM_LISTEN_SUBJECT = ["precepto.data.*"]
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.db = EdgedbClient()
        self.client = self.db.client
        self.nats_client = NATSClient()
        self.token_validator = TokenValidator()

    async def connect(self):
        """Initialize connections to NATS and create necessary stream"""
        try:
            await self.nats_client.connect()
            await self.nats_client.create_stream(self.STREAM_NAME, self.STREAM_LISTEN_SUBJECT)
            self.logger.info("Connected to NATS and set up stream")
        except Exception as e:
            self.logger.error(f"Failed to connect and set up NATSClient: {e}")
            raise

    async def get_user_transcriptions(self, user_id: str) -> List[TranscriptionMeta]:
        """Fetch transcriptions for a specific user"""
        try:
            # cursor = self.db.transcriptions_collection.find({"created_by_id": user_id})
            # transcriptions = []
            # async for doc in cursor:
            #     try:
            #         transcription = TranscriptionMeta(**doc)
            #         transcriptions.append(transcription.model_dump(by_alias=True))
            #     except Exception as e:
            #         self.logger.error(f"Error processing transcription document: {e}")
            #         continue
            transcriptions = await transcript_read_all(self.client, user_id=user_id)
            return transcriptions
        except Exception as e:
            self.logger.error(f"Error fetching transcriptions: {e}")
            raise

    async def create_transcription(self, transcription_data: dict, user_id: str):
        """Create a new transcription"""
        try:
            print("transcription_data before create",transcription_data)
            transcription_data['backend_status'] = "draft"
            transcription_data['backend_step'] = "draft"
            transcription_data['backend_step_duration'] = 0
            transcription_data['backend_step_is_success'] = True
            transcription_data['translation_language'] = "no"
            transcription_data['translation'] = "Not yet completed"
            
            print("transcription_data before create 2",transcription_data)
            result = await transcript_create(self.client, **transcription_data, user_id=user_id)
            print("transcription_data after create 2",result)
            return result
        except Exception as e:
            self.logger.error(f"Error creating transcription: {e}")
            raise

    async def update_transcription(self, transcription_id: str, update_data: dict, user_id: str):
        """Update an existing transcription"""
        update_data['backend_status'] = "draft"
        update_data['next_backend_step'] = "recording_service"

        # update_data['backend_step'] = "draft"
        # update_data['backend_step_duration'] = 0
        # update_data['backend_step_is_success'] = True
        # update_data['translation_language'] = "no"
        # update_data['translation'] = "Not yet completed"
        self.logger.info(f"Updating transcription {transcription_id} with data: {update_data} by user {user_id}")
        try:
            result = await transcript_update(self.client, **update_data, id=transcription_id,)
            return result
        except Exception as e:
            self.logger.error(f"Error updating transcription: {e}")
            raise

    async def delete_transcription(self, transcription_id: str, user_id: str):
        """Delete a transcription"""
        self.logger.info(f"Deleting transcription {transcription_id} by user {user_id}")
        try:
            result = await transcript_delete(self.client, id=transcription_id)
            return result
        except Exception as e:
            self.logger.error(f"Error deleting transcription: {e}")
            raise

    async def handle_get_transcriptions(self, msg):
        """Handle incoming requests for user transcriptions"""
        try:
            data = json.loads(msg.data.decode('utf-8'))
            access_token = data.get('access_token')

            # Validate token and extract user information
            payload = await self.token_validator.validate_access_token(access_token)
            user_id = payload['user']['id']

            # Fetch transcriptions
            transcriptions = await self.get_user_transcriptions(user_id)
            
            response = {
                'status': 'success',
                'transcriptions': transcriptions,
            }
            await msg.respond(json.dumps(response, cls=DataclassEncoder).encode('utf-8'))
            self.logger.info(f"Successfully returned {len(transcriptions)} transcriptions for user {user_id}")

        except Exception as e:
            error_msg = str(e).lower()
            if 'no keys found' in error_msg:
                response = {
                    'status': 'success',
                    'transcriptions': [],
                }
            else:
                self.logger.error(f"Error handling transcription request: {e}")
                response = {
                    'status': 'error',
                    'message': str(e) if hasattr(e, 'message') else 'Failed to get transcriptions'
                }
            await msg.respond(json.dumps(response).encode('utf-8'))

    async def handle_create_transcription(self, msg):
        """Handle incoming create transcription requests"""
        try:
            data = json.loads(msg.data.decode('utf-8'))
            print("got data msg on create" ,data)
            access_token = data.get('access_token')
            transcription_data = data.get('transcription')
            

            payload = await self.token_validator.validate_access_token(access_token)
            user_id = payload['user']['id']
            del transcription_data['id']
            del transcription_data['created_at']
            del transcription_data['created_by_id']
            result = await self.create_transcription(transcription_data, user_id)
            # result = await transcript_read(self.client, user_id=user_id)
            print("result after create",result)
            response = {
                'status': 'success',
                'transcription': result
            }
            await msg.respond(json.dumps(response, cls=DataclassEncoder).encode('utf-8'))

        except Exception as e:
            self.logger.error(f"Error handling create transcription request: {e}")
            response = {
                'status': 'error',
                'message': str(e)
            }
            await msg.respond(json.dumps(response).encode('utf-8'))

    async def handle_update_transcription(self, msg):
        """Handle incoming update transcription requests"""
        try:
            data = json.loads(msg.data.decode('utf-8'))
            access_token = data.get('access_token')
            # transcription_id = data.get('transcription_id')
            update_data = data.get('transcription')
            transcription_id = update_data.get('id')
            del update_data['id']
            del update_data['created_at']
            payload = await self.token_validator.validate_access_token(access_token)
            user_id = payload['user']['id']

            result = await self.update_transcription(transcription_id, update_data, user_id)
            response = {
                'status': 'success',
                'transcription': result
            }
            await msg.respond(json.dumps(response, cls=DataclassEncoder).encode('utf-8'))

        except Exception as e:
            self.logger.error(f"Error handling update transcription request: {e}")
            response = {
                'status': 'error',
                'message': str(e)
            }
            await msg.respond(json.dumps(response).encode('utf-8'))

    async def handle_delete_transcription(self, msg):
        """Handle incoming delete transcription requests"""
        try:
            data = json.loads(msg.data.decode('utf-8'))
            access_token = data.get('access_token')
            transcription_id = data.get('transcription_id')

            payload = await self.token_validator.validate_access_token(access_token)
            user_id = payload['user']['id']

            result = await self.delete_transcription(transcription_id, user_id)
            response = {
                'status': 'success',
                'deleted': True
            }
            await msg.respond(json.dumps(response, cls=DataclassEncoder).encode('utf-8'))

        except Exception as e:
            self.logger.error(f"Error handling delete transcription request: {e}")
            response = {
                'status': 'error',
                'message': str(e)
            }
            await msg.respond(json.dumps(response).encode('utf-8'))

    async def subscribe(self):
        """Set up subscription to NATS subjects"""
        try:
            await self.nats_client.subscribe(self.SUBJECT, cb=self.handle_get_transcriptions)
            await self.nats_client.subscribe(self.SUBJECT_CREATE, cb=self.handle_create_transcription)
            await self.nats_client.subscribe(self.SUBJECT_UPDATE, cb=self.handle_update_transcription)
            await self.nats_client.subscribe(self.SUBJECT_DELETE, cb=self.handle_delete_transcription)
            self.logger.info("Subscribed to all CRUD subjects")
        except Exception as e:
            self.logger.error(f"Failed to subscribe: {e}")
            raise

    async def run(self):
        """Main service run loop"""
        try:
            await self.connect()
            await self.subscribe()

            self.logger.info("DataService is running. Press Ctrl+C to exit.")
            while True:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            self.logger.info("Shutting down DataService...")
        except Exception as e:
            self.logger.error(f"Service error: {e}")
        finally:
            await self.cleanup()

    async def cleanup(self):
        """Cleanup resources"""
        try:
            await self.nats_client.close()
            self.logger.info("DataService has been shut down.")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

if __name__ == '__main__':
    service = DataService()
    asyncio.run(service.run())