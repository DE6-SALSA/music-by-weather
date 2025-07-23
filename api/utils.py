from typing import Dict, List

def collect_tags(row: Dict) -> List[str]:
    return [
        row[f"tag{i}"] for i in range(1, 6)
        if row.get(f"tag{i}") and row[f"tag{i}"].strip()
    ]