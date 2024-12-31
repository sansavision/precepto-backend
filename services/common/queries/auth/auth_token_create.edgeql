INSERT AuthToken {
    user :=  (select User filter .id = <uuid>$user_id),
    token := <str>$token,
    expires_at := <datetime>$expires_at
};
