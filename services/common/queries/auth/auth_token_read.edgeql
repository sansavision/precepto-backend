# Read a Token by User ID
SELECT AuthToken  {**}
FILTER .user.id = <uuid>$user_id;
