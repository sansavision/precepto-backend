# Delete a auth token by user ID
DELETE AuthToken
FILTER .user.id = <uuid>$user_id
