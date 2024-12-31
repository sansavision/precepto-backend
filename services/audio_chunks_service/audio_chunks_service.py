import asyncio
import datetime
import json
import os
import sys
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
import io
from pydub import AudioSegment
from nats.js.api import ObjectMeta

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if (parent_dir not in sys.path):
    sys.path.insert(0, parent_dir)

from common.nats_client import NATSClient
from common.edgedb_client import EdgedbClient
from common.token_utils import TokenValidator

@dataclass
class AudioChunk:
    chunk_id: str
    recording_id: str
    start_time: float
    end_time: float
    status: str
    data_path: str

class AudioChunkManager:
    CHUNKS_PATH = 'audio_chunks'
    OBJECT_STORE_NAME = 'audio-recordings'
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.nats_client = NATSClient()
        self.db = EdgedbClient()
        self.client = self.db.client
        self.token_validator = TokenValidator()
        self.chunks: Dict[str, List[AudioChunk]] = {}
        self.object_store = None
        
        if not os.path.exists(self.CHUNKS_PATH):
            os.makedirs(self.CHUNKS_PATH)

    async def connect(self):
        await self.nats_client.connect()
        
        # Initialize Object Store only
        js = self.nats_client.nc.jetstream()
        try:
            self.object_store = await js.object_store(self.OBJECT_STORE_NAME)
        except:
            self.object_store = await js.create_object_store(self.OBJECT_STORE_NAME)
        
        await self.nats_client.subscribe('audio.chunks', self.handle_chunk)
        await self.nats_client.subscribe('audio.chunks.get', self.handle_get_chunks)
        await self.nats_client.subscribe('audio.chunks.edit', self.handle_edit_chunks)
        await self.nats_client.subscribe('audio.chunks.delete', self.handle_delete_all_chunks)
        await self.nats_client.subscribe('audio.chunks.combine', self.handle_combine_chunks)

    def save_chunk(self, recording_id: str, chunk_id: str, data: bytes) -> str:
        chunk_path = os.path.join(self.CHUNKS_PATH, f"{recording_id}_{chunk_id}.webm")
        with open(chunk_path, 'wb') as f:
            f.write(data)
        return chunk_path

    def delete_chunk(self, chunk: AudioChunk) -> bool:
        try:
            if os.path.exists(chunk.data_path):
                os.remove(chunk.data_path)
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error deleting chunk file {chunk.data_path}: {e}")
            return False

    async def delete_all_chunks(self, recording_id: str):
        chunks = self.get_chunks_from_directory(recording_id)
        
        # Delete individual chunk files
        for chunk in chunks:
            try:
                if os.path.exists(chunk.data_path):
                    os.remove(chunk.data_path)
            except Exception as e:
                self.logger.error(f"Error deleting chunk file {chunk.data_path}: {e}")
        
        try:
            # Only delete from Object Store
            await self.object_store.delete(f"{recording_id}/combined.mp3")
        except Exception as e:
            self.logger.error(f"Error cleaning up MP3 for recording {recording_id}: {e}")

    async def handle_chunk(self, msg):
        self.logger.info("Received audio chunk message")
        try:
            recording_id = msg.headers.get('Recording-ID')
            chunk_id = msg.headers.get('Chunk-ID')
            self.logger.info(f"Recording ID: {recording_id}, Chunk ID: {chunk_id}")
            if not recording_id or not chunk_id:
                self.logger.error("Missing required headers")
                return

            # Save chunk data
            data_path = self.save_chunk(recording_id, chunk_id, msg.data)
            
            # Parse metadata
            metadata = json.loads(msg.headers.get('Metadata', '{}'))
            
            chunk = AudioChunk(
                chunk_id=chunk_id,
                recording_id=recording_id,
                start_time=metadata.get('start_time', 0),
                end_time=metadata.get('end_time', 0),
                status='active',
                data_path=data_path
            )

            if recording_id not in self.chunks:
                self.chunks[recording_id] = []
            self.chunks[recording_id].append(chunk)

            await self.update_chunk_metadata(chunk)

        except Exception as e:
            self.logger.error(f"Error handling chunk: {e}")

    async def handle_get_chunks(self, msg):
        try:
            data = json.loads(msg.data.decode())
            access_token = data.get('access_token')
            recording_id = data.get('recording_id')

            payload = await self.token_validator.validate_access_token(access_token)
            user_id = payload['user']['id']

            chunks = self.chunks.get(recording_id, [])
            response = []
            
            for chunk in chunks:
                if chunk.status == 'active':
                    with open(chunk.data_path, 'rb') as f:
                        chunk_data = f.read()
                    response.append({
                        'id': chunk.chunk_id,
                        'start_time': chunk.start_time,
                        'end_time': chunk.end_time,
                        'data': chunk_data
                    })

            await msg.respond(json.dumps(response).encode())

        except Exception as e:
            self.logger.error(f"Error getting chunks: {e}")
            await msg.respond(json.dumps({'error': str(e)}).encode())

    async def handle_edit_chunks(self, msg):
        try:
            data = json.loads(msg.data.decode())
            access_token = data.get('access_token')
            recording_id = data.get('recording_id')
            edit = data.get('edit')

            payload = await self.token_validator.validate_access_token(access_token)
            user_id = payload['user']['id']

            if edit['type'] == 'replace':
                await self.handle_replace(recording_id, edit)
            elif edit['type'] == 'insert':
                await self.handle_insert(recording_id, edit)
            elif edit['type'] == 'delete':
                await self.handle_delete(recording_id, edit)

            await msg.respond(json.dumps({'status': 'success'}).encode())

        except Exception as e:
            self.logger.error(f"Error handling edit: {e}")
            await msg.respond(json.dumps({'error': str(e)}).encode())

    async def handle_replace(self, recording_id: str, edit: dict):
        affected_chunks = [
            chunk for chunk in self.chunks[recording_id]
            if chunk.start_time >= edit['start_time'] and chunk.end_time <= edit['end_time']
        ]
        
        for chunk in affected_chunks:
            chunk.status = 'replaced'
            await self.update_chunk_metadata(chunk)

        new_chunk_path = self.save_chunk(recording_id, edit['chunk_id'], edit['data'])
        new_chunk = AudioChunk(
            chunk_id=edit['chunk_id'],
            recording_id=recording_id,
            start_time=edit['start_time'],
            end_time=edit['end_time'],
            status='active',
            data_path=new_chunk_path
        )
        
        self.chunks[recording_id].append(new_chunk)
        await self.update_chunk_metadata(new_chunk)

    async def handle_insert(self, recording_id: str, edit: dict):
        new_chunk_path = self.save_chunk(recording_id, edit['chunk_id'], edit['data'])
        new_chunk = AudioChunk(
            chunk_id=edit['chunk_id'],
            recording_id=recording_id,
            start_time=edit['start_time'],
            end_time=edit['end_time'],
            status='active',
            data_path=new_chunk_path
        )
        
        self.chunks[recording_id].append(new_chunk)
        await self.update_chunk_metadata(new_chunk)

    async def handle_delete(self, recording_id: str, edit: dict):
        affected_chunks = [
            chunk for chunk in self.chunks[recording_id]
            if chunk.start_time >= edit['start_time'] and chunk.end_time <= edit['end_time']
        ]
        
        for chunk in affected_chunks:
            chunk.status = 'deleted'
            await self.update_chunk_metadata(chunk)

    async def handle_delete_all_chunks(self, msg):
        try:
            data = json.loads(msg.data.decode())
            access_token = data.get('access_token')
            recording_id = data.get('recording_id')

            payload = await self.token_validator.validate_access_token(access_token)
            user_id = payload['user']['id']

            await self.delete_all_chunks(recording_id)
            await msg.respond(json.dumps({'status': 'success'}).encode())

        except Exception as e:
            self.logger.error(f"Error deleting all chunks: {e}")
            await msg.respond(json.dumps({'error': str(e)}).encode())

    def get_chunks_from_directory(self, recording_id: str) -> List[AudioChunk]:
        """Get all chunks for a recording from the filesystem."""
        chunks = []
        pattern = f"{recording_id}_*.webm"
        chunk_files = [f for f in os.listdir(self.CHUNKS_PATH) if f.startswith(recording_id)]
        
        for filename in chunk_files:
            chunk_id = filename.replace(f"{recording_id}_", "").replace(".webm", "")
            filepath = os.path.join(self.CHUNKS_PATH, filename)
            
            # Extract metadata from filename or use defaults
            chunks.append(AudioChunk(
                chunk_id=chunk_id,
                recording_id=recording_id,
                start_time=0.0,  # These could be stored in a metadata file if needed
                end_time=0.0,
                status='active',
                data_path=filepath
            ))
        
        return sorted(chunks, key=lambda x: x.chunk_id)

    async def combine_chunks(self, recording_id: str) -> bytes:
        chunks = self.get_chunks_from_directory(recording_id)
        if not chunks:
            raise ValueError(f"No chunks found for recording {recording_id}")
        
        print(f"Found {len(chunks)} chunks for recording {recording_id}")
        
        # Combine WebM chunks
        combined = AudioSegment.empty()
        for chunk in chunks:
            if os.path.exists(chunk.data_path):
                segment = AudioSegment.from_file(chunk.data_path, format="webm")
                combined += segment
                print(f"Added chunk {chunk.chunk_id}, duration: {segment.duration_seconds}")
        
        print(f"Combined audio duration: {combined.duration_seconds}")
        
        # Export as MP3
        mp3_buffer = io.BytesIO()
        combined.export(mp3_buffer, format="mp3", bitrate="192k")
        mp3_data = mp3_buffer.getvalue()
        print(f"mp3_data combined audio to MP3")
        # Store in Object Store only
        object_name = f"{recording_id}/combined.mp3"
        await self.object_store.put(
            object_name,
            io.BytesIO(mp3_data),
            meta=ObjectMeta(description=f"Combined audio for recording {recording_id}")
        )
        print(f"Stored combined audio in Object Store")
        
        return mp3_data

    async def get_combined_audio(self, recording_id: str) -> Optional[dict]:
        try:
            # Get directly from Object Store
            result = await self.object_store.get(f"{recording_id}/combined.mp3")
            return {
                "status": "completed",
                "object_name": f"{recording_id}/combined.mp3",
                "data": result.data
            }
        except Exception as e:
            self.logger.error(f"Error getting combined audio: {e}")
            return None

    async def handle_combine_chunks(self, msg):
        try:
            data = json.loads(msg.data.decode())
            access_token = data.get('access_token')
            recording_id = data.get('recording_id')
            print(f"Combining chunks for recording {recording_id}")
            payload = await self.token_validator.validate_access_token(access_token)
            user_id = payload['user']['id']

            # Combine chunks
            combined_audio = await self.combine_chunks(recording_id)
            print(f"Combined audio for recording {recording_id}")
            metadata = await self.get_combined_audio(recording_id)
            if not metadata:
                raise ValueError(f"Combined audio not found for recording {recording_id}")
            print(f"Combined audio metadata: {metadata}")
            
            # Remove binary data from response
            response_metadata = {
                'status': metadata['status'],
                'object_name': metadata['object_name']
            }
            
            await msg.respond(json.dumps({
                'status': 'success',
                'data': response_metadata
            }).encode())
            
            # Use str.encode() directly on the JSON string
            message = json.dumps({'transcription_id': recording_id})
            #  await msg.respond(json.dumps(response, cls=DataclassEncoder).encode('utf-8'))
            await self.nats_client.publish('recording.completed', message)
                
        except Exception as e:
            self.logger.error(f"Error combining chunks: {e}")
            await msg.respond(json.dumps({'error': str(e)}).encode())

    async def update_chunk_metadata(self, chunk: AudioChunk):
        # Update the chunk metadata in the database
        await self.client.execute("""
            UPDATE AudioChunk 
            FILTER .chunk_id = <str>$chunk_id
            SET {
                status := <str>$status,
                start_time := <float64>$start_time,
                end_time := <float64>$end_time
            }
        """, 
        chunk_id=chunk.chunk_id,
        status=chunk.status,
        start_time=chunk.start_time,
        end_time=chunk.end_time
        )

    async def run(self):
        await self.connect()
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await self.cleanup()

    async def cleanup(self):
        await self.nats_client.close()

if __name__ == '__main__':
    manager = AudioChunkManager()
    asyncio.run(manager.run())