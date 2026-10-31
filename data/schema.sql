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
