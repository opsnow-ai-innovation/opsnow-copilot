"""
Mock domContext data for Chat CLI.

TODO: remove mock domContext data before production.
"""

import json


def get_cost_overview_dom_context() -> str:
    """Return a cost overview domContext JSON string for CLI testing."""
    data = {
        "context_name": "cost overview domContext",
        "screen_type": "cost_overview",
        "page": "/cost/overview",
        "title": "Cost Overview",
        "summary": {
            "total_cost": "$52,340",
            "change": "+14.6%",
            "period": "2024-12",
            "top_service": "EC2",
            "top_region": "us-east-1",
        },
        "filters": {
            "period": "last_30_days",
            "accounts": ["prod-001", "dev-002"],
            "regions": ["all"],
            "products": ["all"],
        },
        "providers": [
            {"name": "AWS", "cost": 30120, "share": 0.58},
            {"name": "Azure", "cost": 13240, "share": 0.25},
            {"name": "GCP", "cost": 8980, "share": 0.17},
        ],
        "breakdown": {
            "by_service": [
                {"name": "EC2", "cost": 15000, "change": "+25%"},
                {"name": "S3", "cost": 5200, "change": "+8%"},
                {"name": "Lambda", "cost": 3100, "change": "-4%"},
            ],
            "by_region": [
                {"name": "us-east-1", "cost": 13250},
                {"name": "ap-northeast-2", "cost": 9400},
                {"name": "eu-west-1", "cost": 6800},
            ],
        },
        "trend": {
            "granularity": "daily",
            "points": [
                {"date": "2024-12-01", "cost": 1680},
                {"date": "2024-12-08", "cost": 1725},
                {"date": "2024-12-15", "cost": 1810},
                {"date": "2024-12-22", "cost": 1760},
                {"date": "2024-12-29", "cost": 1895},
            ],
        },
        "insight_summary": [
            "AWS efficiency improved after AutoSavings policy rollout.",
            "Azure spend spike due to new analytics workloads.",
            "GCP costs stable with slight storage growth.",
        ],
        "top_cost_drivers": [
            {"name": "prod-web", "service": "EC2", "monthly_cost": 6200},
            {"name": "data-lake", "service": "S3", "monthly_cost": 4100},
            {"name": "api-gateway", "service": "Lambda", "monthly_cost": 1900},
        ],
    }
    return json.dumps(data, ensure_ascii=False)
