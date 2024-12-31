INSERT User {
    user_name := <str>$user_name,
    first_name :=  <optional str>$first_name,
    last_name :=  <optional str>$last_name,
    email :=  <optional str>$email,
    image_url :=  <optional str>$image_url,
    login_pass := <str>$login_pass,
    is_admin := <bool>$is_admin,
    logged_in := <optional bool>$logged_in,
    last_login := <optional datetime>$last_login,
    category := <optional str>$category
};
