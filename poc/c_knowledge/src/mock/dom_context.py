"""
Mock domContext data for Chat CLI.

TODO: remove mock domContext data before production.
"""

import json
import random
from datetime import datetime, timedelta
from typing import Literal

# TODO: remove before production - filter options
ScreenType = Literal["cost_overview", "govern_kpi", "optimize_commitments"]
PeriodType = Literal["last_7_days", "last_30_days", "last_90_days"]
TrendType = Literal["increasing", "decreasing", "stable", "spike"]
ProviderType = Literal["AWS", "Azure", "GCP"]

PERIOD_OPTIONS: list[PeriodType] = ["last_7_days", "last_30_days", "last_90_days"]
TREND_OPTIONS: list[TrendType] = ["increasing", "decreasing", "stable", "spike"]
PROVIDER_OPTIONS: list[ProviderType] = ["AWS", "Azure", "GCP"]
SCREEN_OPTIONS: list[ScreenType] = ["cost_overview", "govern_kpi", "optimize_commitments"]

REGION_OPTIONS = {
    "AWS": ["us-east-1", "us-west-2", "ap-northeast-2", "eu-west-1"],
    "Azure": ["eastus", "westeurope", "koreacentral", "southeastasia"],
    "GCP": ["us-central1", "asia-northeast3", "europe-west1"],
}

ACCOUNT_OPTIONS = ["prod-001", "prod-002", "dev-001", "staging-001", "analytics-001"]

SERVICE_OPTIONS = {
    "AWS": ["EC2", "S3", "RDS", "Lambda", "EKS", "DynamoDB"],
    "Azure": ["Virtual Machines", "Blob Storage", "Azure SQL", "Functions", "AKS"],
    "GCP": ["Compute Engine", "Cloud Storage", "Cloud SQL", "Cloud Functions", "GKE"],
}

TEAM_OPTIONS = ["Platform Team", "Infra Team", "Data Team", "Team A", "Team B", "Team C", "Team D"]


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


def get_govern_kpi_dom_context() -> str:
    """Return a governance KPI domContext JSON string for CLI testing."""
    data = {
        "context_name": "finops kpi monitor domContext",
        "screen_type": "govern_kpi",
        "page": "/govern/kpi",
        "source_page": "/govern/finops-kpis/list",
        "title": "FinOps KPIs",
        "tabs": ["KPI Monitor", "KPI Library"],
        "active_tab": "KPI Monitor",
        "kpi_monitor_summary": {
            "current_score": {
                "period": "Aug 2025",
                "value": 64,
                "max": 100,
                "status": "Average",
                "change_vs_last_month": -7,
            },
            "pass_fail": {
                "period": "Aug 2025",
                "pass_rate": "52%",
                "pass_count": 10,
                "fail_count": 6,
                "status": "Poor",
                "change_vs_last_month": "-11%",
            },
            "three_month_avg_score": {
                "period": "Jun-Aug 2025",
                "value": 80,
                "max": 100,
                "status": "Good",
                "change_vs_last_period": 5,
            },
        },
        "score_by_team": {
            "order": "High to Low",
            "teams": [
                {"team": "Infra Team", "rank": 1, "score": 94},
                {"team": "Platform Team", "rank": 2, "score": 89},
                {"team": "Network Team", "rank": 3, "score": 78},
                {"team": "Team A", "rank": 4, "score": 67},
                {"team": "Team B", "rank": 5, "score": 60},
                {"team": "Team C", "rank": 6, "score": 48},
                {"team": "Team D", "rank": 7, "score": 30},
                {"team": "Team E", "rank": 8, "score": 25},
            ],
            "insight": (
                "Scores show a persistent gap between high performers (Infra, Platform) "
                "and low performers (Team B, Team C)."
            ),
        },
        "kpi_score_trend": {
            "range": "Jul 2025 - Jan 2025",
            "metric": "KPI Score",
            "points": [
                {"month": "Jul 2025", "score": 79, "status": "Average"},
                {"month": "Jun 2025", "score": 75, "status": "Average"},
                {"month": "May 2025", "score": 42, "status": "Poor"},
                {"month": "Apr 2025", "score": 81, "status": "Good"},
                {"month": "Mar 2025", "score": 48, "status": "Poor"},
                {"month": "Feb 2025", "score": 71, "status": "Average"},
                {"month": "Jan 2025", "score": 90, "status": "Good"},
            ],
            "legend": {
                "good": "80 and above",
                "average": "60-79",
                "poor": "Below 60",
            },
        },
        "key_insights": [
            {
                "kpi": "Tag Coverage Rate",
                "status": "Fail",
                "message": (
                    "Tag Coverage Rate 62.7% (At Risk) -> Governance score likely to decline."
                ),
                "action": "Fix in Tag Governance",
            },
            {
                "kpi": "Commitment Utilization Rate",
                "status": "Fail",
                "message": (
                    "Commitment Utilization 73% (Below Target) -> Optimization required."
                ),
                "action": "Optimize Commitments",
            },
            {
                "kpi": "Untagged Spend Percentage",
                "status": "Pass",
                "message": (
                    "Untagged spend remains low and governance compliance is in good condition."
                ),
                "action": "Review Details",
            },
        ],
        "top_weak_kpis": [
            {
                "rank": 1,
                "priority": "High",
                "name": "Tag Coverage Rate",
                "goal": "Cost Control",
                "assigned": "4 Team",
            },
            {
                "rank": 2,
                "priority": "Medium",
                "name": "Cost Allocation Coverage",
                "goal": "Cost Control",
                "assigned": "1 BU",
            },
            {
                "rank": 3,
                "priority": "Low",
                "name": "Anomaly Detection & Resolution Time",
                "goal": "Operation",
                "assigned": "3 Team",
            },
            {
                "rank": 4,
                "priority": "High",
                "name": "Commitment Utilization Rate",
                "goal": "Optimization",
                "assigned": "3 Team",
            },
            {
                "rank": 5,
                "priority": "High",
                "name": "Budget vs Actual CSP Cloud Spend",
                "goal": "Governance",
                "assigned": "1 Team",
            },
        ],
        "top_strong_kpis": [
            {
                "rank": 1,
                "priority": "High",
                "name": "Percentage of Modernization",
                "goal": "Operation",
                "assigned": "5 Team",
            },
            {
                "rank": 2,
                "priority": "High",
                "name": "Budget vs Forecasted CSP Cloud Spend",
                "goal": "Governance",
                "assigned": "1 Team",
            },
            {
                "rank": 3,
                "priority": "Low",
                "name": "Percentage of oversized instances",
                "goal": "Optimization",
                "assigned": "3 Team",
            },
            {
                "rank": 4,
                "priority": "Medium",
                "name": "Effective Savings Rate Percentage",
                "goal": "Optimization",
                "assigned": "1 BU",
            },
            {
                "rank": 5,
                "priority": "High",
                "name": "Cloud Cost Ratio",
                "goal": "Operation",
                "assigned": "1 BU",
            },
        ],
        "bu_kpi_status": {
            "period": "Aug 2025",
            "rows": [
                {
                    "status": "Fail",
                    "priority": "High",
                    "goal": "Cost Control",
                    "kpi_name": "Tag Coverage Rate",
                    "target": ">= 90%",
                    "current": "78%",
                    "assigned": "4 Team",
                },
                {
                    "status": "Pass",
                    "priority": "Major",
                    "goal": "Cost Control",
                    "kpi_name": "Untagged Spend Percentage",
                    "target": "<= 5%",
                    "current": "3.2%",
                    "assigned": "1 BU",
                },
                {
                    "status": "Pass",
                    "priority": "Minor",
                    "goal": "Cost Control",
                    "kpi_name": "Cost Allocation Coverage",
                    "target": "<= 5%",
                    "current": "3.2%",
                    "assigned": "4 Team",
                },
                {
                    "status": "Pass",
                    "priority": "Minor",
                    "goal": "Cost Control",
                    "kpi_name": "Unallocated Spend Amount",
                    "target": "<= 5%",
                    "current": "3.2%",
                    "assigned": "4 Team",
                },
            ],
        },
    }
    return json.dumps(data, ensure_ascii=False)


def get_random_dom_context() -> str:
    """Return a random domContext JSON string for CLI testing."""
    candidates = [
        get_cost_overview_dom_context,
        get_govern_kpi_dom_context,
        get_optimize_my_commitments_dom_context,
    ]
    return random.choice(candidates)()


def get_optimize_my_commitments_dom_context() -> str:
    """Return an optimize myCommitments domContext JSON string for CLI testing."""
    data = {
        "context_name": "optimize my commitments domContext",
        "screen_type": "optimize_my_commitments",
        "page": "/optimize/myCommitments",
        "title": "My Commitments",
        "tabs": ["Commitments Overview", "Recommendations", "Commitment Library"],
        "active_tab": "Commitments Overview",
        "commitment_summary": {
            "current_utilization": {
                "period": "Aug 2025",
                "value": "73%",
                "status": "Below Target",
                "change_vs_last_month": "-6%",
            },
            "coverage_rate": {
                "period": "Aug 2025",
                "value": "58%",
                "status": "Average",
                "change_vs_last_month": "+3%",
            },
            "estimated_savings": {
                "period": "Aug 2025",
                "value": "$412,000",
                "status": "Good",
                "change_vs_last_period": "+$38,000",
            },
        },
        "usage_by_team": {
            "order": "High to Low",
            "teams": [
                {"team": "Infra Team", "rank": 1, "utilization": "92%"},
                {"team": "Platform Team", "rank": 2, "utilization": "84%"},
                {"team": "Data Team", "rank": 3, "utilization": "76%"},
                {"team": "Team A", "rank": 4, "utilization": "68%"},
                {"team": "Team B", "rank": 5, "utilization": "55%"},
                {"team": "Team C", "rank": 6, "utilization": "43%"},
                {"team": "Team D", "rank": 7, "utilization": "31%"},
            ],
            "insight": (
                "Commitment utilization varies widely across teams. "
                "Team C and Team D need rightsizing and scheduling reviews."
            ),
        },
        "commitment_utilization_trend": {
            "range": "Jul 2025 - Jan 2025",
            "metric": "Utilization",
            "points": [
                {"month": "Jul 2025", "value": "79%", "status": "Average"},
                {"month": "Jun 2025", "value": "75%", "status": "Average"},
                {"month": "May 2025", "value": "64%", "status": "Poor"},
                {"month": "Apr 2025", "value": "81%", "status": "Good"},
                {"month": "Mar 2025", "value": "68%", "status": "Average"},
                {"month": "Feb 2025", "value": "71%", "status": "Average"},
                {"month": "Jan 2025", "value": "90%", "status": "Good"},
            ],
            "legend": {
                "good": "80 and above",
                "average": "60-79",
                "poor": "Below 60",
            },
        },
        "key_insights": [
            {
                "title": "Idle Reserved Capacity",
                "status": "Fail",
                "message": "Idle RI hours at 19% -> move workloads or sell unused capacity.",
                "action": "Review RI Coverage",
            },
            {
                "title": "Savings Plan Drift",
                "status": "Fail",
                "message": "Compute Savings Plan usage down to 71% -> adjust commitment level.",
                "action": "Optimize Savings Plans",
            },
            {
                "title": "Steady Coverage",
                "status": "Pass",
                "message": "Coverage rate improved and remains stable this month.",
                "action": "Review Details",
            },
        ],
        "top_underutilized_commitments": [
            {
                "rank": 1,
                "priority": "High",
                "name": "EC2 RI - m5.xlarge",
                "goal": "Utilization",
                "assigned": "Infra Team",
            },
            {
                "rank": 2,
                "priority": "Medium",
                "name": "RDS RI - db.r5.large",
                "goal": "Utilization",
                "assigned": "Platform Team",
            },
            {
                "rank": 3,
                "priority": "Low",
                "name": "Compute Savings Plan",
                "goal": "Coverage",
                "assigned": "Data Team",
            },
            {
                "rank": 4,
                "priority": "High",
                "name": "EC2 RI - c6a.2xlarge",
                "goal": "Utilization",
                "assigned": "Team B",
            },
            {
                "rank": 5,
                "priority": "High",
                "name": "Redshift RI - ra3.xlplus",
                "goal": "Utilization",
                "assigned": "Team C",
            },
        ],
        "top_effective_commitments": [
            {
                "rank": 1,
                "priority": "High",
                "name": "EC2 RI - t3.medium",
                "goal": "Utilization",
                "assigned": "Infra Team",
            },
            {
                "rank": 2,
                "priority": "High",
                "name": "Compute Savings Plan",
                "goal": "Coverage",
                "assigned": "Platform Team",
            },
            {
                "rank": 3,
                "priority": "Low",
                "name": "RDS RI - db.t4g.medium",
                "goal": "Utilization",
                "assigned": "Team A",
            },
            {
                "rank": 4,
                "priority": "Medium",
                "name": "EC2 RI - m6i.large",
                "goal": "Utilization",
                "assigned": "Data Team",
            },
            {
                "rank": 5,
                "priority": "High",
                "name": "Savings Plan - Lambda",
                "goal": "Coverage",
                "assigned": "Team D",
            },
        ],
        "commitment_table": {
            "period": "Aug 2025",
            "rows": [
                {
                    "status": "Fail",
                    "priority": "High",
                    "type": "RI",
                    "commitment_name": "EC2 m5.xlarge",
                    "target": ">= 85%",
                    "current": "62%",
                    "assigned": "Infra Team",
                },
                {
                    "status": "Pass",
                    "priority": "Major",
                    "type": "Savings Plan",
                    "commitment_name": "Compute SP",
                    "target": ">= 80%",
                    "current": "81%",
                    "assigned": "Platform Team",
                },
                {
                    "status": "Pass",
                    "priority": "Minor",
                    "type": "RI",
                    "commitment_name": "RDS db.r5.large",
                    "target": ">= 80%",
                    "current": "79%",
                    "assigned": "Platform Team",
                },
                {
                    "status": "Pass",
                    "priority": "Minor",
                    "type": "RI",
                    "commitment_name": "EC2 t3.medium",
                    "target": ">= 85%",
                    "current": "91%",
                    "assigned": "Infra Team",
                },
            ],
        },
    }
    return json.dumps(data, ensure_ascii=False)


# =============================================================================
# TODO: remove before production - 필터 기반 랜덤 데이터 생성기
# =============================================================================


def _get_trend_change(trend: TrendType) -> tuple[float, str]:
    """Return (change_percent, status) based on trend.

    TODO: remove before production.
    """
    if trend == "spike":
        change = random.uniform(50, 120)
        return change, "Critical"
    elif trend == "increasing":
        change = random.uniform(10, 35)
        return change, "Warning"
    elif trend == "decreasing":
        change = random.uniform(-35, -10)
        return change, "Good"
    else:  # stable
        change = random.uniform(-5, 5)
        return change, "Stable"


def _generate_trend_points(
    period: PeriodType,
    trend: TrendType,
    base_cost: float,
) -> list[dict]:
    """Generate trend data points based on period and trend.

    TODO: remove before production.
    """
    days_map = {"last_7_days": 7, "last_30_days": 30, "last_90_days": 90}
    num_days = days_map.get(period, 30)
    num_points = min(num_days // 7, 12) + 1

    points = []
    today = datetime.now()
    daily_cost = base_cost / num_days

    trend_multipliers = {
        "spike": lambda i, n: 1 + (i / n) * 1.5,
        "increasing": lambda i, n: 1 + (i / n) * 0.3,
        "decreasing": lambda i, n: 1 - (i / n) * 0.25,
        "stable": lambda i, n: 1 + random.uniform(-0.05, 0.05),
    }
    multiplier_fn = trend_multipliers.get(trend, trend_multipliers["stable"])

    for i in range(num_points):
        days_ago = num_days - (i * (num_days // num_points))
        date = today - timedelta(days=days_ago)
        cost = daily_cost * 7 * multiplier_fn(i, num_points)
        cost = cost * random.uniform(0.9, 1.1)  # add noise

        point = {"date": date.strftime("%Y-%m-%d"), "cost": round(cost)}
        if trend == "spike" and i >= num_points - 2:
            point["anomaly"] = True
        points.append(point)

    return points


def _generate_insights(trend: TrendType, providers: list[str]) -> list[str]:
    """Generate insights based on trend and providers.

    TODO: remove before production.
    """
    insights_map = {
        "spike": [
            "ALERT: Significant cost increase detected - immediate review required.",
            "Unexpected workload surge identified in compute resources.",
            "Auto-scaling triggered excessive instance provisioning.",
            "New resources deployed without budget approval.",
        ],
        "increasing": [
            "Costs trending upward - monitor closely.",
            "Growth in compute usage driving cost increase.",
            "Storage costs growing faster than expected.",
            "Consider implementing cost optimization measures.",
        ],
        "decreasing": [
            "Cost optimization efforts showing positive results.",
            "Reserved Instance strategy delivering savings.",
            "Right-sizing initiatives reducing waste.",
            "On track to meet cost reduction targets.",
        ],
        "stable": [
            "Costs remain stable within expected range.",
            "Spending patterns consistent with budget.",
            "No significant anomalies detected.",
            "Current optimization level maintained.",
        ],
    }

    base_insights = insights_map.get(trend, insights_map["stable"])
    selected = random.sample(base_insights, min(3, len(base_insights)))

    # Add provider-specific insight
    if len(providers) > 1:
        selected.append(f"Multi-cloud distribution: {', '.join(providers)}")
    elif providers:
        selected.append(f"Primary cloud provider: {providers[0]}")

    return selected


def generate_random_cost_overview(
    period: PeriodType | None = None,
    providers: list[ProviderType] | None = None,
    trend: TrendType | None = None,
    accounts: list[str] | None = None,
) -> str:
    """Generate random cost overview data based on filters.

    TODO: remove before production.

    Args:
        period: Time period filter. Random if None.
        providers: Cloud providers. Random if None.
        trend: Cost trend. Random if None.
        accounts: Account filter. Random if None.

    Returns:
        JSON string of cost overview domContext.
    """
    # Randomize None values
    period = period or random.choice(PERIOD_OPTIONS)
    trend = trend or random.choice(TREND_OPTIONS)
    providers = providers or random.sample(
        PROVIDER_OPTIONS, k=random.randint(1, len(PROVIDER_OPTIONS))
    )
    accounts = accounts or random.sample(
        ACCOUNT_OPTIONS, k=random.randint(1, 3)
    )

    # Generate base cost
    base_cost = random.randint(30000, 150000)
    change_percent, status = _get_trend_change(trend)

    # Distribute cost among providers
    provider_data = []
    remaining = base_cost
    for i, prov in enumerate(providers):
        if i == len(providers) - 1:
            cost = remaining
        else:
            cost = int(remaining * random.uniform(0.3, 0.6))
            remaining -= cost

        share = cost / base_cost
        prov_change = change_percent + random.uniform(-10, 10)
        provider_data.append({
            "name": prov,
            "cost": cost,
            "share": round(share, 2),
            "change": f"{prov_change:+.1f}%",
        })

    # Generate services breakdown
    primary_provider = providers[0]
    services = SERVICE_OPTIONS.get(primary_provider, SERVICE_OPTIONS["AWS"])
    service_breakdown = []
    remaining_cost = int(base_cost * 0.7)
    for i, svc in enumerate(services[:5]):
        if i == 4:
            svc_cost = remaining_cost
        else:
            svc_cost = int(remaining_cost * random.uniform(0.2, 0.4))
            remaining_cost -= svc_cost
        svc_change = change_percent + random.uniform(-15, 15)
        service_breakdown.append({
            "name": svc,
            "cost": svc_cost,
            "change": f"{svc_change:+.1f}%",
            **({"alert": True} if trend == "spike" and i < 2 else {}),
        })

    # Generate regions breakdown
    regions = REGION_OPTIONS.get(primary_provider, REGION_OPTIONS["AWS"])
    region_breakdown = [
        {"name": r, "cost": int(base_cost * random.uniform(0.1, 0.4))}
        for r in random.sample(regions, min(3, len(regions)))
    ]

    # Build data
    today = datetime.now()
    period_str = today.strftime("%Y-%m")

    data = {
        "context_name": "cost overview domContext",
        "screen_type": "cost_overview",
        "page": "/cost/overview",
        "title": "Cost Overview",
        "generated": {  # TODO: remove - for debugging
            "period": period,
            "trend": trend,
            "providers": providers,
        },
        "summary": {
            "total_cost": f"${base_cost:,}",
            "change": f"{change_percent:+.1f}%",
            "period": period_str,
            "top_service": service_breakdown[0]["name"] if service_breakdown else "N/A",
            "top_region": region_breakdown[0]["name"] if region_breakdown else "N/A",
            "status": status,
            **({"alert": f"Cost {trend} detected"} if trend in ("spike", "increasing") else {}),
        },
        "filters": {
            "period": period,
            "accounts": accounts,
            "regions": ["all"],
            "products": ["all"],
        },
        "providers": provider_data,
        "breakdown": {
            "by_service": service_breakdown,
            "by_region": region_breakdown,
        },
        "trend": {
            "granularity": "daily",
            "points": _generate_trend_points(period, trend, base_cost),
        },
        "insight_summary": _generate_insights(trend, providers),
        "top_cost_drivers": [
            {
                "name": f"{svc['name'].lower()}-{random.choice(['prod', 'dev', 'staging'])}",
                "service": svc["name"],
                "monthly_cost": svc["cost"],
                "change": svc["change"],
            }
            for svc in service_breakdown[:3]
        ],
    }

    return json.dumps(data, ensure_ascii=False)


def generate_random_govern_kpi(
    period: PeriodType | None = None,
    trend: TrendType | None = None,
) -> str:
    """Generate random governance KPI data based on filters.

    TODO: remove before production.
    """
    period = period or random.choice(PERIOD_OPTIONS)
    trend = trend or random.choice(TREND_OPTIONS)

    # Generate KPI score based on trend
    score_ranges = {
        "spike": (20, 45),
        "increasing": (55, 70),
        "decreasing": (75, 95),
        "stable": (60, 80),
    }
    score_range = score_ranges.get(trend, (50, 80))
    current_score = random.randint(*score_range)

    change_ranges = {
        "spike": (-25, -10),
        "increasing": (-10, 5),
        "decreasing": (5, 15),
        "stable": (-5, 5),
    }
    change_range = change_ranges.get(trend, (-5, 5))
    score_change = random.randint(*change_range)

    # Status based on score
    if current_score >= 80:
        status = "Good"
    elif current_score >= 60:
        status = "Average"
    else:
        status = "Poor"

    # Generate team scores
    teams = random.sample(TEAM_OPTIONS, k=min(6, len(TEAM_OPTIONS)))
    team_scores = []
    for i, team in enumerate(sorted(teams, key=lambda _: random.random())):
        base_score = current_score + random.randint(-20, 20)
        base_score = max(10, min(100, base_score))
        team_scores.append({"team": team, "rank": i + 1, "score": base_score})
    team_scores.sort(key=lambda x: x["score"], reverse=True)
    for i, ts in enumerate(team_scores):
        ts["rank"] = i + 1

    # Tag coverage based on trend
    tag_coverage_ranges = {
        "spike": (30, 50),
        "increasing": (50, 70),
        "decreasing": (75, 95),
        "stable": (60, 80),
    }
    tag_range = tag_coverage_ranges.get(trend, (50, 80))
    tag_coverage = random.randint(*tag_range)

    today = datetime.now()
    period_str = today.strftime("%b %Y")

    data = {
        "context_name": "finops kpi monitor domContext",
        "screen_type": "govern_kpi",
        "page": "/govern/kpi",
        "title": "FinOps KPIs",
        "generated": {
            "period": period,
            "trend": trend,
        },
        "tabs": ["KPI Monitor", "KPI Library"],
        "active_tab": "KPI Monitor",
        "kpi_monitor_summary": {
            "current_score": {
                "period": period_str,
                "value": current_score,
                "max": 100,
                "status": status,
                "change_vs_last_month": score_change,
            },
            "pass_fail": {
                "period": period_str,
                "pass_rate": f"{current_score}%",
                "pass_count": int(current_score / 10),
                "fail_count": 10 - int(current_score / 10),
                "status": status,
            },
        },
        "score_by_team": {
            "order": "High to Low",
            "teams": team_scores,
            "insight": f"Overall KPI trend is {trend}. Focus on bottom performers.",
        },
        "tag_compliance": {
            "overall_coverage": f"{tag_coverage}%",
            "target": "90%",
            "gap": f"{tag_coverage - 90}%",
            "status": "Pass" if tag_coverage >= 80 else "Fail",
        },
        "key_insights": [
            {
                "kpi": "Tag Coverage Rate",
                "status": "Pass" if tag_coverage >= 80 else "Fail",
                "message": f"Tag Coverage at {tag_coverage}%",
                "action": "Review tagging policy" if tag_coverage < 80 else "Maintain current level",
            },
            {
                "kpi": "KPI Score",
                "status": status,
                "message": f"Current score: {current_score}/100 ({status})",
                "action": "Review KPI details",
            },
        ],
    }

    return json.dumps(data, ensure_ascii=False)


def generate_random_commitments(
    period: PeriodType | None = None,
    trend: TrendType | None = None,
    providers: list[ProviderType] | None = None,
) -> str:
    """Generate random commitments data based on filters.

    TODO: remove before production.
    """
    period = period or random.choice(PERIOD_OPTIONS)
    trend = trend or random.choice(TREND_OPTIONS)
    providers = providers or random.sample(PROVIDER_OPTIONS, k=random.randint(1, 2))

    # Utilization based on trend
    util_ranges = {
        "spike": (25, 45),  # wastage
        "increasing": (55, 70),
        "decreasing": (80, 95),  # good utilization
        "stable": (65, 80),
    }
    util_range = util_ranges.get(trend, (60, 80))
    utilization = random.randint(*util_range)

    # Status
    if utilization >= 80:
        util_status = "Good"
    elif utilization >= 60:
        util_status = "Below Target"
    else:
        util_status = "Critical"

    change_map = {
        "spike": random.randint(-20, -10),
        "increasing": random.randint(-10, 0),
        "decreasing": random.randint(5, 15),
        "stable": random.randint(-5, 5),
    }
    util_change = change_map.get(trend, 0)

    # Generate team utilization
    teams = random.sample(TEAM_OPTIONS, k=min(6, len(TEAM_OPTIONS)))
    team_utils = []
    for i, team in enumerate(teams):
        team_util = utilization + random.randint(-25, 25)
        team_util = max(15, min(98, team_util))
        team_utils.append({"team": team, "rank": i + 1, "utilization": f"{team_util}%"})
    team_utils.sort(key=lambda x: int(x["utilization"].rstrip("%")), reverse=True)
    for i, tu in enumerate(team_utils):
        tu["rank"] = i + 1

    # Estimated savings
    base_savings = random.randint(100000, 500000)
    if trend == "decreasing":
        savings_status = "Good"
    elif trend == "spike":
        savings_status = "Poor"
    else:
        savings_status = "Average"

    # Wasted commitment (inverse of utilization)
    wasted_pct = 100 - utilization
    wasted_amount = int(base_savings * wasted_pct / 100)

    today = datetime.now()
    period_str = today.strftime("%b %Y")

    data = {
        "context_name": "optimize my commitments domContext",
        "screen_type": "optimize_my_commitments",
        "page": "/optimize/myCommitments",
        "title": "My Commitments",
        "generated": {
            "period": period,
            "trend": trend,
            "providers": providers,
        },
        "tabs": ["Commitments Overview", "Recommendations", "Commitment Library"],
        "active_tab": "Commitments Overview",
        "commitment_summary": {
            "current_utilization": {
                "period": period_str,
                "value": f"{utilization}%",
                "status": util_status,
                "change_vs_last_month": f"{util_change:+d}%",
            },
            "coverage_rate": {
                "period": period_str,
                "value": f"{random.randint(50, 80)}%",
                "status": "Average",
            },
            "estimated_savings": {
                "period": period_str,
                "value": f"${base_savings:,}",
                "status": savings_status,
            },
            "wasted_commitment": {
                "period": period_str,
                "value": f"${wasted_amount:,}",
                "status": "Critical" if wasted_pct > 30 else "Warning" if wasted_pct > 15 else "Good",
                "detail": f"{wasted_pct}% of commitments unused",
            },
        },
        "usage_by_team": {
            "order": "High to Low",
            "teams": team_utils,
            "insight": f"Commitment utilization trend: {trend}. Review underperforming teams.",
        },
        "key_insights": [
            {
                "title": "Utilization Status",
                "status": "Pass" if utilization >= 75 else "Fail",
                "message": f"Current utilization at {utilization}%",
                "action": "Review commitment allocation" if utilization < 75 else "Maintain level",
            },
            {
                "title": "Waste Analysis",
                "status": "Pass" if wasted_pct < 20 else "Fail",
                "message": f"${wasted_amount:,} in unused commitments ({wasted_pct}%)",
                "action": "Sell unused RIs" if wasted_pct > 30 else "Monitor waste levels",
            },
        ],
    }

    return json.dumps(data, ensure_ascii=False)


def generate_random_dom_context(
    screen_type: ScreenType | None = None,
    period: PeriodType | None = None,
    providers: list[ProviderType] | None = None,
    trend: TrendType | None = None,
    accounts: list[str] | None = None,
) -> str:
    """Generate random domContext data based on filters.

    All parameters are optional. If None, a random value is selected.

    TODO: remove before production.

    Args:
        screen_type: Screen type. Random if None.
        period: Time period. Random if None.
        providers: Cloud providers. Random if None.
        trend: Cost/metric trend. Random if None.
        accounts: Account filter. Random if None.

    Returns:
        JSON string of generated domContext.

    Example:
        # Fully random
        generate_random_dom_context()

        # Only specify trend
        generate_random_dom_context(trend="spike")

        # Specify multiple filters
        generate_random_dom_context(
            screen_type="cost_overview",
            period="last_30_days",
            trend="increasing",
        )
    """
    screen_type = screen_type or random.choice(SCREEN_OPTIONS)

    if screen_type == "cost_overview":
        return generate_random_cost_overview(
            period=period,
            providers=providers,
            trend=trend,
            accounts=accounts,
        )
    elif screen_type == "govern_kpi":
        return generate_random_govern_kpi(
            period=period,
            trend=trend,
        )
    elif screen_type == "optimize_commitments":
        return generate_random_commitments(
            period=period,
            trend=trend,
            providers=providers,
        )
    else:
        return generate_random_cost_overview(
            period=period,
            providers=providers,
            trend=trend,
            accounts=accounts,
        )


def get_filter_options() -> dict:
    """Return available filter options.

    TODO: remove before production.
    """
    return {
        "screen_type": SCREEN_OPTIONS,
        "period": PERIOD_OPTIONS,
        "trend": TREND_OPTIONS,
        "providers": PROVIDER_OPTIONS,
        "accounts": ACCOUNT_OPTIONS,
    }
