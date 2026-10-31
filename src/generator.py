"""Deterministic synthetic marketing-attribution data generator."""
from __future__ import annotations
import argparse, csv, hashlib, json, random, sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEED = 20261022
CHANNELS = ["Paid Search", "Organic Search", "Social", "Email", "Referral", "Display", "Events", "Direct", "Offline"]
CURRENCIES = ["USD", "INR", "EUR"]
STATUSES = ["new", "qualified", "converted", "lost"]
CREATIVE_TYPES = ["video", "image", "text", "carousel"]
AUDIENCE_TYPES = ["prospecting", "retargeting", "customer", "lookalike"]
BASE_DATE = datetime(2025, 1, 1, tzinfo=timezone.utc)

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS Channel(channel_id TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS Campaign(campaign_id TEXT PRIMARY KEY, name TEXT NOT NULL, channel_id TEXT NOT NULL REFERENCES Channel(channel_id), start_date TEXT NOT NULL, end_date TEXT NOT NULL, budget REAL NOT NULL CHECK(budget>=0), currency TEXT NOT NULL, status TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS Creative(creative_id TEXT PRIMARY KEY, campaign_id TEXT NOT NULL REFERENCES Campaign(campaign_id), name TEXT NOT NULL, creative_type TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS Audience(audience_id TEXT PRIMARY KEY, name TEXT NOT NULL, audience_type TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS Contact(contact_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, region TEXT NOT NULL, consent_status TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS CampaignAudience(campaign_id TEXT REFERENCES Campaign(campaign_id), audience_id TEXT REFERENCES Audience(audience_id), PRIMARY KEY(campaign_id,audience_id));
CREATE TABLE IF NOT EXISTS Touchpoint(touchpoint_id TEXT PRIMARY KEY, contact_id TEXT REFERENCES Contact(contact_id), campaign_id TEXT REFERENCES Campaign(campaign_id), channel_id TEXT REFERENCES Channel(channel_id), creative_id TEXT REFERENCES Creative(creative_id), audience_id TEXT REFERENCES Audience(audience_id), occurred_at TEXT NOT NULL, touch_type TEXT NOT NULL, is_offline INTEGER NOT NULL DEFAULT 0, session_id TEXT, issue_type TEXT);
CREATE TABLE IF NOT EXISTS WebSession(session_id TEXT PRIMARY KEY, contact_id TEXT REFERENCES Contact(contact_id), started_at TEXT NOT NULL, source TEXT NOT NULL, identity_evidence TEXT, issue_type TEXT);
CREATE TABLE IF NOT EXISTS Lead(lead_id TEXT PRIMARY KEY, contact_id TEXT REFERENCES Contact(contact_id), session_id TEXT REFERENCES WebSession(session_id), created_at TEXT NOT NULL, status TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS Opportunity(opportunity_id TEXT PRIMARY KEY, lead_id TEXT REFERENCES Lead(lead_id), contact_id TEXT REFERENCES Contact(contact_id), created_at TEXT NOT NULL, closed_at TEXT, stage TEXT NOT NULL, expected_value REAL NOT NULL, currency TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS "Order"(order_id TEXT PRIMARY KEY, opportunity_id TEXT REFERENCES Opportunity(opportunity_id), order_date TEXT NOT NULL, revenue REAL NOT NULL, currency TEXT NOT NULL, external_order_ref TEXT NOT NULL, issue_type TEXT);
CREATE TABLE IF NOT EXISTS CostRecord(cost_id TEXT PRIMARY KEY, campaign_id TEXT REFERENCES Campaign(campaign_id), incurred_at TEXT NOT NULL, amount REAL NOT NULL, currency TEXT NOT NULL, cost_type TEXT NOT NULL, issue_type TEXT);
CREATE TABLE IF NOT EXISTS AttributionResult(result_id TEXT PRIMARY KEY, opportunity_id TEXT REFERENCES Opportunity(opportunity_id), campaign_id TEXT REFERENCES Campaign(campaign_id), model TEXT NOT NULL, credit REAL NOT NULL, attributed_revenue REAL NOT NULL, calculated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS EventHistory(event_id TEXT PRIMARY KEY, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, event_type TEXT NOT NULL, event_at TEXT NOT NULL, old_value TEXT, new_value TEXT, reason TEXT);
CREATE INDEX IF NOT EXISTS idx_touch_contact_time ON Touchpoint(contact_id,occurred_at);
CREATE INDEX IF NOT EXISTS idx_opp_contact ON Opportunity(contact_id);
CREATE INDEX IF NOT EXISTS idx_cost_campaign ON CostRecord(campaign_id);
"""

def ident(prefix, n, width=6): return f"{prefix}-2026-{n:0{width}d}"
def iso(dt): return dt.isoformat().replace("+00:00","Z")
def write_csv(path, rows, fields=None):
    rows=list(rows)
    if not fields: fields=list(rows[0]) if rows else []
    with open(path,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
def sha256(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda:f.read(1<<20),b""): h.update(chunk)
    return h.hexdigest()

def generate(out_dir="data", scale="starter", seed=SEED, config_path="config.json"):
    out=Path(out_dir); out.mkdir(parents=True,exist_ok=True)
    cfg=json.loads(Path(config_path).read_text()) if Path(config_path).exists() else {
      "scale":{"campaigns":500,"contacts":50000,"touchpoints":200000,"opportunities":10000},
      "starter_scale":{"campaigns":20,"contacts":1000,"touchpoints":4000,"opportunities":200}}
    sizes=cfg["scale"] if scale=="full" else cfg["starter_scale"]
    nc,ncontacts,nt,nopp=(sizes[k] for k in ["campaigns","contacts","touchpoints","opportunities"])
    rng=random.Random(seed)
    channels=[{"channel_id":f"CH-{i+1:03d}","name":x} for i,x in enumerate(CHANNELS)]
    audiences=[{"audience_id":f"AUD-{i+1:03d}","name":f"Audience {i+1}","audience_type":AUDIENCE_TYPES[i%4]} for i in range(12)]
    contacts=[{"contact_id":f"CON-{i+1:06d}","created_at":iso(BASE_DATE+timedelta(days=rng.randrange(0,500))),"region":rng.choice(["North America","India","Europe","APAC"]),"consent_status":rng.choice(["granted","restricted","unknown"])} for i in range(ncontacts)]
    campaigns=[]; creatives=[]; campaud=[]; channel_by_id={x["channel_id"]:x for x in channels}
    for i in range(1,nc+1):
        cid=ident("CMP",i); ch=channels[(i-1)%len(channels)]
        start=BASE_DATE+timedelta(days=rng.randrange(0,500)); end=start+timedelta(days=rng.randrange(30,180))
        campaigns.append({"campaign_id":cid,"name":f"{ch['name']} Campaign {i:04d}","channel_id":ch["channel_id"],"start_date":iso(start),"end_date":iso(end),"budget":round(rng.uniform(1000,50000),2),"currency":"USD","status":"active" if end>BASE_DATE+timedelta(days=500) else "completed"})
        crid=f"CRE-{i:06d}"; creatives.append({"creative_id":crid,"campaign_id":cid,"name":f"Creative {i:04d}","creative_type":rng.choice(CREATIVE_TYPES)})
        campaud.append({"campaign_id":cid,"audience_id":rng.choice(audiences)["audience_id"]})
    contact_ids=[x["contact_id"] for x in contacts]; campaign_ids=[x["campaign_id"] for x in campaigns]
    creative_by_campaign={x["campaign_id"]:x["creative_id"] for x in creatives}
    touchpoints=[]; sessions=[]; leads=[]; opps=[]; orders=[]; costs=[]; events=[]
    # Stable, explicit sessions and lead records. Most contacts have one session; some are anonymous.
    for i in range(1,max(2, ncontacts//2)+1):
        c=rng.choice(contacts); sid=ident("SES",i); start=BASE_DATE+timedelta(days=rng.randrange(0,650))
        anon=(i%97==0)
        sessions.append({"session_id":sid,"contact_id":"" if anon else c["contact_id"],"started_at":iso(start),"source":rng.choice(CHANNELS),"identity_evidence":"" if anon else "authenticated_login","issue_type":"anonymous_without_evidence" if anon else ""})
    session_ids=[s["session_id"] for s in sessions]
    for i in range(1,nt+1):
        c=rng.choice(contacts); camp=rng.choice(campaigns); dt=BASE_DATE+timedelta(days=rng.randrange(0,700))
        sid=rng.choice(session_ids) if rng.random()<0.48 else ""
        touchpoints.append({"touchpoint_id":f"TOUCH-{c['contact_id']}-{i:06d}","contact_id":c["contact_id"],"campaign_id":camp["campaign_id"],"channel_id":camp["channel_id"],"creative_id":creative_by_campaign[camp["campaign_id"]],"audience_id":rng.choice(audiences)["audience_id"],"occurred_at":iso(dt),"touch_type":rng.choice(["impression","click","email_open","form_submit","call","event_attendance"]),"is_offline":int(rng.random()<0.08),"session_id":sid,"issue_type":""})
    # Assign opportunities to contacts; conversion timestamp follows lead creation.
    for i in range(1,nopp+1):
        c=rng.choice(contacts); created=BASE_DATE+timedelta(days=rng.randrange(50,750))
        lid=ident("LEAD",i); oid=ident("OPP",i); sid=rng.choice(sessions)["session_id"]
        leads.append({"lead_id":lid,"contact_id":c["contact_id"],"session_id":sid,"created_at":iso(created-timedelta(days=rng.randrange(1,30))),"status":"converted"})
        won=rng.random()<0.72; closed=created+timedelta(days=rng.randrange(1,150)) if won else None
        value=round(rng.uniform(500,25000),2)
        opps.append({"opportunity_id":oid,"lead_id":lid,"contact_id":c["contact_id"],"created_at":iso(created),"closed_at":iso(closed) if closed else "","stage":"closed_won" if won else rng.choice(["qualified","closed_lost"]),"expected_value":value,"currency":"USD"})
        if won:
            orders.append({"order_id":f"ORD-{i:06d}","opportunity_id":oid,"order_date":iso(closed),"revenue":value,"currency":"USD","external_order_ref":f"EXT-{i:06d}","issue_type":""})
    # Campaign spend records; total costs derived from budget fraction.
    for i,c in enumerate(campaigns,1):
        amount=round(c["budget"]*rng.uniform(.55,1.0),2)
        costs.append({"cost_id":f"COST-{i:06d}","campaign_id":c["campaign_id"],"incurred_at":c["end_date"],"amount":amount,"currency":c["currency"],"cost_type":"media_spend","issue_type":""})
    ground=[]
    def label(case, entity, eid, detail):
        ground.append({"case_id":f"GT-{len(ground)+1:04d}","issue_type":case,"entity_type":entity,"entity_id":eid,"expected_decision":detail})
    # Edge cases are explicit and traceable.
    if orders:
        dup=dict(orders[0]); dup["order_id"]="ORD-ANOM-000001"; dup["external_order_ref"]=orders[0]["external_order_ref"]; dup["issue_type"]="duplicate_revenue"
        orders.append(dup); label("duplicate_revenue","Order",dup["order_id"],"Deduplicate by external_order_ref; do not count revenue twice")
    if touchpoints and opps:
        t=dict(touchpoints[0]); t["touchpoint_id"]="TOUCH-ANOM-000001"; t["contact_id"]=opps[0]["contact_id"]; t["occurred_at"]=iso(datetime.fromisoformat(opps[0]["closed_at"].replace("Z","+00:00"))+timedelta(days=2)) if opps[0]["closed_at"] else iso(BASE_DATE+timedelta(days=900)); t["issue_type"]="post_conversion_touch"
        touchpoints.append(t); label("post_conversion_touch","Touchpoint",t["touchpoint_id"],"Exclude from attribution because it occurs after conversion")
    if costs:
        c=dict(costs[0]); c["cost_id"]="COST-ANOM-000001"; c["currency"]="EUR"; c["issue_type"]="currency_mismatch"; costs.append(c); label("currency_mismatch","CostRecord",c["cost_id"],"Exclude from USD ROI until converted with an approved FX rate")
        missing_campaign_id=costs[1]["campaign_id"] if len(costs)>1 else costs[0]["campaign_id"]
        costs=[x for x in costs if x["campaign_id"]!=missing_campaign_id]
        label("campaign_cost_omitted","Campaign",missing_campaign_id,"Campaign has no cost record; flag spend as missing and do not interpret ROI as zero-cost success")
    if sessions:
        anon=next((s for s in sessions if s["issue_type"]),None)
        if anon:
            # Explicitly create a lead referencing anonymous session with no contact proof.
            lid=f"LEAD-ANOM-000001"
            leads.append({"lead_id":lid,"contact_id":"","session_id":anon["session_id"],"created_at":anon["started_at"],"status":"new"})
            label("anonymous_session_link","Lead",lid,"Do not resolve identity without evidence; keep identity link unresolved")
        # Event history: append-only lifecycle examples.
    for i, o in enumerate(opps, 1):
        events.append({
            "event_id": f"EVT-{i:07d}",
            "entity_type": "Opportunity",
            "entity_id": o["opportunity_id"],
            "event_type": "stage_changed",
            "event_at": o["created_at"],
            "old_value": "new",
            "new_value": "qualified",
            "reason": "Synthetic lifecycle transition"
        })

    tables = {
        "Channel": channels,
        "Campaign": campaigns,
        "Creative": creatives,
        "Audience": audiences,
        "Contact": contacts,
        "CampaignAudience": campaud,
        "Touchpoint": touchpoints,
        "WebSession": sessions,
        "Lead": leads,
        "Opportunity": opps,
        "Order": orders,
        "CostRecord": costs,
        "EventHistory": events
    }
    # Chronological 80/20 split based on opportunity creation date.
    sorted_opps = sorted(
        opps,
        key=lambda x: (x["created_at"], x["opportunity_id"])
    )

    split_index = int(len(sorted_opps) * 0.8)

    # Use a timestamp boundary so identical timestamps stay together.
    if sorted_opps and split_index < len(sorted_opps):
        split_timestamp = sorted_opps[split_index]["created_at"]

        train_opps = [
            o for o in sorted_opps
            if o["created_at"] < split_timestamp
        ]

        test_opps = [
            o for o in sorted_opps
            if o["created_at"] >= split_timestamp
        ]
    else:
        train_opps = sorted_opps
        test_opps = []

    # Export chronological training and testing datasets.
    write_csv(out / "Opportunity_train.csv", train_opps)
    write_csv(out / "Opportunity_test.csv", test_opps)

    # Export a record of each opportunity's split assignment.
    train_ids = {o["opportunity_id"] for o in train_opps}

    split_rows = [
        {
            "opportunity_id": o["opportunity_id"],
            "created_at": o["created_at"],
            "split": "train" if o["opportunity_id"] in train_ids else "test"
        }
        for o in sorted_opps
    ]

    write_csv(out / "opportunity_split.csv", split_rows)

    # Validate chronological ordering.
    if train_opps and test_opps:
        assert max(o["created_at"] for o in train_opps) < min(
            o["created_at"] for o in test_opps
        ), "Chronological split validation failed"
    # Export CSVs and a JSON bundle.
    for name,rows in tables.items(): write_csv(out/f"{name}.csv",rows)
    (out/"ground_truth.json").write_text(json.dumps(ground,indent=2))
        # Attribution models, based on eligible touches up to won order date.
    by_contact = defaultdict(list)

    for t in touchpoints:
        by_contact[t["contact_id"]].append(t)

    results = []
    calc = iso(datetime(2026, 10, 31, tzinfo=timezone.utc))

    # Deduplicate orders using external_order_ref.
    revenue_by_opp = {}
    seen_external_order_refs = set()

    for order in orders:
        if order["currency"] != "USD":
            continue

        if order["issue_type"]:
            continue

        external_ref = order["external_order_ref"]

        if not external_ref or external_ref in seen_external_order_refs:
            continue

        seen_external_order_refs.add(external_ref)

        revenue_by_opp.setdefault(
            order["opportunity_id"],
            order["revenue"]
        )

    # Apply the four attribution models.
    for o in opps:
        rev = revenue_by_opp.get(o["opportunity_id"])

        if rev is None or not o["closed_at"]:
            continue

        cutoff = o["closed_at"]

        eligible = [
            t for t in by_contact[o["contact_id"]]
            if t["occurred_at"] <= cutoff and not t["issue_type"]
        ]

        eligible.sort(key=lambda x: x["occurred_at"])

        if not eligible:
            continue

        model_credits = {}
        model_credits["first_touch"] = {eligible[0]["campaign_id"]: 1.0}
        model_credits["last_touch"] = {eligible[-1]["campaign_id"]: 1.0}

        unique = list(dict.fromkeys(t["campaign_id"] for t in eligible))
        model_credits["linear"] = {
            cid: 1 / len(unique) for cid in unique
        }

        if len(unique) == 1:
            pos = {unique[0]: 1.0}
        elif len(unique) == 2:
            pos = {unique[0]: 0.5, unique[-1]: 0.5}
        else:
            pos = {unique[0]: 0.4, unique[-1]: 0.4}
            for cid in unique[1:-1]:
                pos[cid] = 0.2 / (len(unique) - 2)

        model_credits["position_based"] = pos

        for model, credits in model_credits.items():
            for cid, credit in credits.items():
                results.append({
                    "result_id": f"ATR-{len(results)+1:09d}",
                    "opportunity_id": o["opportunity_id"],
                    "campaign_id": cid,
                    "model": model,
                    "credit": round(credit, 10),
                    "attributed_revenue": round(rev * credit, 2),
                    "calculated_at": calc
                })

    write_csv(out / "AttributionResult.csv", results)
    # SQL seed database.
    db=out/"attribution.db"
    if db.exists(): db.unlink()
    con=sqlite3.connect(db); con.executescript(SCHEMA)
    mapping={"Channel":"channel_id","Campaign":"campaign_id","Creative":"creative_id","Audience":"audience_id","Contact":"contact_id","CampaignAudience":None,"Touchpoint":"touchpoint_id","WebSession":"session_id","Lead":"lead_id","Opportunity":"opportunity_id","Order":"order_id","CostRecord":"cost_id","EventHistory":"event_id"}
    for table,rows in tables.items():
        if not rows: continue
        cols=list(rows[0]); placeholders=",".join("?" for _ in cols)
        for r in rows:
            vals=[None if r.get(k,"")=="" else r.get(k) for k in cols]
            con.execute(f'INSERT INTO "{table}" ({",".join(cols)}) VALUES ({placeholders})',vals)
    for r in results:
        con.execute("INSERT INTO AttributionResult VALUES (?,?,?,?,?,?,?)",tuple(r.values()))
    con.commit(); con.close()
    # Manifest/checksums and validation report.
    manifest={"seed":seed,"scale":scale,"generated_at_utc":calc,"counts":{k:len(v) for k,v in tables.items()}|{"AttributionResult":len(results)},"files":{}}
    for p in sorted(out.iterdir()):
        if p.is_file() and p.name not in ["manifest.json","validation_summary.json"]: manifest["files"][p.name]=sha256(p)
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2))
    summary=validate(out)
    (out/"validation_summary.json").write_text(json.dumps(summary,indent=2))
    return manifest,summary

def validate(out_dir):
    out=Path(out_dir); checks={}
    con=sqlite3.connect(out/"attribution.db"); con.execute("PRAGMA foreign_keys=ON")
    checks["foreign_key_violations"]=con.execute("PRAGMA foreign_key_check").fetchall()
    for table,key in [("Campaign","campaign_id"),("Contact","contact_id"),("Touchpoint","touchpoint_id"),("Opportunity","opportunity_id"),("Lead","lead_id"),("WebSession","session_id"),("Order","order_id")]:
        checks[f"{table}_duplicate_primary_keys"]=con.execute(f'SELECT COUNT(*)-COUNT(DISTINCT {key}) FROM "{table}"').fetchone()[0]
    checks["touchpoints_missing_campaign"]=con.execute("SELECT COUNT(*) FROM Touchpoint t LEFT JOIN Campaign c USING(campaign_id) WHERE c.campaign_id IS NULL").fetchone()[0]
    checks["won_opportunities_without_order"] = con.execute(
    'SELECT COUNT(*) FROM Opportunity o '
    'WHERE stage = "closed_won" '
    'AND NOT EXISTS (SELECT 1 FROM "Order" r '
    'WHERE r.opportunity_id = o.opportunity_id)'
).fetchone()[0]
    checks["attribution_credit_sum_errors"]=con.execute("""SELECT COUNT(*) FROM (SELECT opportunity_id,model,ROUND(SUM(credit),6) s FROM AttributionResult GROUP BY opportunity_id,model HAVING ABS(s-1)>0.00001)""").fetchone()[0]
    checks["attribution_without_eligible_touch"]=con.execute("""SELECT COUNT(*) FROM AttributionResult ar JOIN Opportunity o USING(opportunity_id) WHERE NOT EXISTS (SELECT 1 FROM Touchpoint t WHERE t.contact_id=o.contact_id AND t.campaign_id=ar.campaign_id AND t.occurred_at<=o.closed_at AND (t.issue_type IS NULL OR t.issue_type=''))""").fetchone()[0]
    con.close()
    checks["ground_truth_cases"]=len(json.loads((out/"ground_truth.json").read_text()))
    checks["passed"] = (
    not checks["foreign_key_violations"]
    and all(
        v == 0
        for k, v in checks.items()
        if k.endswith((
            "duplicate_primary_keys",
            "missing_campaign",
            "without_order",
            "sum_errors",
            "after_conversion",
            "eligible_touch"
        ))
    )
)
    return checks

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--out",default="data"); p.add_argument("--scale",choices=["starter","full"],default="starter"); p.add_argument("--seed",type=int,default=SEED); p.add_argument("--config",default="config.json")
    a=p.parse_args(); m,v=generate(a.out,a.scale,a.seed,a.config); print(json.dumps({"manifest":m,"validation":v},indent=2))
