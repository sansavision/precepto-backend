# services/data_service/add_sample_data.py
import asyncio
import json
import os
import sys
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from common.nats_client import NATSClient
from common.models import TranscriptionMeta

async def add_sample_transcriptions():
    nats_client = NATSClient()
    await nats_client.connect()
    kv_transcriptions = await nats_client.setup_kv_bucket('transcriptions')

    # Sample transcription for user with id 'user1'
    transcription = TranscriptionMeta(
        id='test1',
        name='Sample Transcription',
        status='complete',
        created_by_id='user1',
        created_at='2023-10-01T10:00:00Z',
        updated_at='2023-10-01T12:00:00Z',
        duration=120.5,
        words=300,
        speakers=2,
        confidence=0.95,
        language='en',
        speaker_labels=True,
        keywords=['meeting', 'project'],
        topics=['Business', 'Technology'],
        actions=['Schedule follow-up'],
        translations=[''],
        summary='Meeting about the new project.',
        notes='Ensure all action items are completed by next week.'
    )

    await kv_transcriptions.put(transcription.id, transcription.to_json().encode('utf-8'))
    print(f"Added sample transcription with id '{transcription.id}' for user '{transcription.created_by_id}'")

    await nats_client.close()

if __name__ == '__main__':
    asyncio.run(add_sample_transcriptions())
