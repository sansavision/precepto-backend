import asyncio
import dataclasses
import json
import os
import sys
import logging
import uuid
from edgedb import create_async_client

from datetime import datetime
from uuid import UUID
from typing import Any

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

logging.basicConfig(level=logging.INFO)

class DataclassEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        # Check if it's a dataclass
        if dataclasses.is_dataclass(obj):
            return dataclasses.asdict(obj)
        # Check if it's a datetime
        if isinstance(obj, datetime):
            return obj.isoformat()
        
        if isinstance(obj, uuid.UUID):
            return str(obj)
        
        if type(obj).__name__ == "DerivedEnumValue":
            return str(obj.value)  # or obj.name, depending on your needs
        # Let the default encoder handle everything else
        return super().default(obj)

class EdgedbClient:
    def __init__(self, loop=None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.client = self.create_client()

    def create_client(self):
        try:
            client = create_async_client(port = 5656, user = "edgedb", database = "precepto", timeout = 60, tls_security="insecure")
            self.logger.info(f"Succesfully created db client: {client}")
            return client
        except Exception as e:
            self.logger.error(f"Error creating client: {e}")




    def edgedb_to_dict_internal(self,obj: Any) -> dict:
        """Convert EdgeDB object to a dictionary."""
        result = {}
        for key in dir(obj):
            if not key.startswith('_'):  # Skip internal attributes
                value = getattr(obj, key)
                # Handle specific types
                if isinstance(value, datetime):
                    value = value.isoformat()
                elif isinstance(value, UUID):
                    value = str(value)
                elif hasattr(value, '__iter__') and not isinstance(value, (str, bytes)):
                    value = [self.edgedb_to_dict(item) if hasattr(item, '__dict__') else item for item in value]
                result[key] = value
        return result

    def serialize_edgedb_to_json_dict(self,obj: Any) -> dict:
        """Convert edge obj object to JSON-serializable dictionary."""
        edgedb_dict = self.edgedb_to_dict_internal(obj)
        return edgedb_dict
    

    def serialized_edgedb_json_dict_to_json(self,obj: Any) -> str:
        """Returns a edge object to JSON-serializalized."""
        edgedb_str = json.dumps(self.serialize_edgedb_to_json_dict(obj))
        return edgedb_str

    # async def test_db(self):
    #     try:
    #         await self.client.query('SELECT {1, 2, 3}')
    #         self.logger.info("Successfully tested db connection.")
    #     except Exception as e:
    #         self.logger.error(f"Error testing db connection: {e}")


# if __name__ == "__main__":
#     client = EdgedbClient()
#     asyncio.run(client.test_db())