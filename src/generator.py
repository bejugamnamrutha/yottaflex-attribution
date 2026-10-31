
"""Deterministic synthetic marketing-attribution data generator."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sqlite3

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


SEED = 20261022

CHANNELS = [
    "Paid Search", "Organic Search", "Social", "Email",
    "Referral", "Display", "Events", "Direct", "Offline"
]

CURRENCIES = ["USD", "INR", "EUR"]
STATUSES = ["new", "qualified", "converted", "lost"]
CREATIVE_TYPES = ["video", "image", "text", "carousel"]
AUDIENCE_TYPES = ["prospecting", "retargeting", "customer", "lookalike"]

BASE_DATE = datetime(2025, 1, 1, tzinfo=timezone.utc)


SCHEMA = """
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS Channel (
    channel_id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS Campaign (
    campaign_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    channel_id TEXT NOT NULL REFERENCES Channel(channel_id),
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    budget REAL NOT NULL CHECK(budget >= 0),
    currency TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS Creative (
    creative_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES Campaign(campaign_id),
    name TEXT NOT NULL,
    creative_type TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS Audience (
    audience_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    audience_type TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS Contact (
    contact_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    region TEXT NOT NULL,
    consent_status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS CampaignAudience (
    campaign_id TEXT REFERENCES Campaign(campaign_id),
    audience_id TEXT REFERENCES Audience(audience_id),
    PRIMARY KEY (campaign_id, audience_id)
);

CREATE TABLE IF NOT EXISTS WebSession (
    session_id TEXT PRIMARY KEY,
    contact_id TEXT REFERENCES Contact(contact_id),
    started_at TEXT NOT NULL,
    source TEXT NOT NULL,
    identity_evidence TEXT,
    issue_type TEXT
);

CREATE TABLE IF NOT EXISTS Touchpoint (
    touchpoint_id TEXT PRIMARY KEY,
    contact_id TEXT REFERENCES Contact(contact_id),
    campaign_id TEXT REFERENCES Campaign(campaign_id),
    channel_id TEXT REFERENCES Channel(channel_id),
    creative_id TEXT REFERENCES Creative(creative_id),
    audience_id TEXT REFERENCES Audience(audience_id),
    occurred_at TEXT NOT NULL,
    touch_type TEXT NOT NULL,
    is_offline INTEGER NOT NULL DEFAULT 0,
    session_id TEXT REFERENCES WebSession(session_id),
    issue_type TEXT
);

CREATE TABLE IF NOT EXISTS Lead (
    lead_id TEXT PRIMARY KEY,
    contact_id TEXT REFERENCES Contact(contact_id),
    session_id TEXT REFERENCES WebSession(session_id),
    created_at TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS Opportunity (
    opportunity_id TEXT PRIMARY KEY,
    lead_id TEXT REFERENCES Lead(lead_id),
    contact_id TEXT REFERENCES Contact(contact_id),
    created_at TEXT NOT NULL,
    closed_at TEXT,
    stage TEXT NOT NULL,
    expected_value REAL NOT NULL,
    currency TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS "Order" (
    order_id TEXT PRIMARY KEY,
    opportunity_id TEXT REFERENCES Opportunity(opportunity_id),
    order_date TEXT NOT NULL,
    revenue REAL NOT NULL,
    currency TEXT NOT NULL,
    external_order_ref TEXT NOT NULL,
    issue_type TEXT
);

CREATE TABLE IF NOT EXISTS CostRecord (
    cost_id TEXT PRIMARY KEY,
    campaign_id TEXT REFERENCES Campaign(campaign_id),
    incurred_at TEXT NOT NULL,
    amount REAL NOT NULL,
    currency TEXT NOT NULL,
    cost_type TEXT NOT NULL,
    issue_type TEXT
);

CREATE TABLE IF NOT EXISTS AttributionResult (
    result_id TEXT PRIMARY KEY,
    opportunity_id TEXT REFERENCES Opportunity(opportunity_id),
    campaign_id TEXT REFERENCES Campaign(campaign_id),
    model TEXT NOT NULL,
    credit REAL NOT NULL,
    attributed_revenue REAL NOT NULL,
    calculated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS EventHistory (
    event_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_at TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_touch_contact_time
ON Touchpoint(contact_id, occurred_at);

CREATE INDEX IF NOT EXISTS idx_opp_contact
ON Opportunity(contact_id);

CREATE INDEX IF NOT EXISTS idx_cost_campaign
ON CostRecord(campaign_id);
"""


def ident(prefix, number, width=6):
    return f"{prefix}-2026-{number:0{width}d}"


def iso(dt):
    return dt.isoformat().replace("+00:00", "Z")


def write_csv(path, rows, fields=None):
    rows = list(rows)

    if fields is None:
        fields = list(rows[0]) if rows else []

    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def sha256(path):
    digest = hashlib.sha256()

    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1 << 20), b""):
            digest.update(chunk)

    return digest.hexdigest()


def generate(
    out_dir="data",
    scale="starter",
    seed=SEED,
    config_path="config.json"
):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    default_config = {
        "scale": {
            "campaigns": 500,
            "contacts": 50000,
            "touchpoints": 200000,
            "opportunities": 10000
        },
        "starter_scale": {
            "campaigns": 20,
            "contacts": 1000,
            "touchpoints": 4000,
            "opportunities": 200
        }
    }

    config_file = Path(config_path)

    if config_file.exists():
        config = json.loads(config_file.read_text(encoding="utf-8"))
    else:
        config = default_config

    sizes = (
        config["scale"]
        if scale == "full"
        else config["starter_scale"]
    )

    campaign_count = sizes["campaigns"]
    contact_count = sizes["contacts"]
    touchpoint_count = sizes["touchpoints"]
    opportunity_count = sizes["opportunities"]

    rng = random.Random(seed)

    # ---------------------------------------------------------
    # 1. Generate master data
    # ---------------------------------------------------------

    channels = [
        {
            "channel_id": f"CH-{i + 1:03d}",
            "name": channel_name
        }
        for i, channel_name in enumerate(CHANNELS)
    ]

    audiences = [
        {
            "audience_id": f"AUD-{i + 1:03d}",
            "name": f"Audience {i + 1}",
            "audience_type": AUDIENCE_TYPES[i % len(AUDIENCE_TYPES)]
        }
        for i in range(12)
    ]

    contacts = []

    for i in range(1, contact_count + 1):
        created = BASE_DATE + timedelta(days=rng.randrange(0, 500))

        contacts.append({
            "contact_id": f"CON-{i:06d}",
            "created_at": iso(created),
            "region": rng.choice([
                "North America", "India", "Europe", "APAC"
            ]),
            "consent_status": rng.choice([
                "granted", "restricted", "unknown"
            ])
        })

    contact_by_id = {
        contact["contact_id"]: contact
        for contact in contacts
    }

    campaigns = []
    creatives = []
    campaign_audiences = []

    for i in range(1, campaign_count + 1):
        campaign_id = ident("CMP", i)
        channel = channels[(i - 1) % len(channels)]

        start = BASE_DATE + timedelta(days=rng.randrange(0, 500))
        end = start + timedelta(days=rng.randrange(30, 180))

        campaigns.append({
            "campaign_id": campaign_id,
            "name": f"{channel['name']} Campaign {i:04d}",
            "channel_id": channel["channel_id"],
            "start_date": iso(start),
            "end_date": iso(end),
            "budget": round(rng.uniform(1000, 50000), 2),
            "currency": "USD",
            "status": (
                "active"
                if end > BASE_DATE + timedelta(days=500)
                else "completed"
            )
        })

        creatives.append({
            "creative_id": f"CRE-{i:06d}",
            "campaign_id": campaign_id,
            "name": f"Creative {i:04d}",
            "creative_type": rng.choice(CREATIVE_TYPES)
        })

        campaign_audiences.append({
            "campaign_id": campaign_id,
            "audience_id": rng.choice(audiences)["audience_id"]
        })

    creative_by_campaign = {
        creative["campaign_id"]: creative["creative_id"]
        for creative in creatives
    }

    # ---------------------------------------------------------
    # 2. Generate web sessions
    # ---------------------------------------------------------

    sessions = []
    sessions_by_contact = defaultdict(list)

    session_count = max(2, contact_count // 2)

    for i in range(1, session_count + 1):
        contact = rng.choice(contacts)
        contact_id = contact["contact_id"]

        contact_created = datetime.fromisoformat(
            contact["created_at"].replace("Z", "+00:00")
        )

        session_start = BASE_DATE + timedelta(
            days=rng.randrange(0, 650)
        )

        session_start = max(session_start, contact_created)

        anonymous = (i == 1 or i % 97 == 0)

        session = {
            "session_id": ident("SES", i),
            "contact_id": "" if anonymous else contact_id,
            "started_at": iso(session_start),
            "source": rng.choice(CHANNELS),
            "identity_evidence": (
                "" if anonymous else "authenticated_login"
            ),
            "issue_type": (
                "anonymous_without_evidence" if anonymous else ""
            )
        }

        sessions.append(session)

        if not anonymous:
            sessions_by_contact[contact_id].append(
                session["session_id"]
            )

    # ---------------------------------------------------------
    # 3. Generate touchpoints
    # ---------------------------------------------------------

    touchpoints = []

    for i in range(1, touchpoint_count + 1):
        contact = rng.choice(contacts)
        contact_id = contact["contact_id"]

        campaign = rng.choice(campaigns)
        campaign_id = campaign["campaign_id"]

        contact_created = datetime.fromisoformat(
            contact["created_at"].replace("Z", "+00:00")
        )

        occurred = BASE_DATE + timedelta(
            days=rng.randrange(0, 700)
        )

        occurred = max(occurred, contact_created)

        matching_sessions = sessions_by_contact.get(
            contact_id, []
        )

        session_id = ""

        if matching_sessions and rng.random() < 0.48:
            session_id = rng.choice(matching_sessions)

        touchpoints.append({
            "touchpoint_id": (
                f"TOUCH-{contact_id}-{i:06d}"
            ),
            "contact_id": contact_id,
            "campaign_id": campaign_id,
            "channel_id": campaign["channel_id"],
            "creative_id": creative_by_campaign[campaign_id],
            "audience_id": rng.choice(audiences)["audience_id"],
            "occurred_at": iso(occurred),
            "touch_type": rng.choice([
                "impression",
                "click",
                "email_open",
                "form_submit",
                "call",
                "event_attendance"
            ]),
            "is_offline": int(rng.random() < 0.08),
            "session_id": session_id,
            "issue_type": ""
        })

    # ---------------------------------------------------------
    # 4. Generate leads, opportunities and orders
    # ---------------------------------------------------------

    leads = []
    opportunities = []
    orders = []

    for i in range(1, opportunity_count + 1):
        contact = rng.choice(contacts)
        contact_id = contact["contact_id"]

        contact_created = datetime.fromisoformat(
            contact["created_at"].replace("Z", "+00:00")
        )

        proposed_created = BASE_DATE + timedelta(
            days=rng.randrange(50, 750)
        )

        opportunity_created = max(
            proposed_created,
            contact_created
        )

        lead_created = max(
            contact_created,
            opportunity_created - timedelta(
                days=rng.randrange(1, 30)
            )
        )

        lead_id = ident("LEAD", i)
        opportunity_id = ident("OPP", i)

        # The session is optional. Leaving it blank avoids
        # linking a lead to a session belonging to another contact.
        leads.append({
            "lead_id": lead_id,
            "contact_id": contact_id,
            "session_id": "",
            "created_at": iso(lead_created),
            "status": "converted"
        })

        won = rng.random() < 0.72

        closed = None

        if won:
            closed = opportunity_created + timedelta(
                days=rng.randrange(1, 150)
            )

        expected_value = round(
            rng.uniform(500, 25000), 2
        )

        opportunities.append({
            "opportunity_id": opportunity_id,
            "lead_id": lead_id,
            "contact_id": contact_id,
            "created_at": iso(opportunity_created),
            "closed_at": iso(closed) if closed else "",
            "stage": (
                "closed_won"
                if won
                else rng.choice(["qualified", "closed_lost"])
            ),
            "expected_value": expected_value,
            "currency": "USD"
        })

        if won:
            orders.append({
                "order_id": f"ORD-{i:06d}",
                "opportunity_id": opportunity_id,
                "order_date": iso(closed),
                "revenue": expected_value,
                "currency": "USD",
                "external_order_ref": f"EXT-{i:06d}",
                "issue_type": ""
            })

    # ---------------------------------------------------------
    # 5. Generate campaign cost records
    # ---------------------------------------------------------

    costs = []

    for i, campaign in enumerate(campaigns, start=1):
        amount = round(
            campaign["budget"] * rng.uniform(0.55, 1.0),
            2
        )

        costs.append({
            "cost_id": f"COST-{i:06d}",
            "campaign_id": campaign["campaign_id"],
            "incurred_at": campaign["end_date"],
            "amount": amount,
            "currency": campaign["currency"],
            "cost_type": "media_spend",
            "issue_type": ""
        })

    # ---------------------------------------------------------
    # 6. Inject five labelled edge cases
    # ---------------------------------------------------------

    ground_truth = []

    def label(case, entity, entity_id, expected_decision):
        ground_truth.append({
            "case_id": f"GT-{len(ground_truth) + 1:04d}",
            "issue_type": case,
            "entity_type": entity,
            "entity_id": entity_id,
            "expected_decision": expected_decision
        })

    # Edge case 1: Duplicate revenue
    if orders:
        duplicate_order = dict(orders[0])

        duplicate_order["order_id"] = "ORD-ANOM-000001"
        duplicate_order["external_order_ref"] = (
            orders[0]["external_order_ref"]
        )
        duplicate_order["issue_type"] = "duplicate_revenue"

        orders.append(duplicate_order)

        label(
            "duplicate_revenue",
            "Order",
            duplicate_order["order_id"],
            "Deduplicate by external_order_ref; do not count revenue twice"
        )

    # Edge case 2: Touchpoint after conversion
    won_opportunity = next(
        (
            opportunity
            for opportunity in opportunities
            if opportunity["stage"] == "closed_won"
        ),
        None
    )

    if touchpoints and won_opportunity:
        anomaly_touch = dict(touchpoints[0])

        anomaly_touch["touchpoint_id"] = "TOUCH-ANOM-000001"
        anomaly_touch["contact_id"] = (
            won_opportunity["contact_id"]
        )

        closed_at = datetime.fromisoformat(
            won_opportunity["closed_at"].replace("Z", "+00:00")
        )

        anomaly_touch["occurred_at"] = iso(
            closed_at + timedelta(days=2)
        )

        anomaly_touch["session_id"] = ""
        anomaly_touch["issue_type"] = "post_conversion_touch"

        touchpoints.append(anomaly_touch)

        label(
            "post_conversion_touch",
            "Touchpoint",
            anomaly_touch["touchpoint_id"],
            "Exclude from attribution because it occurs after conversion"
        )

    # Edge case 3: Currency mismatch
    if costs:
        mismatch_cost = dict(costs[0])

        mismatch_cost["cost_id"] = "COST-ANOM-000001"
        mismatch_cost["currency"] = "EUR"
        mismatch_cost["issue_type"] = "currency_mismatch"

        costs.append(mismatch_cost)

        label(
            "currency_mismatch",
            "CostRecord",
            mismatch_cost["cost_id"],
            "Exclude from USD ROI until converted with an approved FX rate"
        )

    # Edge case 4: Campaign with omitted costs
    if len(costs) > 1:
        missing_campaign_id = costs[1]["campaign_id"]

        costs = [
            cost
            for cost in costs
            if cost["campaign_id"] != missing_campaign_id
        ]

        label(
            "campaign_cost_omitted",
            "Campaign",
            missing_campaign_id,
            "Flag spend as missing; do not interpret ROI as zero-cost success"
        )

    # Edge case 5: Anonymous session without identity evidence
    anonymous_session = next(
        (
            session
            for session in sessions
            if session["issue_type"] == "anonymous_without_evidence"
        ),
        None
    )

    if anonymous_session:
        anonymous_lead_id = "LEAD-ANOM-000001"

        leads.append({
            "lead_id": anonymous_lead_id,
            "contact_id": "",
            "session_id": anonymous_session["session_id"],
            "created_at": anonymous_session["started_at"],
            "status": "new"
        })

        label(
            "anonymous_session_link",
            "Lead",
            anonymous_lead_id,
            "Do not resolve identity without evidence; keep identity unresolved"
        )

    # ---------------------------------------------------------
    # 7. Generate event history
    # ---------------------------------------------------------

    events = []

    for i, opportunity in enumerate(opportunities, start=1):
        events.append({
            "event_id": f"EVT-{i:07d}",
            "entity_type": "Opportunity",
            "entity_id": opportunity["opportunity_id"],
            "event_type": "stage_changed",
            "event_at": opportunity["created_at"],
            "old_value": "new",
            "new_value": "qualified",
            "reason": "Synthetic lifecycle transition"
        })

    # ---------------------------------------------------------
    # 8. Organize source tables
    # ---------------------------------------------------------

    tables = {
        "Channel": channels,
        "Campaign": campaigns,
        "Creative": creatives,
        "Audience": audiences,
        "Contact": contacts,
        "CampaignAudience": campaign_audiences,
        "WebSession": sessions,
        "Touchpoint": touchpoints,
        "Lead": leads,
        "Opportunity": opportunities,
        "Order": orders,
        "CostRecord": costs,
        "EventHistory": events
    }

    # ---------------------------------------------------------
    # 9. Create chronological opportunity train/test split
    # ---------------------------------------------------------

    sorted_opportunities = sorted(
        opportunities,
        key=lambda row: (
            row["created_at"],
            row["opportunity_id"]
        )
    )

    split_index = int(len(sorted_opportunities) * 0.8)

    if (
        sorted_opportunities
        and split_index < len(sorted_opportunities)
    ):
        split_timestamp = sorted_opportunities[
            split_index
        ]["created_at"]

        train_opportunities = [
            row
            for row in sorted_opportunities
            if row["created_at"] < split_timestamp
        ]

        test_opportunities = [
            row
            for row in sorted_opportunities
            if row["created_at"] >= split_timestamp
        ]
    else:
        train_opportunities = sorted_opportunities
        test_opportunities = []

    write_csv(
        out / "Opportunity_train.csv",
        train_opportunities
    )

    write_csv(
        out / "Opportunity_test.csv",
        test_opportunities
    )

    train_ids = {
        row["opportunity_id"]
        for row in train_opportunities
    }

    split_rows = [
        {
            "opportunity_id": row["opportunity_id"],
            "created_at": row["created_at"],
            "split": (
                "train"
                if row["opportunity_id"] in train_ids
                else "test"
            )
        }
        for row in sorted_opportunities
    ]

    write_csv(
        out / "opportunity_split.csv",
        split_rows
    )

    if train_opportunities and test_opportunities:
        assert max(
            row["created_at"]
            for row in train_opportunities
        ) < min(
            row["created_at"]
            for row in test_opportunities
        ), "Chronological split validation failed"

    # ---------------------------------------------------------
    # 10. Calculate attribution results
    # ---------------------------------------------------------

    touches_by_contact = defaultdict(list)

    for touchpoint in touchpoints:
        touches_by_contact[
            touchpoint["contact_id"]
        ].append(touchpoint)

    results = []

    calculated_at = iso(
        datetime(2026, 10, 31, tzinfo=timezone.utc)
    )

    # Deduplicate orders using external_order_ref.
    revenue_by_opportunity = {}
    seen_external_refs = set()

    for order in orders:
        if order["currency"] != "USD":
            continue

        if order["issue_type"]:
            continue

        external_ref = order["external_order_ref"]

        if not external_ref or external_ref in seen_external_refs:
            continue

        seen_external_refs.add(external_ref)

        revenue_by_opportunity.setdefault(
            order["opportunity_id"],
            order["revenue"]
        )

    # Calculate four attribution models.
    for opportunity in opportunities:
        revenue = revenue_by_opportunity.get(
            opportunity["opportunity_id"]
        )

        if revenue is None or not opportunity["closed_at"]:
            continue

        cutoff = opportunity["closed_at"]

        eligible_touches = [
            touch
            for touch in touches_by_contact[
                opportunity["contact_id"]
            ]
            if (
                touch["occurred_at"] <= cutoff
                and not touch["issue_type"]
            )
        ]

        eligible_touches.sort(
            key=lambda row: row["occurred_at"]
        )

        if not eligible_touches:
            continue

        unique_campaigns = list(
            dict.fromkeys(
                touch["campaign_id"]
                for touch in eligible_touches
            )
        )

        model_credits = {}

        # First-touch attribution
        model_credits["first_touch"] = {
            eligible_touches[0]["campaign_id"]: 1.0
        }

        # Last-touch attribution
        model_credits["last_touch"] = {
            eligible_touches[-1]["campaign_id"]: 1.0
        }

        # Linear attribution
        model_credits["linear"] = {
            campaign_id: 1 / len(unique_campaigns)
            for campaign_id in unique_campaigns
        }

        # Position-based attribution
        if len(unique_campaigns) == 1:
            position_credits = {
                unique_campaigns[0]: 1.0
            }

        elif len(unique_campaigns) == 2:
            position_credits = {
                unique_campaigns[0]: 0.5,
                unique_campaigns[-1]: 0.5
            }

        else:
            position_credits = {
                unique_campaigns[0]: 0.4,
                unique_campaigns[-1]: 0.4
            }

            middle_credit = (
                0.2 / (len(unique_campaigns) - 2)
            )

            for campaign_id in unique_campaigns[1:-1]:
                position_credits[campaign_id] = middle_credit

        model_credits["position_based"] = position_credits

        for model, credits in model_credits.items():
            for campaign_id, credit in credits.items():
                results.append({
                    "result_id": f"ATR-{len(results) + 1:09d}",
                    "opportunity_id": opportunity["opportunity_id"],
                    "campaign_id": campaign_id,
                    "model": model,
                    "credit": round(credit, 10),
                    "attributed_revenue": round(
                        revenue * credit, 2
                    ),
                    "calculated_at": calculated_at
                })

    # ---------------------------------------------------------
    # 11. Export CSV and JSON files
    # ---------------------------------------------------------

    for table_name, rows in tables.items():
        write_csv(
            out / f"{table_name}.csv",
            rows
        )

        (out / f"{table_name}.json").write_text(
            json.dumps(
                rows,
                indent=2,
                ensure_ascii=False
            ),
            encoding="utf-8"
        )

    write_csv(
        out / "AttributionResult.csv",
        results
    )

    (out / "AttributionResult.json").write_text(
        json.dumps(
            results,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    write_csv(
        out / "ground_truth.csv",
        ground_truth
    )

    (out / "ground_truth.json").write_text(
        json.dumps(
            ground_truth,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    (out / "schema.sql").write_text(
        SCHEMA.strip() + "\n",
        encoding="utf-8"
    )

    # ---------------------------------------------------------
    # 12. Create SQLite database
    # ---------------------------------------------------------

    database_path = out / "attribution.db"

    if database_path.exists():
        database_path.unlink()

    connection = sqlite3.connect(database_path)
    connection.executescript(SCHEMA)

    for table_name, rows in tables.items():
        if not rows:
            continue

        columns = list(rows[0])

        placeholders = ",".join(
            "?" for _ in columns
        )

        column_sql = ",".join(
            f'"{column}"'
            for column in columns
        )

        insert_sql = (
            f'INSERT INTO "{table_name}" '
            f"({column_sql}) VALUES ({placeholders})"
        )

        values = [
            tuple(
                None if row.get(column, "") == ""
                else row.get(column)
                for column in columns
            )
            for row in rows
        ]

        connection.executemany(
            insert_sql,
            values
        )

    if results:
        connection.executemany(
            """
            INSERT INTO AttributionResult
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["result_id"],
                    row["opportunity_id"],
                    row["campaign_id"],
                    row["model"],
                    row["credit"],
                    row["attributed_revenue"],
                    row["calculated_at"]
                )
                for row in results
            ]
        )

    connection.commit()
    connection.close()

    # ---------------------------------------------------------
    # 13. Create manifest and validation report
    # ---------------------------------------------------------

    manifest = {
        "seed": seed,
        "scale": scale,
        "generated_at_utc": calculated_at,
        "counts": {
            table_name: len(rows)
            for table_name, rows in tables.items()
        } | {
            "AttributionResult": len(results)
        },
        "files": {}
    }

    for file_path in sorted(out.iterdir()):
        if (
            file_path.is_file()
            and file_path.name not in [
                "manifest.json",
                "validation_summary.json"
            ]
        ):
            manifest["files"][file_path.name] = sha256(
                file_path
            )

    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8"
    )

    validation_summary = validate(out)

    (out / "validation_summary.json").write_text(
        json.dumps(validation_summary, indent=2),
        encoding="utf-8"
    )

    return manifest, validation_summary


def validate(out_dir):
    out = Path(out_dir)
    checks = {}

    connection = sqlite3.connect(
        out / "attribution.db"
    )

    connection.execute("PRAGMA foreign_keys=ON")

    checks["foreign_key_violations"] = (
        connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()
    )

    # Check primary-key uniqueness.
    primary_key_checks = [
        ("Campaign", "campaign_id"),
        ("Contact", "contact_id"),
        ("Touchpoint", "touchpoint_id"),
        ("Opportunity", "opportunity_id"),
        ("Lead", "lead_id"),
        ("WebSession", "session_id"),
        ("Order", "order_id")
    ]

    for table, key in primary_key_checks:
        checks[f"{table}_duplicate_primary_keys"] = (
            connection.execute(
                f"""
                SELECT COUNT(*) - COUNT(DISTINCT {key})
                FROM "{table}"
                """
            ).fetchone()[0]
        )

    checks["touchpoints_missing_campaign"] = (
        connection.execute(
            """
            SELECT COUNT(*)
            FROM Touchpoint t
            LEFT JOIN Campaign c
                ON t.campaign_id = c.campaign_id
            WHERE c.campaign_id IS NULL
            """
        ).fetchone()[0]
    )

    checks["won_opportunities_without_order"] = (
        connection.execute(
            """
            SELECT COUNT(*)
            FROM Opportunity o
            WHERE o.stage = 'closed_won'
            AND NOT EXISTS (
                SELECT 1
                FROM "Order" r
                WHERE r.opportunity_id = o.opportunity_id
            )
            """
        ).fetchone()[0]
    )

    checks["attribution_credit_sum_errors"] = (
        connection.execute(
            """
            SELECT COUNT(*)
            FROM (
                SELECT
                    opportunity_id,
                    model,
                    ROUND(SUM(credit), 6) AS total_credit
                FROM AttributionResult
                GROUP BY opportunity_id, model
                HAVING ABS(total_credit - 1) > 0.00001
            )
            """
        ).fetchone()[0]
    )

    checks["attribution_without_eligible_touch"] = (
        connection.execute(
            """
            SELECT COUNT(*)
            FROM AttributionResult ar
            JOIN Opportunity o
                ON ar.opportunity_id = o.opportunity_id
            WHERE NOT EXISTS (
                SELECT 1
                FROM Touchpoint t
                WHERE t.contact_id = o.contact_id
                AND t.campaign_id = ar.campaign_id
                AND t.occurred_at <= o.closed_at
                AND (
                    t.issue_type IS NULL
                    OR t.issue_type = ''
                )
            )
            """
        ).fetchone()[0]
    )

    checks["post_conversion_attribution_errors"] = (
        connection.execute(
            """
            SELECT COUNT(*)
            FROM AttributionResult ar
            JOIN Opportunity o
                ON ar.opportunity_id = o.opportunity_id
            WHERE EXISTS (
                SELECT 1
                FROM Touchpoint t
                WHERE t.contact_id = o.contact_id
                AND t.campaign_id = ar.campaign_id
                AND t.occurred_at > o.closed_at
                AND t.issue_type = 'post_conversion_touch'
            )
            AND NOT EXISTS (
                SELECT 1
                FROM Touchpoint t
                WHERE t.contact_id = o.contact_id
                AND t.campaign_id = ar.campaign_id
                AND t.occurred_at <= o.closed_at
                AND (
                    t.issue_type IS NULL
                    OR t.issue_type = ''
                )
            )
            """
        ).fetchone()[0]
    )

    connection.close()

    ground_truth_path = out / "ground_truth.json"

    checks["ground_truth_cases"] = len(
        json.loads(
            ground_truth_path.read_text(
                encoding="utf-8"
            )
        )
    )

    error_suffixes = (
        "duplicate_primary_keys",
        "missing_campaign",
        "without_order",
        "sum_errors",
        "eligible_touch",
        "attribution_errors"
    )

    numeric_checks_passed = all(
        value == 0
        for key, value in checks.items()
        if key.endswith(error_suffixes)
    )

    checks["passed"] = (
        not checks["foreign_key_violations"]
        and numeric_checks_passed
        and checks["ground_truth_cases"] == 5
    )

    return checks


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate synthetic marketing attribution data."
    )

    parser.add_argument(
        "--out",
        default="data",
        help="Output directory"
    )

    parser.add_argument(
        "--scale",
        choices=["starter", "full"],
        default="starter",
        help="Dataset size"
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=SEED,
        help="Random seed for reproducible data"
    )

    parser.add_argument(
        "--config",
        default="config.json",
        help="Path to dataset configuration"
    )

    args = parser.parse_args()

    manifest, validation = generate(
        out_dir=args.out,
        scale=args.scale,
        seed=args.seed,
        config_path=args.config
    )

    print(
        json.dumps(
            {
                "manifest": manifest,
                "validation": validation
            },
            indent=2
        )
    )
