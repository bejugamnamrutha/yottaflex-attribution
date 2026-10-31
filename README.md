# YottaFlex.ai – Marketing Attribution & ROI Analytics

A reproducible synthetic-data project for the Associate AI Forward Deployed Engineer challenge. It connects campaigns, channels, creatives, audiences, contacts, touchpoints, web sessions, leads, opportunities, orders, and campaign costs. The project compares attribution models, calculates campaign ROI and ROAS, and preserves labelled data-quality exceptions separately from analytical inputs.

## Technology Stack

- Python 3.10+
- SQLite for relational storage and foreign-key integrity
- Pandas for data processing and analytics
- Streamlit for the interactive dashboard
- Pytest for automated testing
- Python `random.Random` with fixed seed `20261022`

## Quick Start

Create and activate a virtual environment:

```bash
python -m venv venv

# Windows PowerShell
.\venv\Scripts\Activate.ps1

# macOS/Linux
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Generate the starter dataset:

```bash
python src/generator.py --out data --scale starter --seed 20261022 --config config.json
```

Generate the full-scale dataset:

```bash
python src/generator.py --out data --scale full --seed 20261022 --config config.json
```

Run the dashboard:

```bash
streamlit run app.py
```

Run automated tests:

```bash
pytest -q
```

If PowerShell blocks virtual-environment activation, you can run Python directly using:

```powershell
.\venv\Scripts\python.exe src\generator.py --out data --scale starter --seed 20261022 --config config.json
.\venv\Scripts\python.exe -m pytest -q
```

## Full-Scale Dataset

The full-scale configuration generates:

| Entity | Records |
|---|---:|
| Campaign | 500 |
| Channel | 9 |
| Creative | 500 |
| Audience | 12 |
| Contact | 50,000 |
| CampaignAudience | 500 |
| WebSession | 25,000 |
| Touchpoint | 200,001 |
| Lead | 10,001 |
| Opportunity | 10,000 |
| Order | 7,129 |
| CostRecord | 500 |
| EventHistory | 10,000 |
| AttributionResult | 54,248 |

The touchpoint count includes 200,000 baseline records and one additional labelled post-conversion edge-case record.

The generator uses a fixed seed and configurable scale settings in `config.json`.

## Project Outputs

Generated files are stored in the `data/` directory:

- Entity-level CSV and JSON exports.
- `attribution.db` – SQLite database.
- `schema.sql` – SQL table definitions, constraints, and indexes.
- `AttributionResult.csv` and `AttributionResult.json` – attribution outputs.
- `ground_truth.csv` and `ground_truth.json` – labelled edge cases and expected decisions.
- `Opportunity_train.csv` and `Opportunity_test.csv` – chronological opportunity-level split.
- `opportunity_split.csv` – split assignment information.
- `manifest.json` – generation seed, timestamp, record counts, and SHA-256 checksums.
- `validation_summary.json` – data-integrity and attribution validation results.

Ground-truth labels are kept separate from analytical input features to avoid evaluation leakage.

## Attribution Models

All eligible touchpoints must belong to the opportunity's contact and occur at or before the closed-won timestamp. Post-conversion touchpoints are excluded.

The project implements four attribution models:

- **First-touch:** 100% credit to the earliest eligible campaign.
- **Last-touch:** 100% credit to the latest eligible campaign.
- **Linear:** Equal credit across distinct campaigns in the journey.
- **Position-based:** 40% credit to the first campaign, 40% to the last, and 20% distributed among middle campaigns. If there is one campaign, it receives 100%; if there are two, each receives 50%.

Each opportunity's attribution credits sum to 1 for each model.

Revenue is deduplicated using `external_order_ref`. Only eligible USD orders without an issue label are included in analytical revenue.

## ROI and ROAS

**ROI:**

`(Attributed Revenue - Campaign Spend) / Campaign Spend`

**ROAS:**

`Attributed Revenue / Campaign Spend`

Campaign spend is calculated from valid USD `CostRecord` entries. Campaign budget represents a planning limit, not actual spend.

Missing campaign costs and currency mismatches are flagged rather than silently treated as valid spend.

## Data Model and Relationships

- Channel 1:N Campaign.
- Campaign 1:N Creative.
- Campaign N:M Audience through `CampaignAudience`.
- Contact 1:N Touchpoint, WebSession, Lead, and Opportunity.
- WebSession 1:N Lead, with an optional session relationship.
- Lead 1:N Opportunity.
- Opportunity 1:N Order.
- Campaign 1:N CostRecord and AttributionResult.
- Opportunity 1:N AttributionResult.
- EventHistory records lifecycle events.

The project uses primary keys, foreign keys, indexes, optional identity relationships, and explicit lifecycle fields. See `data/schema.sql` and `DATA_DICTIONARY.md` for details.

## Data Quality and Edge Cases

Five labelled scenarios are deliberately included:

1. **Duplicate revenue:** A repeated `external_order_ref` is identified and excluded from duplicate revenue aggregation.
2. **Post-conversion touch:** A touchpoint occurring after conversion is excluded from attribution.
3. **Currency mismatch:** An EUR cost in a USD analysis is flagged and excluded rather than converted without an approved exchange rate.
4. **Missing campaign cost:** A campaign with omitted cost records is flagged for review.
5. **Anonymous session:** A session without a contact identifier or identity evidence remains unresolved; no identity is inferred.

The `ground_truth` files document these scenarios for evaluation. They must not be used as model input features.

## Reproducibility

Run the generator with the same seed and configuration to reproduce the synthetic records.

Compare entity CSV checksums in `manifest.json` to verify deterministic output. Generation timestamps and database file bytes may vary because of runtime metadata.

The random data generation is seeded, and attribution calculations are deterministic.

## Validation and Testing

The generator validates:

- Foreign-key integrity.
- Primary-key uniqueness for core entities.
- Touchpoint campaign references.
- Closed-won opportunities with orders.
- Attribution credit totals.
- Eligible-touch attribution rules.
- Post-conversion attribution exclusions.
- Ground-truth edge-case coverage.

Run the automated test suite:

```bash
pytest -q
```

## Design Decisions and Limitations

- All records are synthetic; no personal or confidential customer data is used.
- USD is the baseline currency. The EUR exception is flagged, and automatic foreign-exchange conversion is not implemented.
- Attribution is deterministic and rule-based. It allocates credit but does not prove that a campaign caused a sale.
- Anonymous identities are not inferred without evidence.
- The train/test split is performed at the opportunity level using chronological ordering. It does not represent a complete production-grade, time-aware split of every related entity.
- Production extensions could include approved effective-dated FX rates, consent-aware retention, late-arriving event handling, idempotent ingestion, role-based access, and a formal data-quality quarantine process.

## Submission Checklist

- [ ] Public GitHub repository.
- [ ] Source code, tests, documentation, and configuration committed.
- [ ] Starter dataset generated successfully.
- [ ] Full-scale dataset generated successfully.
- [ ] Automated tests pass.
- [ ] Validation summary reviewed.
- [ ] Dashboard tested and screenshots added.
- [ ] Ground-truth labels kept separate from analytical inputs.
- [ ] No credentials, private data, or unnecessary oversized files committed.