from typing import Dict, List, Optional

def collect_tags(row: Dict) -> List[str]:
    return [
        row[f"tag{i}"] for i in range(1, 6)
        if row.get(f"tag{i}") and row[f"tag{i}"].strip()
    ]

def build_redshift_query(
    weather_condition: Optional[str] = None,
    tags: Optional[List[str]] = None,
    search_query: Optional[str] = None,
    limit: int = 10,
    randomize: bool = False
) -> str:
    select_clause = "artist, title, play_cnt, listener_cnt, tag1, tag2, tag3, tag4, tag5"
    base_query = f"SELECT {select_clause} FROM raw_data.top_tag5"
    conditions = []

    if tags:
        tag_conditions = []
        for tag in tags:
            tag_conditions.append(
                f"(LOWER(tag1) LIKE '%{tag.lower()}%' OR LOWER(tag2) LIKE '%{tag.lower()}%' OR "
                f"LOWER(tag3) LIKE '%{tag.lower()}%' OR LOWER(tag4) LIKE '%{tag.lower()}%' OR LOWER(tag5) LIKE '%{tag.lower()}%')"
            )
        conditions.append("(" + " OR ".join(tag_conditions) + ")")

    if weather_condition:
        from .constants import WEATHER_TO_TAGS_MAP
        mapped_tags = WEATHER_TO_TAGS_MAP.get(weather_condition, [])
        if mapped_tags:
            weather_tag_conditions = []
            for tag in mapped_tags:
                weather_tag_conditions.append(
                    f"(LOWER(tag1) LIKE '%{tag.lower()}%' OR LOWER(tag2) LIKE '%{tag.lower()}%' OR "
                    f"LOWER(tag3) LIKE '%{tag.lower()}%' OR LOWER(tag4) LIKE '%{tag.lower()}%' OR LOWER(tag5) LIKE '%{tag.lower()}%')"
                )
            conditions.append("(" + " OR ".join(weather_tag_conditions) + ")")

    if search_query:
        search_pattern = f"%{search_query.lower()}%"
        conditions.append(
            f"""
            (
                LOWER(artist) LIKE '{search_pattern}' OR
                LOWER(title) LIKE '{search_pattern}' OR
                LOWER(tag1) LIKE '{search_pattern}' OR
                LOWER(tag2) LIKE '{search_pattern}' OR
                LOWER(tag3) LIKE '{search_pattern}' OR
                LOWER(tag4) LIKE '{search_pattern}' OR
                LOWER(tag5) LIKE '{search_pattern}'
            )
            """
        )

    full_query = base_query
    if conditions:
        full_query += " WHERE " + " AND ".join(conditions)

    full_query += " ORDER BY " + ("RANDOM()" if randomize else "load_time DESC") + f" LIMIT {limit};"
    return full_query
