# Update a user's information
UPDATE User
FILTER .id = <uuid>$id
SET {
    first_name := <optional str>$first_name,
    last_name := <optional str>$last_name,
    email := <optional str>$email,
    image_url := <optional str>$image_url,
    is_admin := <optional bool>$is_admin,
    last_login := <optional datetime>$last_login,
    logged_in := <optional bool>$logged_in,
    category := <optional str>$category
};

 