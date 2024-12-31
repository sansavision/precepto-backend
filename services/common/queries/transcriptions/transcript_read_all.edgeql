# Read a transcription by ID
SELECT Transcription {**}
FILTER .created_by.id = <uuid>$user_id;

 