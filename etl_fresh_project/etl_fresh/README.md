# Enterprise ETL Pipeline — Setup Guide (Windows 11)

## Project Structure
```
etl_fresh/
├── config/models.py              # Pydantic models (Week 1)
├── extractors/
│   ├── stripe_extractor.py       # Stripe API (Week 1)
│   ├── salesforce_extractor.py   # Salesforce API (Week 1)
│   └── zendesk_extractor.py      # Zendesk API (Week 1)
├── transformers/transformer.py   # Polars/Pandas (Week 2)
├── loaders/db_loader.py          # PostgreSQL UPSERT (Week 3)
├── orchestration/pipeline.py     # Full pipeline runner (Week 3)
├── dags/etl_dag.py               # Airflow DAG (Week 4)
├── utils/
│   ├── logger.py
│   └── alerting.py               # Slack/Email alerts (Week 4)
├── tests/test_transformers.py    # 20 Pytest tests (Week 2)
├── .env.example
├── requirements.txt
├── Dockerfile                    # Week 4
├── docker-compose.yml            # Week 4
└── .github/workflows/ci.yml      # CI/CD (Week 4)
```

---

## STEP 1 — Folder Extract Karo

ZIP file pe right click → Extract All → Desktop pe extract karo
Folder ka naam: `etl_fresh`

---

## STEP 2 — VS Code Mein Kholo

```
File → Open Folder → etl_fresh select karo
```

---

## STEP 3 — Terminal Kholo

```
VS Code mein: Terminal → New Terminal
```

---

## STEP 4 — Virtual Environment Banao

```
python -m venv venv
```

---

## STEP 5 — Activate Karo

```
venv\Scripts\activate
```

Terminal mein (venv) dikhega — matlab activate ho gaya

---

## STEP 6 — Libraries Install Karo

```
pip install -r requirements.txt
```

3-5 minute lagenge — wait karo

---

## STEP 7 — .env File Banao

```
copy .env.example .env
```

.env file mein ye check karo:
```
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=data_warehouse
POSTGRES_USER=postgres
POSTGRES_PASSWORD=etl_password
```

---

## STEP 8 — PostgreSQL Mein Database Banao

pgAdmin 4 kholo → Servers → PostgreSQL 15 → Connect
Password: etl_password

Phir Databases pe right click → Create → Database
Name: data_warehouse → Save

---

## STEP 9 — Tests Chalao (SABSE IMPORTANT)

```
set PYTHONPATH=. && pytest tests/ -v
```

Expected output:
```
test_email_lowercase         PASSED
test_currency_uppercase      PASSED
test_cents_to_dollars        PASSED
... (20 lines)
20 passed in 0.8s
```

---

## STEP 10 — Database Tables Banao

```
set PYTHONPATH=. && python -c "from loaders.db_loader import DatabaseLoader; db = DatabaseLoader(); print('Tables ready!')"
```

---

## STEP 11 — Pipeline Chalao (Real APIs ke saath)

```
set PYTHONPATH=. && python orchestration/pipeline.py
```

---

## Common Errors

| Error | Fix |
|-------|-----|
| `python is not recognized` | Python install karo + PATH tick karo |
| `(venv)` nahi dikhta | `venv\Scripts\activate` chalao |
| `ModuleNotFoundError` | `pip install -r requirements.txt` chalao |
| PostgreSQL connection refused | pgAdmin mein PostgreSQL service check karo |
| `PYTHONPATH` kaam nahi karta | `set PYTHONPATH=.` use karo |
