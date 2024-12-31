import asyncio
import json
import os
import sys
import logging
import uuid
from typing import List

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from common.nats_client import NATSClient
# from common.models import JSONEncoder, TranscriptTemplate
from common.edgedb_client import EdgedbClient, DataclassEncoder
from common.token_utils import TokenValidator

from common.queries.templates.template_create_async_edgeql import template_create, TemplateCreateResult as TranscriptTemplate 
from common.queries.templates.template_read_async_edgeql import template_read
from common.queries.templates.template_read_all_async_edgeql import template_read_all
from common.queries.templates.template_update_async_edgeql import template_update
from common.queries.templates.template_delete_async_edgeql import template_delete


logging.basicConfig(level=logging.INFO)

if os.environ.get('PROD_MODE', "false") == 'false':
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=os.path.join(os.path.pardir, ".env"))



class TemplateService:
    SUBJECT_CREATE = 'template.create'
    SUBJECT_GET = 'template.get'
    SUBJECT_GET_ALL = 'template.get_all'
    SUBJECT_UPDATE = 'template.update'
    SUBJECT_DELETE = 'template.delete'
    SUBJECT_SHARE = 'template.share'
    STREAM_NAME = 'precepto_template_service'
    STREAM_LISTEN_SUBJECT = ["precepto.template.*"]

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.db = EdgedbClient()
        self.client = self.db.client
        self.nats_client = NATSClient()
        self.token_validator = TokenValidator(
            secret_key=os.environ.get('JWT_SECRET'),
            algorithm='HS256'
        )

    async def connect(self):
        try:
            await self.nats_client.connect()
            await self.nats_client.create_stream(self.STREAM_NAME, self.STREAM_LISTEN_SUBJECT)
            self.logger.info("Connected to NATS and created stream")
        except Exception as e:
            self.logger.error(f"Failed to set up NATSClient: {e}")
            raise

    async def handle_create_template(self, msg):
        try:
            data = json.loads(msg.data.decode())
            payload = await self.token_validator.validate_access_token(data.get('access_token'))
            user_id = payload['user']['id']

            template_data = data.get('template')
            self.logger.info(f"Template created by user xx template_data'{template_data}'")
            # template = TranscriptTemplate(**template_data)
            # template.created_by_id = user_id
            # print("template before create",template)
            # result = await self.db.templates_collection.insert_one(template.model_dump(by_alias=True))
            del template_data['created_by_id']
            del template_data['created_at']
            del template_data['updated_at']
            del template_data['shared_with']
            del template_data['id']

            result = await template_create(self.client, **template_data, user_id=user_id)
            # template.id = result.inserted_id
            print("template after create",result)
            response = {
                'status': 'success', 
                # 'template': template.model_dump(by_alias=True)
                'template': result
            }
            await msg.respond(json.dumps(response, cls=DataclassEncoder).encode())
            self.logger.info(f"Template created by user '{user_id}'")

        except Exception as e:
            self.logger.error(f"Create template error: {e}")
            response = {'status': 'error', 'message': str(e)}
            await msg.respond(json.dumps(response).encode())

    async def handle_get_template(self, msg):
        try:
            data = json.loads(msg.data.decode())
            payload = await self.token_validator.validate_access_token(data.get('access_token'))
            user_id = payload['user']['id']
            template_id = data.get('template_id')
            
            # template_doc = await self.db.templates_collection.find_one({"_id": template_id})
            template_doc = await template_read(self.client, id= template_id)
            if not template_doc:
                raise ValueError('Template not found')

            # template = TranscriptTemplate(**template_doc)
            # if not (template_doc.created_by.id == user_id or template_doc.is_public or user_id in template_doc.shared_with):
            if not (str(template_doc.created_by.id) == user_id or template_doc.is_public):
                raise ValueError('Access denied')

            response = {
                'status': 'success',
                'template': template_doc, #template.model_dump(by_alias=True)
            }
            await msg.respond(json.dumps(response).encode())

        except Exception as e:
            self.logger.error(f"Get template error: {e}")
            response = {'status': 'error', 'message': str(e)}
            await msg.respond(json.dumps(response).encode())

    async def load_default_template(self) -> str:
        template_path = os.path.join(os.path.dirname(__file__), 'default_template.json')
        with open(template_path, 'r', encoding='utf-8') as file:
            return file.read()



    async def handle_get_all_templates_internal(self, msg, user_id):
            try:
                templates = await template_read_all(self.client, user_id=user_id)
                
                # Convert EdgeDB objects to dictionaries and handle datetime serialization
                serialized_templates = []
                for template in templates:
                    template_dict = self.db.edgedb_to_dict(template)
                    # Convert datetime objects to ISO format strings
                    template_dict['created_at'] = template_dict['created_at'].isoformat()
                    template_dict['updated_at'] = template_dict['updated_at'].isoformat()
                    serialized_templates.append(template_dict)
                
                response = {'status': 'success', 'templates': serialized_templates}
                await msg.respond(json.dumps(response).encode())
                
            except Exception as e:
                self.logger.error(f"Get all templates error: {str(e)}")
                error_response = {'status': 'error', 'message': str(e)}
                await msg.respond(json.dumps(error_response).encode())

    async def handle_get_all_template(self, msg):
        try:
            data = json.loads(msg.data.decode())
            payload = await self.token_validator.validate_access_token(data.get('access_token'))
            user_id = payload['user']['id']

            # query = {
            #     "$or": [
            #         {"created_by_id": user_id},
            #         {"is_public": True},
            #         {"shared_with": user_id}
            #     ]
            # }
            
            # templates = []
            # async for doc in self.db.templates_collection.find(query):
            #     template = TranscriptTemplate(**doc)
            #     templates.append(template.model_dump(by_alias=True))
            templates = await template_read_all(self.client, user_id=user_id)
            if not templates:
                # Create default template without id (MongoDB will generate it)
                default_template_data = {
                    "name": "Default Template",
                    "template": await self.load_default_template(),
                    # "created_by_id": user_id,
                    "is_public": False,
                    # "shared_with": []
                }
                
                # result = await self.db.templates_collection.insert_one(default_template_data)
                result = await template_create(self.client, **default_template_data, user_id=user_id)
                # default_template_data["_id"] = result.inserted_id
                # templates.append(TranscriptTemplate(**default_template_data).model_dump(by_alias=True))
            templates = await template_read_all(self.client, user_id=user_id)
            print("templates pre serilizase")
            # serialized_templates = []
            # for template in templates:
            #     try:
            #         template_dict = self.db.serialize_edgedb_to_json_dict(template)
            #         # Convert datetime objects to ISO format strings
            #         # template_dict['created_at'] = template_dict['created_at'].isoformat()
            #         # template_dict['updated_at'] = template_dict['updated_at'].isoformat()
            #         serialized_templates.append(template_dict)
            #     except Exception as e:
            #         self.logger.error(f"Error processing template document: {e}")
            # # serialized_templates = list(map(lambda x: self.db.serialize_edgedb_to_json_dict(x), templates))
            # json.dumps(response, cls=DataclassEncoder)
            # print("templates after serilizase",serialized_templates)
            # for t in templates:
            #     template_dict = self.db.serialize_edgedb_to_json_dict(t)
            response = {'status': 'success', 'templates': templates}
            # await msg.respond(json.dumps(response, cls=JSONEncoder).encode())
            await msg.respond(json.dumps(response,  cls=DataclassEncoder).encode())

        except Exception as e:
            self.logger.error(f"Get all templates error: {e}")
            response = {'status': 'error', 'message': str(e)}
            # await msg.respond(json.dumps(response, cls=JSONEncoder).encode())
            await msg.respond(json.dumps(response).encode())

    async def handle_update_template(self, msg):
        try:
            data = json.loads(msg.data.decode())
            print( " got data", data)
            payload = await self.token_validator.validate_access_token(data.get('access_token'))
            user_id = payload['user']['id']
            print ("user_id",user_id)
            template_data = data.get('template')
            print("template_data",template_data)
            # template_doc = await self.db.templates_collection.find_one({"_id": template_data['_id']})
            template_doc = await template_read(self.client, id=template_data['id'])
            print("template_doc after read template",template_doc)
            if not template_doc:
                raise ValueError('Template not found')
            print("template_doc. compare",template_doc.created_by.id, user_id)
            # existing_template = TranscriptTemplate(**template_doc)
            if str(template_doc.created_by.id) != user_id:
                raise ValueError('Access denied')
            print("after complare")
            # updated_template = TranscriptTemplate(**template_data)
            # result = await self.db.templates_collection.replace_one(
            #     {"_id": template_data['_id']},
            #     updated_template.model_dump(by_alias=True)
            # )
            del template_data['created_by']
            del template_data['created_at']
            del template_data['updated_at']
            del template_data['shared_with']
            del template_data['id']
            await template_update(self.client, **template_data, id=template_doc.id)
            template_new = await template_read(self.client, id=template_doc.id)
            response = {
                'status': 'success',
                'template': template_new,
                # 'template': updated_template.model_dump(by_alias=True)
            }
            await msg.respond(json.dumps(response, cls=DataclassEncoder).encode())

        except Exception as e:
            self.logger.error(f"Update template error: {e}")
            response = {'status': 'error', 'message': str(e)}
            await msg.respond(json.dumps(response).encode())

    async def handle_delete_template(self, msg):
        try:
            data = json.loads(msg.data.decode())
            payload = await self.token_validator.validate_access_token(data.get('access_token'))
            user_id = payload['user']['id']
            template_id = data.get('template_id')

            # template_doc = await self.db.templates_collection.find_one({"_id": template_id})
            template_doc = await template_read(self.client, id= template_id)
            if not template_doc:
                raise ValueError('Template not found')

            # template = TranscriptTemplate(**template_doc)
            if str(template_doc.created_by.id) != user_id:
                raise ValueError('Access denied')

            # await self.db.templates_collection.delete_one({"_id": template_id})
            await template_delete(self.client, id= template_id)
            response = {'status': 'success', 'message': 'Template deleted successfully'}
            await msg.respond(json.dumps(response).encode())

        except Exception as e:
            self.logger.error(f"Delete template error: {e}")
            response = {'status': 'error', 'message': str(e)}
            await msg.respond(json.dumps(response).encode())

    # async def handle_share_template(self, msg):
    #     try:
    #         data = json.loads(msg.data.decode())
    #         payload = await self.token_validator.validate_access_token(data.get('access_token'))
    #         user_id = payload['user']['id']
    #         template_id = data.get('template_id')
    #         share_user_id = data.get('user_id')

    #         if share_user_id == user_id:
    #             raise ValueError('Cannot share template with yourself')

    #         # template_doc = await self.db.templates_collection.find_one({"_id": template_id})
    #         template_doc = await template_read(self.client, id= template_id)
    #         if not template_doc:
    #             raise ValueError('Template not found')

    #         # template = TranscriptTemplate(**template_doc)
    #         if template_doc.created_by.id != user_id:
    #             raise ValueError('Access denied')

    #         if share_user_id in template_doc.shared_with:
    #             raise ValueError('Template already shared with this user')

    #         # result = await self.db.templates_collection.update_one(
    #         #     {"_id": template_id},
    #         #     {"$push": {"shared_with": share_user_id}}
    #         # )

    #         template = await template_update(self.client, id=template_id, )

    #         template.shared_with.append(share_user_id)
    #         response = {
    #             'status': 'success',
    #             'template': template.model_dump(by_alias=True)
    #         }
    #         await msg.respond(json.dumps(response).encode())

    #     except Exception as e:
    #         self.logger.error(f"Share template error: {e}")
    #         response = {'status': 'error', 'message': str(e)}
    #         await msg.respond(json.dumps(response).encode())

    async def subscribe(self):
        try:
            for subject in [
                self.SUBJECT_CREATE,
                self.SUBJECT_GET,
                self.SUBJECT_GET_ALL,
                self.SUBJECT_UPDATE,
                self.SUBJECT_DELETE,
                # self.SUBJECT_SHARE
            ]:
                await self.nats_client.subscribe(
                    subject,
                    cb=getattr(self, f"handle_{subject.split('.')[-1]}_template")
                )
            self.logger.info("Subscribed to all template subjects")
        except Exception as e:
            self.logger.error(f"Subscription error: {e}")
            raise

    async def run(self):
        try:
            await self.connect()
            await self.subscribe()
            
            self.logger.info("TemplateService is running")
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Shutting down TemplateService")
        finally:
            await self.nats_client.close()

if __name__ == '__main__':
    service = TemplateService()
    asyncio.run(service.run())