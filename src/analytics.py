"""Attribution and ROI analysis helpers."""
import sqlite3
import pandas as pd

MODELS=["first_touch","last_touch","linear","position_based"]

def load_frames(db_path):
    con=sqlite3.connect(db_path)
    names=["Campaign","Channel","Touchpoint","Opportunity","Order","CostRecord","AttributionResult","Lead","WebSession"]
    frames={n:pd.read_sql_query(f'SELECT * FROM "{n}"',con) for n in names}
    con.close()
    return frames

def campaign_roi(frames, model="linear"):
    camps = frames["Campaign"].copy()
    costs = frames["CostRecord"].copy()

    # Include only valid USD costs.
    valid_costs = costs[
        (costs["currency"] == "USD") &
        (costs["issue_type"].fillna("") == "")
    ]

    spend = (
        valid_costs.groupby("campaign_id", as_index=False)["amount"]
        .sum()
        .rename(columns={"amount": "spend"})
    )

    # Calculate attributed revenue for the selected model.
    attr = frames["AttributionResult"]
    attr = attr[attr["model"] == model]

    attr = (
        attr.groupby("campaign_id", as_index=False)["attributed_revenue"]
        .sum()
    )

    result = (
        camps.merge(spend, on="campaign_id", how="left")
        .merge(attr, on="campaign_id", how="left")
    )

    # Missing costs remain missing instead of being treated as zero.
    result["missing_cost_flag"] = result["spend"].isna()

    # Calculate ROI only when valid spend exists.
    result["roi"] = (
        (result["attributed_revenue"] - result["spend"]) /
        result["spend"]
    ).where(result["spend"] > 0)

    result["roas"] = (
        result["attributed_revenue"] / result["spend"]
    ).where(result["spend"] > 0)

    return result

def model_summary(frames):
    a=frames["AttributionResult"]
    return a.groupby("model",as_index=False).agg(attributed_revenue=("attributed_revenue","sum"),credited_campaigns=("campaign_id","nunique"),opportunities=("opportunity_id","nunique"))

def funnel_metrics(frames):
    return {"leads":len(frames["Lead"]),"opportunities":len(frames["Opportunity"]),
            "closed_won":int((frames["Opportunity"].stage=="closed_won").sum()),
            "orders":frames["Order"].external_order_ref.nunique(),
            "duplicate_order_refs":int(frames["Order"].external_order_ref.duplicated().sum())}

def exception_report(frames):
    t = frames["Touchpoint"]
    o = frames["Opportunity"]
    costs = frames["CostRecord"]
    campaigns = frames["Campaign"]
    orders = frames["Order"]

    # Find touchpoints that happened after an opportunity was won.
    post = t.merge(
        o[["contact_id", "closed_at"]],
        on="contact_id",
        how="inner"
    )

    post = post[
        (post["closed_at"].notna()) &
        (post["closed_at"] != "") &
        (post["occurred_at"] > post["closed_at"])
    ]

    # Identify campaigns without any cost record.
    campaigns_with_cost = set(costs["campaign_id"])
    missing_cost_campaigns = campaigns[
        ~campaigns["campaign_id"].isin(campaigns_with_cost)
    ]

    return {
        "post_conversion_touchpoints": int(post["touchpoint_id"].nunique()),
        "currency_mismatch_costs": int((costs["currency"] != "USD").sum()),
        "duplicate_revenue_rows": int(
            orders["external_order_ref"].duplicated().sum()
        ),
        "anonymous_sessions": int(
            ((frames["WebSession"]["contact_id"].isna()) |
             (frames["WebSession"]["contact_id"] == "")).sum()
        ),
        "unresolved_leads": int(
            ((frames["Lead"]["contact_id"].isna()) |
             (frames["Lead"]["contact_id"] == "")).sum()
        ),
        "campaigns_missing_cost_records": int(
            missing_cost_campaigns["campaign_id"].nunique()
        )
    }