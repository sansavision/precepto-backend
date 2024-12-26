import asyncio
import jwt
import json
import os
import sys
import logging
import uuid
from nats.js.errors import  KeyValueError
from typing import List

# Adjust the path to include the parent directory for imports
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from common.nats_client import NATSClient
from common.models import TranscriptTemplate

logging.basicConfig(level=logging.INFO)

class TemplateService:
    JWT_SECRET = os.environ.get('JWT_SECRET')
    JWT_ALGORITHM = 'HS256'

    # NATS Subjects
    SUBJECT_CREATE = 'template.create'
    SUBJECT_GET = 'template.get'
    SUBJECT_GET_ALL = 'template.get_all'
    SUBJECT_UPDATE = 'template.update'
    SUBJECT_DELETE = 'template.delete'
    SUBJECT_SHARE = 'template.share'

    BUCKET = 'templates'
    STREAM_NAME = 'precepto_template_service'
    STREAM_LISTEN_SUBJECT = ["templates"]

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.nats_client = NATSClient()
        self.kv_templates = None

    async def connect(self):
        try:
            await self.nats_client.connect()
            await self.nats_client.create_stream(self.STREAM_NAME, self.STREAM_LISTEN_SUBJECT)
            self.kv_templates = await self.nats_client.setup_kv_bucket(self.BUCKET)
            self.nats_client.kv_templates = self.kv_templates
            self.logger.info(f"Connected to KV store '{self.BUCKET}'")
        except Exception as e:
            self.logger.error(f"Failed to set up NATSClient: {e}")
            sys.exit(1)

    def verify_access_token(self, token):
        try:
            payload = jwt.decode(token, self.JWT_SECRET, algorithms=[self.JWT_ALGORITHM])
            if payload.get('type') != 'access':
                raise jwt.InvalidTokenError('Invalid token type')
            return payload.get('user')
        except jwt.ExpiredSignatureError:
            raise jwt.ExpiredSignatureError('Access token expired.')
        except jwt.InvalidTokenError:
            raise jwt.InvalidTokenError('Invalid access token.')

    async def handle_create_template(self, msg):
        try:
            data = json.loads(msg.data.decode())
            access_token = data.get('access_token')
            template_data = data.get('template')

            user = self.verify_access_token(access_token)
            user_id = user.get('id')

            template = TranscriptTemplate.from_json(json.dumps(template_data))
            template.id = str(uuid.uuid4())
            template.created_by_id = user_id

            await self.kv_templates.put(template.id, template.to_json().encode())
            print(template.to_json())
            response = {'status': 'success', 'template': json.loads(template.to_json())}
            await msg.respond(json.dumps(response).encode())
            self.logger.info(f"Template '{template.id}' created by user '{user_id}'")
        except Exception as e:
            self.logger.error(f"Create template error: {e}")
            response = {'status': 'error', 'message': 'Failed to create template.'}
            await msg.respond(json.dumps(response).encode())

    async def handle_get_template(self, msg):
        try:
            data = json.loads(msg.data.decode())
            access_token = data.get('access_token')
            template_id = data.get('template_id')

            user = self.verify_access_token(access_token)
            user_id = user.get('id')

            entry = await self.kv_templates.get(template_id)
            if not entry:
                response = {'status': 'error', 'message': 'Template not found.'}
                await msg.respond(json.dumps(response).encode())
                return

            template = TranscriptTemplate.from_json(entry.value.decode())

            if template.created_by_id != user_id and not template.is_public and user_id not in template.shared_with:
                response = {'status': 'error', 'message': 'Access denied.'}
                await msg.respond(json.dumps(response).encode())
                return

            response = {'status': 'success', 'template': json.loads(template.to_json())}
            await msg.respond(json.dumps(response).encode())
            self.logger.info(f"Template '{template.id}' retrieved by user '{user_id}'")
        except Exception as e:
            self.logger.error(f"Get template error: {e}")
            response = {'status': 'error', 'message': 'Failed to get template.'}
            await msg.respond(json.dumps(response).encode())

    async def handle_get_all_templates(self, msg):
        try:
            data = msg.data.decode('utf-8')
            self.logger.debug(f"Received data: {data}")
            data = json.loads(data)
            access_token = data.get('access_token')

            user = self.verify_access_token(access_token)
            user_id = user.get('id')

            templates = []
            try:
                keys = await self.kv_templates.keys()  # Await the coroutine to get the async iterator
            except KeyValueError as e:
                if 'no keys found' in str(e).lower():
                    self.logger.info("No existing templates found.")
                    keys = []
                else:
                    raise  # Re-raise the exception if it's a different error

            for key in keys:
                entry = await self.kv_templates.get(key)
                template = TranscriptTemplate.from_json(entry.value.decode('utf-8'))
                if (template.created_by_id == user_id or 
                    template.is_public or 
                    user_id in template.shared_with):
                    templates.append(template.to_dict())

            # If no templates, create a default template
            if not templates:
                default_template = TranscriptTemplate(
                    id=str(uuid.uuid4()),
                    name='Default Template',
                    template=self.load_default_template(),
                    created_by_id=user_id,
                    is_public=False,
                    shared_with=[]
                )
                await self.kv_templates.put(default_template.id, default_template.to_json().encode('utf-8'))
                templates.append(default_template.to_dict())
                self.logger.info(f"Default template created for user '{user_id}'")

            response = {'status': 'success', 'templates': templates}
            self.logger.debug(f"Responding with: {response}")
            await msg.respond(json.dumps(response).encode())
            self.logger.info(f"User '{user_id}' retrieved templates")
        
        except KeyValueError as e:
            if 'no keys found' in str(e).lower():
                self.logger.info("No existing templates found. Proceeding to create default template.")
                try:
                    default_template = TranscriptTemplate(
                        id=str(uuid.uuid4()),
                        name='Default Template',
                        template=self.load_default_template(),
                        created_by_id=user_id,
                        is_public=False,
                        shared_with=[]
                    )
                    await self.kv_templates.put(default_template.id, default_template.to_json().encode('utf-8'))
                    templates.append(default_template.to_dict())
                    self.logger.info(f"Default template created for user '{user_id}'")

                    response = {'status': 'success', 'templates': templates}
                    self.logger.debug(f"Responding with: {response}")
                    await msg.respond(json.dumps(response).encode())
                    self.logger.info(f"User '{user_id}' retrieved templates with default.")
                
                except Exception as create_e:
                    self.logger.error(f"Error creating default template: {create_e}")
                    response = {'status': 'error', 'message': 'Failed to create default template.'}
                    await msg.respond(json.dumps(response).encode('utf-8'))
            else:
                # Handle other KeyValueErrors
                self.logger.error(f"KeyValueError encountered: {e}")
                response = {'status': 'error', 'message': 'Failed to retrieve templates.'}
                await msg.respond(json.dumps(response).encode('utf-8'))
        
        except Exception as e:
            self.logger.error(f"Get all templates error: {e}")
            response = {'status': 'error', 'message': 'Failed to get templates.'}
            await msg.respond(json.dumps(response).encode('utf-8'))

    def load_default_template(self):
        try:
            template_path = os.path.join(os.path.dirname(__file__), 'default_template.json')
            with open(template_path, 'r', encoding='utf-8') as file:
                template_content = file.read()
            return template_content
        except FileNotFoundError:
            self.logger.error("Default template JSON file not found.")
            raise
        except json.JSONDecodeError as e:
            self.logger.error(f"Error decoding JSON from default template: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error loading default template: {e}")
            raise

    async def handle_update_template(self, msg):
        try:
            data = json.loads(msg.data.decode())
            access_token = data.get('access_token')
            template_data = data.get('template')

            user = self.verify_access_token(access_token)
            user_id = user.get('id')
            template_id = template_data.get('id')

            entry = await self.kv_templates.get(template_id)
            if not entry:
                response = {'status': 'error', 'message': 'Template not found.'}
                await msg.respond(json.dumps(response).encode())
                return

            existing_template = TranscriptTemplate.from_json(entry.value.decode())

            if existing_template.created_by_id != user_id:
                response = {'status': 'error', 'message': 'Access denied.'}
                await msg.respond(json.dumps(response).encode())
                return

            updated_template = TranscriptTemplate.from_json(json.dumps(template_data))
            updated_template.created_by_id = user_id

            await self.kv_templates.put(updated_template.id, updated_template.to_json().encode())

            response = {'status': 'success', 'template': json.loads(updated_template.to_json())}
            await msg.respond(json.dumps(response).encode())
            self.logger.info(f"Template '{template_id}' updated by user '{user_id}'")
        except Exception as e:
            self.logger.error(f"Update template error: {e}")
            response = {'status': 'error', 'message': 'Failed to update template.'}
            await msg.respond(json.dumps(response).encode())

    async def handle_delete_template(self, msg):
        try:
            data = json.loads(msg.data.decode())
            access_token = data.get('access_token')
            template_id = data.get('template_id')

            user = self.verify_access_token(access_token)
            user_id = user.get('id')

            entry = await self.kv_templates.get(template_id)
            if not entry:
                response = {'status': 'error', 'message': 'Template not found.'}
                await msg.respond(json.dumps(response).encode())
                return

            template = TranscriptTemplate.from_json(entry.value.decode())

            if template.created_by_id != user_id:
                response = {'status': 'error', 'message': 'Access denied.'}
                await msg.respond(json.dumps(response).encode())
                return

            await self.kv_templates.delete(template_id)

            response = {'status': 'success', 'message': 'Template deleted successfully.'}
            await msg.respond(json.dumps(response).encode())
            self.logger.info(f"Template '{template_id}' deleted by user '{user_id}'")
        except Exception as e:
            self.logger.error(f"Delete template error: {e}")
            response = {'status': 'error', 'message': 'Failed to delete template.'}
            await msg.respond(json.dumps(response).encode())

    async def handle_share_template(self, msg):
        try:
            data = json.loads(msg.data.decode())
            access_token = data.get('access_token')
            template_id = data.get('template_id')
            share_user_id = data.get('user_id')

            user = self.verify_access_token(access_token)
            user_id = user.get('id')

            # Optional: Verify that share_user_id exists in the system
            # You might need to interact with the user service or KV store to confirm

            # Fetch the template
            entry = await self.kv_templates.get(template_id)
            if not entry:
                response = {'status': 'error', 'message': 'Template not found.'}
                await msg.respond(json.dumps(response).encode())
                return

            template = TranscriptTemplate.from_json(entry.value.decode('utf-8'))

            if template.created_by_id != user_id:
                response = {'status': 'error', 'message': 'Access denied.'}
                await msg.respond(json.dumps(response).encode())
                return

            if share_user_id in template.shared_with:
                response = {'status': 'error', 'message': 'Template already shared with this user.'}
                await msg.respond(json.dumps(response).encode())
                return

            # Optional: Prevent sharing with oneself
            if share_user_id == user_id:
                response = {'status': 'error', 'message': 'Cannot share template with yourself.'}
                await msg.respond(json.dumps(response).encode())
                return

            # Append the user to shared_with
            template.shared_with.append(share_user_id)
            await self.kv_templates.put(template.id, template.to_json().encode())

            response = {'status': 'success', 'template': json.loads(template.to_json())}
            await msg.respond(json.dumps(response).encode())
            self.logger.info(f"Template '{template.id}' shared with user '{share_user_id}' by '{user_id}'")
        except Exception as e:
            self.logger.error(f"Share template error: {e}")
            response = {'status': 'error', 'message': 'Failed to share template.'}
            await msg.respond(json.dumps(response).encode())

    async def subscribe(self):
        await self.nats_client.nc.subscribe(self.SUBJECT_CREATE, cb=self.handle_create_template)
        await self.nats_client.nc.subscribe(self.SUBJECT_GET, cb=self.handle_get_template)
        await self.nats_client.nc.subscribe(self.SUBJECT_GET_ALL, cb=self.handle_get_all_templates)
        await self.nats_client.nc.subscribe(self.SUBJECT_UPDATE, cb=self.handle_update_template)
        await self.nats_client.nc.subscribe(self.SUBJECT_DELETE, cb=self.handle_delete_template)
        await self.nats_client.nc.subscribe(self.SUBJECT_SHARE, cb=self.handle_share_template)

        self.logger.info("Subscribed to template subjects")

    async def run(self):
        await self.connect()
        await self.subscribe()

        try:
            self.logger.info("TemplateService is running.")
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Shutting down TemplateService...")
            await self.nats_client.close()

if __name__ == '__main__':
    service = TemplateService()
    asyncio.run(service.run())


'''
python backend/template_service/template_service.py

'''