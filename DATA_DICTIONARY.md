# Detailed schema reference

See the SQL DDL in `src/generator.py` for exact types, keys and constraints. CSV values are UTF-8; timestamps are UTC ISO-8601 strings. IDs are immutable within a deterministic run.

| Table | Key | Fields | Rules |
|---|---|---|---|
| Channel | channel_id | name | unique channel name |
| Campaign | campaign_id | name, channel_id, start_date, end_date, budget, currency, status | channel FK; budget >= 0; end >= start |
| Creative | creative_id | campaign_id, name, creative_type | campaign FK; type video/image/text/carousel |
| Audience | audience_id | name, audience_type | type prospecting/retargeting/customer/lookalike |
| Contact | contact_id | created_at, region, consent_status | synthetic ID; consent granted/restricted/unknown |
| CampaignAudience | campaign_id + audience_id | bridge | N:M; composite PK |
| Touchpoint | touchpoint_id | contact_id, campaign_id, channel_id, creative_id, audience_id, occurred_at, touch_type, is_offline, session_id, issue_type | parent FKs; offline 0/1; labelled exceptions retained |
| WebSession | session_id | contact_id, started_at, source, identity_evidence, issue_type | contact optional; anonymous requires evidence before linking |
| Lead | lead_id | contact_id, session_id, created_at, status | contact/session optional; status new/qualified/converted/lost |
| Opportunity | opportunity_id | lead_id, contact_id, created_at, closed_at, stage, expected_value, currency | dates ordered; stage qualified/closed_won/closed_lost |
| Order | order_id | opportunity_id, order_date, revenue, currency, external_order_ref, issue_type | opportunity FK; revenue >= 0; external ref used for duplicate detection |
| CostRecord | cost_id | campaign_id, incurred_at, amount, currency, cost_type, issue_type | campaign FK; amount >= 0; currency checked by analysis policy |
| AttributionResult | result_id | opportunity_id, campaign_id, model, credit, attributed_revenue, calculated_at | FKs; model first_touch/last_touch/linear/position_based; credit 0..1 |
| EventHistory | event_id | entity_type, entity_id, event_type, event_at, old_value, new_value, reason | append-only audit event |
