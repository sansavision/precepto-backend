# Update a template's details
UPDATE Template
FILTER .id = <uuid>$id
SET {
    name := <optional str>$name,
    description := <optional str>$description,
    template := <str>$template,
    is_public := <optional bool>$is_public,
    image_url := <optional str>$image_url
};
