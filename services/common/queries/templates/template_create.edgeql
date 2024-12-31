# Create a new template
INSERT Template {
    name := <str>$name,
    description := <optional str>$description,
    template := <str>$template,
    is_public := <optional bool>$is_public,
    image_url := <optional str>$image_url,
    created_by := (select User filter .id = <uuid>$user_id)
};
