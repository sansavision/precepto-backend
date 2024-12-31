import asyncio
import sys
import bcrypt
import jwt
import json
import logging
import os
from datetime import datetime, timedelta, timezone

from edgedb import errors

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


from common.nats_client import NATSClient

from common.edgedb_client import EdgedbClient
from common.queries.user.user_read_async_edgeql import UserReadResult as User 
from common.queries.user.user_read_by_username_async_edgeql import user_read_by_username
from common.queries.user.user_update_async_edgeql import user_update
from common.queries.user.user_create_async_edgeql import user_create
from common.queries.auth.auth_token_read_async_edgeql import auth_token_read
from common.queries.auth.auth_token_create_async_edgeql import auth_token_create
from common.queries.auth.auth_token_delete_async_edgeql import auth_token_delete 

logging.basicConfig(level=logging.INFO)

if os.environ.get('PROD_MODE',"false") == 'false':
    # only in dev
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=os.path.join(os.path.pardir,".env"))

class AuthenticationService:
    JWT_SECRET = os.environ.get('JWT_SECRET')
    JWT_ALGORITHM = 'HS256'
    # ACCESS_TOKEN_EXPIRE_MINUTES = 15
    ACCESS_TOKEN_EXPIRE_MINUTES = 60*24
    REFRESH_TOKEN_EXPIRE_DAYS = 7
    SUBJECT_REGISTER = 'auth.register'
    SUBJECT_LOGIN = 'auth.login'
    SUBJECT_CHANGE_PASSWORD = 'auth.change_password'
    SUBJECT_REFRESH_TOKEN = 'auth.refresh_token'
    STREAM_NAME = "precepto_authentication_service"
    STREAM_LISTEN_SUBJECT = ["precepto.auth.*"]

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.nats_client = NATSClient()
        self.db = EdgedbClient()
        self.client = self.db.client
        # Add refresh token collection initialization
        # self.refresh_tokens_collection = self.client.db.refresh_tokens

    async def connect(self):
        try:
            await self.nats_client.connect()
            await self.nats_client.create_stream(self.STREAM_NAME, self.STREAM_LISTEN_SUBJECT)
            self.logger.info("Connected to NATS and set up stream.")
        except Exception as e:
            self.logger.error(f"Failed to connect and set up NATSClient: {e}")
            raise

    def create_access_token(self, user: User, expires_delta: timedelta = None):
        to_encode = {
            "exp": datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)),
            "type": "access",
            "user": {
                "id": str(user.id),
                "user_name": user.user_name,
                # "templates": user.Template,
                "last_login": user.last_login.isoformat(),
                "created_at": user.created_at.isoformat(),
                "updated_at": user.updated_at.isoformat(),
                "logged_in": user.logged_in,
            }
        }
        encoded_jwt = jwt.encode(to_encode, self.JWT_SECRET, algorithm=self.JWT_ALGORITHM)
        return encoded_jwt

    def create_refresh_token(self, data: dict, expires_delta: timedelta = None):
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + (expires_delta or timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS))
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, self.JWT_SECRET, algorithm=self.JWT_ALGORITHM)
        return encoded_jwt

    async def store_refresh_token(self, user_id: str, refresh_token: str):
        expires_at = datetime.now(timezone.utc) + timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS)
        await auth_token_create(self.client, user_id=user_id, token=refresh_token, expires_at=expires_at)
        # await self.refresh_tokens_collection.insert_one({
        #     'user_id': user_id,
        #     'token': refresh_token,
        #     'created_at': datetime.now(timezone.utc),
        #     'expires_at': datetime.now(timezone.utc) + timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS)
        # })

    async def revoke_refresh_token(self, user_id: str):
        await auth_token_delete(self.client, id=user_id)
        # await self.refresh_tokens_collection.delete_one({'token': refresh_token})

    async def handle_user_registration(self, msg):
        self.logger.info(f"Received user registration request: {msg.data}")
        try:
            user_data = msg.data.decode()
            user_info = User(**json.loads(user_data))
            username = user_info.user_name
            password = user_info.login_pass.encode('utf-8')

            self.logger.info(f"Registering user: {username}")

            hashed_password = bcrypt.hashpw(password, bcrypt.gensalt())
            user_info.login_pass = hashed_password.decode('utf-8')
            user_info.created_at = datetime.now(timezone.utc)
            user_info.updated_at = user_info.created_at
            user_doc = user_info.model_dump(by_alias=True)

            # await self.users_collection.insert_one(user_doc)
            await user_create(self.client, **user_doc)
            self.logger.info(f"User '{username}' registered successfully.")
            response = {'status': 'success', 'message': 'User registered successfully.'}

        except errors.ConstraintViolationError as e:
            self.logger.info(f"User '{username}' already exists. {e}")
            response = {'status': 'error', 'message': 'User already exists.'}
        except Exception as e:
            self.logger.error(f"Error handling user registration: {e}")
            self.logger.exception("Error handling user registration")
            response = {'status': 'error', 'message': 'Internal server error.'}

        await msg.respond(json.dumps(response).encode())

    async def handle_user_login(self, msg):
        try:
            credentials = msg.data.decode()
            credentials = json.loads(credentials)
            username = credentials['username']
            password = credentials['password'].encode('utf-8')
            user_doc = await user_read_by_username(self.client, user_name=str(username) )
            # user_doc = await self.users_collection.find_one({"name": username})
            print("user doc", user_doc)
            if not user_doc:
                response = {'status': 'error', 'message': 'Invalid username or password.'}
                await msg.respond(json.dumps(response).encode())
                return

            stored_hashed_password = user_doc.login_pass.encode('utf-8')
            print("stored_hashed_password", stored_hashed_password)
            if bcrypt.checkpw(password, stored_hashed_password):
                updated_at = datetime.now(timezone.utc)

                print("after bcrypt")
                # await self.users_collection.update_one(
                #     {"name": username},
                #     {"$set": {
                #         "last_login": updated_at,
                #         "logged_in": True,
                #         "updated_at": updated_at
                #     }}
                # )
                await user_update(self.client, logged_in=True,  id=user_doc.id, last_login=updated_at, category=user_doc.category)
                print("after update")
                # user_doc['last_login'] = updated_at
                # user_doc['logged_in'] = True
                # user_doc['updated_at'] = updated_at
                # print("before user cast")
                # user = User(**user_doc) # WORKAROUND: EdgeDB returns a dict instead of a User object
                access_token = self.create_access_token(user_doc)
                refresh_token = self.create_refresh_token({"sub": str(user_doc.id), "user_name": user_doc.user_name})
                print("after tokens")
                # Store refresh token
                await self.store_refresh_token(user_id=user_doc.id, refresh_token=refresh_token)
                print("after store refresh token")
                self.logger.info(f"User '{username}' logged in successfully.")
                response = {
                    'status': 'success',
                    'message': 'Login successful.',
                    'access_token': access_token,
                    'refresh_token': refresh_token
                }
            else:
                response = {'status': 'error', 'message': 'Invalid username or password.'}
            await msg.respond(json.dumps(response).encode())
        except Exception as e:
            self.logger.error(f"Login error: {e}")
            response = {'status': 'error', 'message': 'Login failed.'}
            await msg.respond(json.dumps(response).encode())

    async def handle_password_change(self, msg):
        try:
            data = msg.data.decode()
            data = json.loads(data)
            access_token = data.get('access_token')
            new_password = data.get('new_password').encode('utf-8')

            payload = jwt.decode(access_token, self.JWT_SECRET, algorithms=[self.JWT_ALGORITHM])

            if payload.get('type') != 'access':
                raise jwt.InvalidTokenError('Invalid token type')

            username = payload.get('user', {}).get('user_name')

            if not username:
                raise jwt.InvalidTokenError('Username not found in token')

            # user_doc = await self.users_collection.find_one({"name": username})
            user_doc = await user_read_by_username(self.client, user_name=str(username) )
            if not user_doc:
                response = {'status': 'error', 'message': 'User not found.'}
                await msg.respond(json.dumps(response).encode())
                return

            hashed_password = bcrypt.hashpw(new_password, bcrypt.gensalt())
            updated_at = datetime.now(timezone.utc)
            # await self.users_collection.update_one(
            #     {"name": username},
            #     {"$set": {
            #         "login_pass": hashed_password.decode('utf-8'),
            #         "updated_at": updated_at
            #     }}
            # )
            await user_update(self.client, login_pass=hashed_password.decode('utf-8'), updated_at=updated_at, id=user_doc.id,  category=user_doc.category)
            self.logger.info(f"Password for user '{username}' changed successfully.")
            response = {'status': 'success', 'message': 'Password changed successfully.'}
            await msg.respond(json.dumps(response).encode())
        except jwt.ExpiredSignatureError:
            response = {'status': 'error', 'message': 'Access token expired.'}
            await msg.respond(json.dumps(response).encode())
        except jwt.InvalidTokenError as e:
            response = {'status': 'error', 'message': 'Invalid access token.'}
            await msg.respond(json.dumps(response).encode())
        except Exception as e:
            self.logger.error(f"Password change error: {e}")
            response = {'status': 'error', 'message': 'Password change failed.'}
            await msg.respond(json.dumps(response).encode())

    async def handle_token_refresh(self, msg):
        print("handle_token_refresh got request", msg)
        try:
            data = msg.data.decode()
            print("handle_token_refresh got request", data)
            data = json.loads(data)
            refresh_token = data.get('refresh_token')

            payload = jwt.decode(refresh_token, self.JWT_SECRET, algorithms=[self.JWT_ALGORITHM])

            if payload.get('type') != 'refresh':
                raise jwt.InvalidTokenError('Invalid token type')

            username = payload.get('user_name')

            if not username:
                raise jwt.InvalidTokenError('Username not found in token')

            # user_doc = await self.users_collection.find_one({"name": username})
            user_doc = await user_read_by_username(self.client, user_name=str(username) )
            if not user_doc:
                response = {'status': 'error', 'message': 'User not found.'}
                await msg.respond(json.dumps(response).encode())
                return

            # Verify token exists in database
            # stored_token = await self.refresh_tokens_collection.find_one({"token": refresh_token})
            stored_token = await auth_token_read(self.client, id=str(user_doc.id))
            if not stored_token:
                raise jwt.InvalidTokenError('Refresh token not found or revoked')

            # Revoke old refresh token
            await self.revoke_refresh_token(refresh_token)

            # Create new tokens
            # user = User(**user_doc)
            access_token = self.create_access_token(user_doc)
            new_refresh_token = self.create_refresh_token({"sub": str(user_doc.id), "user_name": user_doc.user_name})
            
            # Store new refresh token
            await self.store_refresh_token(str(user_doc.id), new_refresh_token)

            self.logger.info(f"Access token refreshed for user '{username}'.")
            response = {
                'status': 'success',
                'access_token': access_token,
                'refresh_token': new_refresh_token
            }
            await msg.respond(json.dumps(response).encode())
        except jwt.ExpiredSignatureError:
            response = {'status': 'error', 'message': 'Refresh token expired.'}
            await msg.respond(json.dumps(response).encode())
        except jwt.InvalidTokenError as e:
            response = {'status': 'error', 'message': 'Invalid refresh token.'}
            await msg.respond(json.dumps(response).encode())
        except Exception as e:
            self.logger.error(f"Token refresh error: {e}")
            response = {'status': 'error', 'message': 'Token refresh failed.'}
            await msg.respond(json.dumps(response).encode())

    async def subscribe(self):
        try:
            await self.nats_client.subscribe(self.SUBJECT_REGISTER, cb=self.handle_user_registration)
            self.logger.info(f"Subscribed to subject '{self.SUBJECT_REGISTER}'")
            await self.nats_client.subscribe(self.SUBJECT_LOGIN, cb=self.handle_user_login)
            self.logger.info(f"Subscribed to subject '{self.SUBJECT_LOGIN}'")
            await self.nats_client.subscribe(self.SUBJECT_CHANGE_PASSWORD, cb=self.handle_password_change)
            self.logger.info(f"Subscribed to subject '{self.SUBJECT_CHANGE_PASSWORD}'")
            await self.nats_client.subscribe(self.SUBJECT_REFRESH_TOKEN, cb=self.handle_token_refresh)
            self.logger.info(f"Subscribed to subject '{self.SUBJECT_REFRESH_TOKEN}'")
        except Exception as e:
            self.logger.error(f"Failed to subscribe to subjects: {e}")
            raise

    async def run(self):
        # self.logger.info("will setupdb")
        # await self._setup_db()
        # self.logger.info("will create index")
        # await self.db._create_users_indexes()
        self.logger.info("will connect nats")
        await self.connect()
        self.logger.info("will subscribe")
        await self.subscribe()
        self.logger.info("will run is complete")

        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Shutting down Authentication Service.")
            await self.nats_client.close()
            self.db.mongo_client.close()

if __name__ == '__main__':
    auth_service = AuthenticationService()
    asyncio.run(auth_service.run())
