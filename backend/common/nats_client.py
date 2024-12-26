# common/nats_client.py
import asyncio
import json
from nats.aio.client import Client as NATS
from nats.js.errors import BucketNotFoundError, APIError, NotFoundError
from nats.js.api import StreamConfig, StreamInfo
# from nats.js.api import KeyValue

import os
import sys
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from common.models import User, TranscriptTemplate, TranscriptionMeta
import logging
from typing import List, Optional

class NATSClient:
    def __init__(self, loop=None):
        self.loop = loop or asyncio.get_event_loop()
        self.nc = NATS()
        self.js = None
        self.kv_users: Optional[any] = None
        self.kv_templates: Optional[any] = None
        self.kv_transcriptions: Optional[any] = None
        self.kv_templates: Optional[any] = None
        self.logger = logging.getLogger(self.__class__.__name__)
        self.nats_url = json.loads('["nats://nats1.sansadev.com:4222", "nats://nats2.sansadev.com:4223", "nats://nats3.sansadev.com:4224"]')

    async def delete_stream(self, name_string:str):
        stream_name = name_string
        try:
            await self.js.delete_stream(stream_name)
            logging.info(f"Stream '{stream_name}' deleted successfully.")
        except APIError as e:
            logging.error(f"APIError while deleting stream '{stream_name}': {e}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error while deleting stream '{stream_name}': {e}")
            raise
    async def connect(self, servers=["nats://localhost:4222"]):
        try:
            await self.nc.connect(servers=self.nats_url ) # loop=self.loop
            self.js = self.nc.jetstream()
            self.logger.info("Connected to NATS")

            # # Create the stream if it doesn't exist
            # await self.create_stream()

            # # Create or access the KV bucket
            # await self.setup_kv_bucket()

        except Exception as e:
            self.logger.error(f"Error connecting to NATS: {e}")
            raise

        # # Initialize KV stores
        # self.kv_users = await self.js.key_value(bucket='users')
        # self.kv_templates = await self.js.key_value(bucket='templates')
        # self.kv_transcriptions = await self.js.key_value(bucket='transcriptions')

    async def create_stream(self, name_string:str, subjects_list: List[str]):
        # stream_name = "precepto_authentication_service"
        # subjects = ["precepto.auth.*"]
        stream_name = name_string
        subjects = subjects_list

        try:
            # Check if the stream already exists
            stream_info = await self.js.stream_info(stream_name)
            logging.info(f"Stream '{stream_name}' already exists.")
        except NotFoundError:
            # Stream does not exist, create it
            stream_config = StreamConfig(
                name=stream_name,
                subjects=subjects,
                storage="file",  # Options: "file" or "memory"
                retention="limits",  # Options: "limits", "interest", "workqueue"
                max_msgs=100000,
                max_bytes=1_000_000_000,  # 1 GB
                max_age=72 * 3600,  # 72 hours in seconds
                # dup_window=120,  # 2 minutes in seconds
            )

            try:
                await self.js.add_stream(stream_config)
                logging.info(f"Stream '{stream_name}' created successfully.")
            except APIError as e:
                logging.error(f"APIError while creating stream '{stream_name}': {e}")
                raise
            except Exception as e:
                logging.error(f"Unexpected error while creating stream '{stream_name}': {e}")
                raise

    async def setup_kv_bucket(self,name:str):
        bucket_name = name
        kv = None
        try:
            # Attempt to access the KV bucket
            # self.kv_users = await self.js.key_value(bucket=bucket_name)
            kv = await self.js.create_key_value(bucket=bucket_name)
            logging.info(f"KV bucket '{bucket_name}' accessed successfully.")
            return kv
        except NotFoundError:
            # KV bucket does not exist, create it
            logging.info(f"KV bucket '{bucket_name}' not found. Creating it.")
            try:
                kv = await self.js.create_key_value(bucket=bucket_name)
                logging.info(f"KV bucket '{bucket_name}' created successfully.")
                return kv
            except APIError as e:
                logging.error(f"APIError while creating KV bucket '{bucket_name}': {e}")
                raise
            except Exception as e:
                logging.error(f"Unexpected error while creating KV bucket '{bucket_name}': {e}")
                raise
        except APIError as e:
            logging.error(f"APIError while accessing KV bucket '{bucket_name}': {e}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error while accessing KV bucket '{bucket_name}': {e}")
            raise

    async def kv_put(self, bucket: any, key: str, value: str):
        await bucket.put(key, value.encode())
        self.logger.info(f"KV Put: {key}")

    async def kv_get(self, bucket: any, key: str) -> Optional[str]:
        try:
            entry = await bucket.get(key)
            self.logger.info(f"KV Get: {key}")
            return entry.value.decode()
        except Exception as e:
            self.logger.error(f"KV Get Error: {e}")
            return None

    async def kv_delete(self, kv_store, key):
        try:
            await kv_store.delete(key)
            self.logger.info(f"Deleted key '{key}' from KV store")
        except Exception as e:
            self.logger.error(f"Failed to delete key '{key}' from KV store: {e}")

    async def subscribe(self, subject: str, callback):
        await self.nc.subscribe(subject, cb=callback)
        self.logger.info(f"Subscribed to subject: {subject}")

    async def publish(self, subject: str, message: str, headers=None):
        await self.nc.publish(subject, message.encode(), headers=headers)
        self.logger.info(f"Published to subject: {subject}")

    async def close(self):
        await self.nc.close()
        self.logger.info("Disconnected from NATS")





    # async def create_stream(self):
    #     stream_name = "precepto_authentication_service"
    #     subjects = ["precepto.auth.*"]

    #     try:
    #         # Check if the stream already exists
    #         stream_info = await self.js.stream_info(stream_name)
    #         logging.info(f"Stream '{stream_name}' already exists.")
    #     except NotFoundError:
    #         # Stream does not exist, create it
    #         stream_config = StreamConfig(
    #             name=stream_name,
    #             subjects=subjects,
    #             storage="file",  # Options: "file" or "memory"
    #             retention="limits",  # Options: "limits", "interest", "workqueue"
    #             max_msgs=100000,
    #             max_bytes=1_000_000_000,  # 1 GB
    #             max_age=72 * 3600,  # 72 hours in seconds
    #             # dup_window=120,  # 2 minutes in seconds
    #         )

    #         try:
    #             await self.js.add_stream(stream_config)
    #             logging.info(f"Stream '{stream_name}' created successfully.")
    #         except APIError as e:
    #             logging.error(f"APIError while creating stream '{stream_name}': {e}")
    #             raise
    #         except Exception as e:
    #             logging.error(f"Unexpected error while creating stream '{stream_name}': {e}")
    #             raise




        # async def setup_kv_bucket(self):
    #     bucket_name = "users"

    #     try:
    #         # Attempt to access the KV bucket
    #         # self.kv_users = await self.js.key_value(bucket=bucket_name)
    #         self.kv_users = await self.js.create_key_value(bucket=bucket_name)
    #         logging.info(f"KV bucket '{bucket_name}' accessed successfully.")
    #     except NotFoundError:
    #         # KV bucket does not exist, create it
    #         logging.info(f"KV bucket '{bucket_name}' not found. Creating it.")
    #         try:
    #             self.kv_users = await self.js.create_key_value(bucket=bucket_name)
    #             logging.info(f"KV bucket '{bucket_name}' created successfully.")
    #         except APIError as e:
    #             logging.error(f"APIError while creating KV bucket '{bucket_name}': {e}")
    #             raise
    #         except Exception as e:
    #             logging.error(f"Unexpected error while creating KV bucket '{bucket_name}': {e}")
    #             raise
    #     except APIError as e:
    #         logging.error(f"APIError while accessing KV bucket '{bucket_name}': {e}")
    #         raise
    #     except Exception as e:
    #         logging.error(f"Unexpected error while accessing KV bucket '{bucket_name}': {e}")
    #         raise