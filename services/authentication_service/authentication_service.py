import asyncio
import bcrypt
import jwt
import json
from datetime import datetime, timedelta, timezone
from nats.js.errors import NotFoundError
import os
import sys
import logging

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from common.nats_client import NATSClient
from common.models import User


logging.basicConfig(level=logging.INFO)


class AuthenticationService:
    JWT_SECRET = os.environ.get('JWT_SECRET')
    JWT_ALGORITHM = 'HS256'
    ACCESS_TOKEN_EXPIRE_MINUTES = 15
    REFRESH_TOKEN_EXPIRE_DAYS = 7
    SUBJECT_REGISTER = 'auth.register'
    SUBJECT_LOGIN = 'auth.login'
    SUBJECT_CHANGE_PASSWORD = 'auth.change_password'
    SUBJECT_REFRESH_TOKEN = 'auth.refresh_token'
    BUCKET = 'users'
    STREAM_NAME = "precepto_authentication_service"
    STREAM_LISTEN_SUBJECT = ["precepto.auth.*"]
    def __init__(self):
        # Setup self.logger
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(self.__class__.__name__)

        # Initialize NATS client
        self.nats_client = NATSClient()
        self.kv_users = None

    async def connect(self):
        try:
            await self.nats_client.connect()
            await self.nats_client.create_stream( self.STREAM_NAME, self.STREAM_LISTEN_SUBJECT)
            self.kv_users  = await self.nats_client.setup_kv_bucket(self.BUCKET)
            self.nats_client.kv_users = self.kv_users
            # await self.nats_client.delete_stream("precepto_data_service")
            # await self.nats_client.delete_stream("AUDIO_CHUNKS_STREAM")
            # await self.nats_client.delete_stream("precepto_template_service")
            # self.kv_users = self.nats_client.kv_users
        except Exception as e:
            self.logger.error(f"Failed to connect and set up NATSClient: {e}")
            return

    def create_access_token(self, user: User, expires_delta: timedelta = None):
        to_encode = {
            "exp": datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)),
            "type": "access",
            "user": {
                "id": user.id,
                "name": user.name,
                "templates": user.templates,
                "last_login": user.last_login,
                "created_at": user.created_at,
                "updated_at": user.updated_at,
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

    async def handle_user_registration(self, msg):
        self.logger.info(f"Received user registration request: {msg.data}")
        try:
            user_data = msg.data.decode()
            user_info = User.from_json(user_data)
            username = user_info.name
            password = user_info.login_pass.encode('utf-8')

            self.logger.info(f"Registering user: {username}")
            self.logger.info(f"Registering password: {password}")


            try:
                existing_user = await self.kv_users.get(username)
                response = {'status': 'error', 'message': 'User already exists.'}
                self.logger.info(f"User '{username}' already exists.")
            except NotFoundError:
                hashed_password = bcrypt.hashpw(password, bcrypt.gensalt())
                user_info.login_pass = hashed_password.decode('utf-8')
                user_info.created_at = datetime.now(timezone.utc).isoformat()
                user_info_json = user_info.to_json()
                self.logger.debug(f"UserInfo Json debug: {user_info_json} (Type: {type(user_info_json)})")
                if not isinstance(username, str) or not isinstance(user_info_json, str):
                    self.logger.error("Username or UserInfo JSON is not a string.")
                    raise TypeError("Username and UserInfo must be strings.")
                await self.kv_users.put(username, user_info_json.encode('utf-8'))
                self.logger.info("UserInfo stored successfully.")
                response = {'status': 'success', 'message': 'User registered successfully.'}
                self.logger.info(f"User '{username}' registered successfully.")

            await msg.respond(json.dumps(response).encode())
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

            entry = await self.kv_users.get(username)
            user_info = User.from_json(entry.value.decode())
            stored_hashed_password = user_info.login_pass.encode('utf-8')
            if bcrypt.checkpw(password, stored_hashed_password):
                user_info.last_login = datetime.now(timezone.utc).isoformat()
                user_info.logged_in = True
                user_info.updated_at = datetime.now(timezone.utc).isoformat()

                await self.kv_users.put(username, user_info.to_json().encode())
                access_token = self.create_access_token(user_info)
                refresh_token = self.create_refresh_token({"sub": user_info.id, "name": user_info.name})

                print(f"access_token: {access_token}")
                print(f"refresh_token: {access_token}")
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

            username = payload.get('name')

            entry = await self.kv_users.get(username)
            user_info = User.from_json(entry.value.decode())

            hashed_password = bcrypt.hashpw(new_password, bcrypt.gensalt())
            user_info.login_pass = hashed_password.decode('utf-8')
            user_info.updated_at = datetime.now(timezone.utc).isoformat()

            await self.kv_users.put(username, user_info.to_json().encode())

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
        try:
            data = msg.data.decode()
            data = json.loads(data)
            refresh_token = data.get('refresh_token')

            payload = jwt.decode(refresh_token, self.JWT_SECRET, algorithms=[self.JWT_ALGORITHM])

            if payload.get('type') != 'refresh':
                raise jwt.InvalidTokenError('Invalid token type')

            username = payload.get('name')

            entry = await self.kv_users.get(username)
            user_info = User.from_json(entry.value.decode())

            access_token = self.create_access_token(user_info)

            response = {
                'status': 'success',
                'access_token': access_token,
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
            await self.nats_client.nc.subscribe(self.SUBJECT_REGISTER, cb=self.handle_user_registration)
            self.logger.info(f"Subscribed to subject '{self.SUBJECT_REGISTER}'")
            await self.nats_client.nc.subscribe(self.SUBJECT_LOGIN, cb=self.handle_user_login)
            self.logger.info(f"Subscribed to subject '{self.SUBJECT_LOGIN}'")
            await self.nats_client.nc.subscribe(self.SUBJECT_CHANGE_PASSWORD, cb=self.handle_password_change)
            self.logger.info(f"Subscribed to subject '{self.SUBJECT_CHANGE_PASSWORD}'")
            await self.nats_client.nc.subscribe(self.SUBJECT_REFRESH_TOKEN, cb=self.handle_token_refresh)
            self.logger.info(f"Subscribed to subject '{self.SUBJECT_REFRESH_TOKEN}'")
        except Exception as e:
            self.logger.error(f"Failed to subscribe to subjects: {e}")
            return
    
    async def run(self):
        await self.connect()
        await self.subscribe()

        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await self.nats_client.close()

if __name__ == '__main__':
    auth_service = AuthenticationService()
    asyncio.run(auth_service.run())


'''
python backend/authentication_service/authentication_service.py
'''