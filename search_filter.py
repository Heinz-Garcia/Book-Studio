def normalize_search_term(value):
    return str(value or "").strip().lower()


def matches_title_path(search_term, title, path):
    if not search_term:
        return True
    title_text = str(title or "").lower()
    path_text = str(path or "").lower()
    return (search_term in title_text) or (search_term in path_text)


def matches_tree_node(
    search_term,
    node_text,
    path_text,
    raw_title,
    content_text,
    is_fulltext,
):
    if not search_term:
        return True

    node_text = str(node_text or "").lower()
    path_text = str(path_text or "").lower()
    raw_title = str(raw_title or "").lower()
    content_text = str(content_text or "").lower()

    if is_fulltext:
        return (
            (search_term in raw_title)
            or (search_term in path_text)
            or (search_term in content_text)
        )

    return (search_term in node_text) or (search_term in path_text)


def should_include_available_item(
    search_term,
    apply_left_search,
    is_fulltext,
    title,
    path,
    content_text,
):
    if not apply_left_search or not search_term:
        return True

    if is_fulltext:
        return (
            matches_title_path(search_term, title, path)
            or (search_term in str(content_text or "").lower())
        )

    return matches_title_path(search_term, title, path)
