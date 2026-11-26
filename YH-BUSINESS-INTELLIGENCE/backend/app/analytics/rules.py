from decimal import Decimal


def insights_for_overview(overview) -> list[dict[str, str]]:
    """Explainable rules over posted records; this module makes no network calls."""
    zero = Decimal("0")
    margin = (overview.net_profit_estimate / overview.revenue * 100) if overview.revenue else zero
    insights: list[dict[str, str]] = []
    if overview.revenue == 0:
        insights.append({"severity": "info", "code": "NO_POSTED_REVENUE",
                         "message": "No posted sales were found in this period; profitability is not yet measurable."})
    else:
        insights.append({
            "severity": "positive" if overview.net_profit_estimate >= 0 else "warning",
            "code": "PROFITABILITY",
            "message": f"Estimated net profit is {overview.net_profit_estimate} "
                       f"{overview.functional_currency_code} ({margin.quantize(Decimal('0.1'))}% of revenue).",
        })
    if overview.revenue and overview.expenses / overview.revenue >= Decimal("0.5"):
        insights.append({"severity": "warning", "code": "HIGH_EXPENSE_RATIO",
                         "message": "Posted expenses are at least half of revenue; review category-level spending."})
    if overview.revenue and overview.cost_of_goods_sold / overview.revenue >= Decimal("0.7"):
        insights.append({"severity": "warning", "code": "LOW_GROSS_MARGIN",
                         "message": "Posted cost of goods is at least 70% of revenue; review purchasing cost and pricing."})
    if not insights:
        insights.append({"severity": "positive", "code": "HEALTHY_PERIOD",
                         "message": "No configured rule-based warning was triggered for this period."})
    return insights
