# Update a authtoken's details
UPDATE AuthToken
FILTER .user.id = <uuid>$user_id
SET {
    token := <str>$token,
    expires_at := <datetime>$expires_at
};