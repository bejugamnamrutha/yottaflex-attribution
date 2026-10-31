# YottaFlex.ai – Marketing Attribution Data Dictionary

## 1. Overview

This document describes the schema, fields, data types, relationships, nullability, uniqueness rules, units, and validation conventions used in the synthetic marketing attribution dataset.

The dataset is stored in SQLite and exported as UTF-8 CSV and JSON files.

**General conventions**

- Database: SQLite
- Timestamps: UTC, ISO 8601 text format (`YYYY-MM-DDTHH:MM:SSZ`)
- Date fields: ISO 8601 date strings (`YYYY-MM-DD`)
- Identifiers: Deterministic text IDs generated using entity-specific prefixes
- Monetary values: Numeric values represented using `REAL`
- Currency: ISO-style currency codes, such as `USD` and `EUR`
- Boolean values: Integer `0` or `1`
- Empty optional values: Stored as SQL `NULL` or empty strings depending on the export and generation path.
- Synthetic data only: No real customer information is used.

**Important:** `NOT NULL`, `PRIMARY KEY`, `UNIQUE`, `FOREIGN KEY`, and `CHECK` constraints below describe database-enforced rules. Allowed-value conventions and additional validation may be enforced by the Python generator or analytics layer.

## 2. Entity relationship overview

| Parent entity | Child entity | Relationship |
|---|---|---|
| Channel | Campaign | One-to-many |
| Campaign | Creative | One-to-many |
| Campaign | Audience | Many-to-many through CampaignAudience |
| Contact | WebSession | One-to-many |
| Contact | Touchpoint | One-to-many |
| Contact | Lead | One-to-many |
| Contact | Opportunity | One-to-many |
| WebSession | Lead | One-to-many |
| WebSession | Touchpoint | One-to-many |
| Lead | Opportunity | One-to-many |
| Opportunity | Order | One-to-many |
| Campaign | CostRecord | One-to-many |
| Campaign | Touchpoint | One-to-many |
| Opportunity | AttributionResult | One-to-many |
| Campaign | AttributionResult | One-to-many |

Some relationships are optional. For example, an anonymous WebSession can exist without a Contact, and an unresolved Lead can remain without an associated Contact.

## 3. Field-level data dictionary

### 3.1 Channel

Purpose: Stores marketing acquisition channels.

| Field | Type | Required | Key / uniqueness | Description and validation |
|---|---|---|---|---|
| channel_id | TEXT | Yes | Primary key | Unique channel identifier |
| name | TEXT | Yes | UNIQUE | Channel name; must be unique |

### 3.2 Campaign

Purpose: Stores marketing campaign details and budgets.

| Field | Type | Required | Key / uniqueness | Description and validation |
|---|---|---|---|---|
| campaign_id | TEXT | Yes | Primary key | Unique campaign identifier |
| name | TEXT | Yes | — | Campaign name |
| channel_id | TEXT | Yes | Foreign key → Channel | Must reference an existing channel |
| start_date | TEXT | Yes | — | Campaign start date, ISO 8601 |
| end_date | TEXT | Yes | — | Campaign end date; must not precede start date |
| budget | REAL | Yes | CHECK >= 0 | Campaign budget; monetary amount |
| currency | TEXT | Yes | — | Currency code, e.g. USD |
| status | TEXT | Yes | — | Campaign lifecycle status |

### 3.3 Creative

Purpose: Stores campaign creative assets and formats.

| Field | Type | Required | Key / uniqueness | Description and validation |
|---|---|---|---|---|
| creative_id | TEXT | Yes | Primary key | Unique creative identifier |
| campaign_id | TEXT | Yes | Foreign key → Campaign | Parent campaign |
| name | TEXT | Yes | — | Creative name |
| creative_type | TEXT | Yes | — | Generated creative category; examples include video, image, text, and carousel |

### 3.4 Audience

Purpose: Stores campaign audience segments.

| Field | Type | Required | Key / uniqueness | Description and validation |
|---|---|---|---|---|
| audience_id | TEXT | Yes | Primary key | Unique audience identifier |
| name | TEXT | Yes | — | Audience segment name |
| audience_type | TEXT | Yes | — | Audience category; examples include prospecting, retargeting, customer, and lookalike |

### 3.5 Contact

Purpose: Stores synthetic customer/contact records.

| Field | Type | Required | Key / uniqueness | Description and validation |
|---|---|---|---|---|
| contact_id | TEXT | Yes | Primary key | Unique synthetic contact identifier |
| created_at | TEXT | Yes | — | Contact creation timestamp, UTC |
| region | TEXT | Yes | — | Synthetic geographic region |
| consent_status | TEXT | Yes | — | Consent category; generated values include granted, restricted, and unknown |

### 3.6 CampaignAudience

Purpose: Implements the many-to-many relationship between campaigns and audience segments.

| Field | Type | Required | Key / uniqueness | Description and validation |
|---|---|---|---|---|
| campaign_id | TEXT | Yes in generated data | Composite primary key; foreign key → Campaign | Associated campaign |
| audience_id | TEXT | Yes in generated data | Composite primary key; foreign key → Audience | Associated audience |

The combination of `campaign_id` and `audience_id` must be unique. The SQL schema permits NULL values in the individual columns, so the generator is responsible for producing complete bridge records.

### 3.7 WebSession

Purpose: Records website sessions and available identity evidence.

| Field | Type | Required | Key / uniqueness | Description and validation |
|---|---|---|---|---|
| session_id | TEXT | Yes | Primary key | Unique session identifier |
| contact_id | TEXT | Optional | Foreign key → Contact | NULL for anonymous sessions |
| started_at | TEXT | Yes | — | Session start timestamp, UTC |
| source | TEXT | Yes | — | Session acquisition source |
| identity_evidence | TEXT | Optional | — | Evidence supporting identity resolution |
| issue_type | TEXT | Optional | — | Exception label; may identify anonymous sessions without evidence |

Identity must not be inferred for an anonymous session without sufficient evidence.

### 3.8 Touchpoint

Purpose: Records campaign interactions, including online and offline interactions.

| Field | Type | Required | Key / uniqueness | Description and validation |
|---|---|---|---|---|
| touchpoint_id | TEXT | Yes | Primary key | Unique touchpoint identifier |
| contact_id | TEXT | Optional | Foreign key → Contact | Associated contact, when known |
| campaign_id | TEXT | Optional | Foreign key → Campaign | Associated campaign |
| channel_id | TEXT | Optional | Foreign key → Channel | Associated channel |
| creative_id | TEXT | Optional | Foreign key → Creative | Associated creative |
| audience_id | TEXT | Optional | Foreign key → Audience | Associated audience |
| occurred_at | TEXT | Yes | — | Interaction timestamp, UTC |
| touch_type | TEXT | Yes | — | Interaction category |
| is_offline | INTEGER | Yes | Default 0 | Boolean-style flag: 0 = online, 1 = offline |
| session_id | TEXT | Optional | Foreign key → WebSession | Related web session, if available |
| issue_type | TEXT | Optional | — | Exception label, including post-conversion touches |

Attribution eligibility requires a valid interaction before the opportunity conversion time. Offline interactions are retained even when no web session exists.

### 3.9 Lead

Purpose: Records leads generated from marketing activity.

| Field | Type | Required | Key / uniqueness | Description and validation |
|---|---|---|---|---|
| lead_id | TEXT | Yes | Primary key | Unique lead identifier |
| contact_id | TEXT | Optional | Foreign key → Contact | Associated contact, if resolved |
| session_id | TEXT | Optional | Foreign key → WebSession | Related session, if available |
| created_at | TEXT | Yes | — | Lead creation timestamp, UTC |
| status | TEXT | Yes | — | Lead lifecycle status; generated values include new, qualified, converted, and lost |

Unresolved anonymous leads must remain unresolved unless identity evidence is available.

### 3.10 Opportunity

Purpose: Tracks potential sales and conversion outcomes.

| Field | Type | Required | Key / uniqueness | Description and validation |
|---|---|---|---|---|
| opportunity_id | TEXT | Yes | Primary key | Unique opportunity identifier |
| lead_id | TEXT | Optional | Foreign key → Lead | Associated lead |
| contact_id | TEXT | Optional | Foreign key → Contact | Associated contact |
| created_at | TEXT | Yes | — | Opportunity creation timestamp, UTC |
| closed_at | TEXT | Optional | — | Opportunity closure timestamp, UTC |
| stage | TEXT | Yes | — | Generated lifecycle stages include qualified, closed_won, and closed_lost |
| expected_value | REAL | Yes | — | Expected monetary value |
| currency | TEXT | Yes | — | Currency code associated with expected value |

Lifecycle dates should be chronologically consistent. Closed opportunities should have an appropriate closure timestamp.

### 3.11 Order

Purpose: Stores revenue generated from converted opportunities.

| Field | Type | Required | Key / uniqueness | Description and validation |
|---|---|---|---|---|
| order_id | TEXT | Yes | Primary key | Unique order identifier |
| opportunity_id | TEXT | Optional | Foreign key → Opportunity | Related opportunity |
| order_date | TEXT | Yes | — | Order date/timestamp, UTC |
| revenue | REAL | Yes | — | Revenue amount |
| currency | TEXT | Yes | — | Revenue currency |
| external_order_ref | TEXT | Yes | — | External order reference used for duplicate detection |
| issue_type | TEXT | Optional | — | Exception label, including duplicate_revenue |

Revenue must not be counted more than once for the same external order reference. Currency mismatches must be handled before combining monetary amounts.

### 3.12 CostRecord

Purpose: Records campaign expenditure.

| Field | Type | Required | Key / uniqueness | Description and validation |
|---|---|---|---|---|
| cost_id | TEXT | Yes | Primary key | Unique cost record identifier |
| campaign_id | TEXT | Optional | Foreign key → Campaign | Related campaign |
| incurred_at | TEXT | Yes | — | Cost occurrence timestamp, UTC |
| amount | REAL | Yes | — | Cost amount |
| currency | TEXT | Yes | — | Cost currency |
| cost_type | TEXT | Yes | — | Cost category |
| issue_type | TEXT | Optional | — | Exception label, including currency_mismatch |

ROI calculations must use comparable currencies. Missing campaign cost records must be flagged rather than treated as zero spend.

### 3.13 AttributionResult

Purpose: Stores campaign-level attribution credits and attributed revenue for each opportunity.

| Field | Type | Required | Key / uniqueness | Description and validation |
|---|---|---|---|---|
| result_id | TEXT | Yes | Primary key | Unique attribution result identifier |
| opportunity_id | TEXT | Optional | Foreign key → Opportunity | Associated opportunity |
| campaign_id | TEXT | Optional | Foreign key → Campaign | Credited campaign |
| model | TEXT | Yes | — | Attribution model: first_touch, last_touch, linear, or position_based |
| credit | REAL | Yes | — | Attribution share; expected range 0–1 |
| attributed_revenue | REAL | Yes | — | Revenue allocated to this campaign |
| calculated_at | TEXT | Yes | — | Calculation timestamp, UTC |

For each opportunity and attribution model, the sum of campaign credits should equal 1 when attribution is available. Only eligible pre-conversion touchpoints should receive credit.

### 3.14 EventHistory

Purpose: Maintains an audit history of entity lifecycle changes and events.

| Field | Type | Required | Key / uniqueness | Description and validation |
|---|---|---|---|---|
| event_id | TEXT | Yes | Primary key | Unique event identifier |
| entity_type | TEXT | Yes | — | Entity associated with the event |
| entity_id | TEXT | Yes | — | Identifier of the affected entity |
| event_type | TEXT | Yes | — | Event category |
| event_at | TEXT | Yes | — | Event timestamp, UTC |
| old_value | TEXT | Optional | — | Previous value |
| new_value | TEXT | Optional | — | Updated value |
| reason | TEXT | Optional | — | Explanation for the event |

EventHistory acts as an audit record. The entity identifier is a polymorphic reference and is not declared as a conventional SQL foreign key.

## 4. Attribution models

| Model | Description |
|---|---|
| First-touch | Assigns all attribution credit to the first eligible campaign interaction |
| Last-touch | Assigns all attribution credit to the last eligible campaign interaction |
| Linear | Distributes credit equally across eligible campaign interactions |
| Position-based | Gives greater weight to the first and last interactions, distributing the remaining credit across intermediate interactions |

Attribution excludes post-conversion touchpoints and follows the project's revenue deduplication and identity-resolution rules.

## 5. Derived metrics

| Metric | Definition | Unit |
|---|---|---|
| Attribution credit | Share of opportunity revenue assigned to a campaign | Fraction (0–1) |
| Attributed revenue | Revenue multiplied by attribution credit | Currency amount |
| Spend | Sum of eligible campaign cost records | Currency amount |
| ROAS | Attributed revenue divided by spend | Ratio |
| ROI | (Attributed revenue − spend) divided by spend | Ratio |

ROI and ROAS should not be interpreted when campaign spend is missing or when revenue and spend currencies are not comparable.

## 6. Data quality and validation rules

The generator and validation process check:

1. Primary-key uniqueness for core entities.
2. Foreign-key integrity across relational tables.
3. Valid campaign references for touchpoints.
4. Won opportunities having associated orders.
5. Attribution credit totals for each opportunity and model.
6. Attribution results having eligible pre-conversion interactions.
7. Exclusion of post-conversion touchpoints.
8. Duplicate external order references.
9. Currency mismatches in campaign costs.
10. Missing campaign cost records.
11. Anonymous sessions without identity evidence.
12. Presence of all five labelled ground-truth exception cases.

## 7. Known limitations

- Currency conversion is not performed. Non-USD amounts are excluded from USD-based ROI calculations until an approved exchange rate is available.
- Some entity relationships are optional because anonymous and partially identified journeys are intentionally represented.
- Some business rules are enforced by the generator and analytics code rather than SQL constraints.
- EventHistory uses a polymorphic entity reference rather than a foreign key to every entity table.
- The chronological train/test split is opportunity-level; it should not be interpreted as a complete entity-wide leakage-prevention mechanism.

## 8. Related files

| File | Purpose |
|---|---|
| `data/schema.sql` | Exported SQLite DDL |
| `data/attribution.db` | Generated relational database |
| `data/manifest.json` | Seed, generation metadata, row counts, and checksums |
| `data/ground_truth.csv` | Labelled edge cases |
| `data/ground_truth.json` | JSON version of labelled edge cases |
| `data/validation_summary.json` | Generated validation results |
| `src/generator.py` | Synthetic dataset generation and validation |
| `src/analytics.py` | Attribution and campaign analytics |
| `tests/test_project.py` | Automated project tests |
