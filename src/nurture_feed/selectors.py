def get_selector_config() -> dict[str, list[str]]:
    return {
        "item_nodes": [
            ".email-list .email-list-item.announcement-body",
            ".email-list-item.announcement-body",
            ".email-list .email-list-item",
        ],
        "title_nodes": [
            "a.email-list-detail .from",
            ".email-list-detail .from",
            "a.email-list-detail",
        ],
        "description_nodes": [
            "a.email-list-detail p.msg",
            ".email-list-detail p.msg",
            "p.msg",
        ],
        "date_nodes": [
            "a.email-list-detail .text-muted",
            ".email-list-detail .text-muted",
            ".text-muted",
        ],
    }

