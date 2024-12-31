# Read all template by user ID
SELECT Template  {**}
FILTER .created_by.id = <uuid>$user_id;
