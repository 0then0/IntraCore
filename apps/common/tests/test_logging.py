from apps.common.logging import mask_sensitive_mapping


def test_mask_sensitive_mapping_masks_nested_values():
    masked = mask_sensitive_mapping(
        {
            "department_code": "engineering",
            "profile": {
                "email": "employee@example.com",
                "phone": "+79990001122",
            },
            "contacts": [
                {
                    "telegram_username": "employee",
                    "kind": "telegram",
                },
            ],
        },
    )

    assert masked == {
        "department_code": "engineering",
        "profile": {
            "email": "***",
            "phone": "***",
        },
        "contacts": [
            {
                "telegram_username": "***",
                "kind": "telegram",
            },
        ],
    }
