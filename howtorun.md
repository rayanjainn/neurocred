# How to Run — Airavat Digital Twin Engine

All commands are run from the **`airavat/`** subdirectory unless noted otherwise.

```
cd airavat/
```

---

## 1. Prerequisites

| Tool | Min version | Install |
|------|-------------|---------|
| Mamba / Conda | 23+ | see below |
| Redis | 7.x | `conda install -c conda-forge redis` |
| Git | any | |

### Install Mamba (recommended over plain conda)

If you have Miniforge or Mambaforge already, skip this. Otherwise:

```bash
# macOS / Linux — install Miniforge (ships mamba by default)
curl -L https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh -o miniforge.sh
bash miniforge.sh -b -p "$HOME/miniforge3"
source "$HOME/miniforge3/etc/profile.d/conda.sh"
conda init zsh       # or bash
exec $SHELL
```

Verify:
```bash
mamba --version
```

---

## 2. Create the conda environment

```bash
# From the airavat/ directory
mamba create -n airavat python=3.11 -y
mamba activate airavat
```

### Install Redis via conda (no brew needed)

```bash
mamba install -c conda-forge redis -y
```

### Install Python dependencies

Heavy ML packages (numpy, scipy, scikit-learn, xgboost) are faster to install
through conda-forge than pip. Install them with mamba first, then pip for the
rest:

```bash
# Core scientific stack — conda-forge builds are faster and link to system BLAS
mamba install -c conda-forge \
    numpy scipy scikit-learn xgboost \
    polars pyarrow psutil \
    redis-py \
    -y

# Remaining packages (not on conda-forge or better from PyPI)
pip install -e ".[dev]"
```

> `sdv` (GaussianCopulaSynthesizer) and `sentence-transformers` (MiniLM-L6-v2)
> are installed via pip as part of `pip install -e ".[dev]"`.

---

## 3. Environment variables (optional)

Defaults work out of the box. Create a `.env` only if you need to override:

```bash
cat > .env << 'EOF'
REDIS_URL=redis://localhost:6379/0
N_PROFILES=250
HISTORY_MONTHS=12
EOF
```

---

## 4. Offline pipeline (no Redis needed)

Generates synthetic data, computes features, trains the model, runs tests.

```bash
mamba activate airavat
bash scripts/run_offline.sh
```

Or step by step:

```bash
# Phase 1 — generate 250 profiles × 12 months across 6 data sources
#            writes data/raw/*_chunk_NNNN.parquet
python -m src.ingestion.generator

# Phase 3 — compute 18 behavioural features per user (EMA + KNNImputer + IsolationForest)
#            writes data/features/user_id=*/features.parquet
python -m src.features.engine batch

# Phase 4 — train XGBoost digital-twin scorer
#            writes data/models/xgb_digital_twin.ubj + feature_columns.json
python -m src.scoring.trainer

# Phase 5 — run tests
python -m pytest tests/ -v
```

---

## 5. Online pipeline (with Redis)

```bash
# Terminal 0 — start Redis (installed via conda)
redis-server

# Or as a background daemon
redis-server --daemonize yes --logfile /tmp/airavat-redis.log
```

Then run the full pipeline:

```bash
mamba activate airavat
bash scripts/run_online.sh
```

Or step by step:

```bash
# Phase 1 — generate data to Parquet
python -m src.ingestion.generator

# Phase 2 — ingest Parquet data into Redis Streams
python -m src.ingestion.redis_producer

# Phase 3 — batch feature engine
python -m src.features.engine batch

# Phase 4 — train model
python -m src.scoring.trainer

# Phase 5 — run tests
python -m pytest tests/ -v

# Phase 6 — start API server (port 8001)
uvicorn src.api.main:app --host 0.0.0.0 --port 8001 --reload
```

---

## 6. Start the API server only

```bash
mamba activate airavat
bash scripts/start_server.sh
# or directly:
uvicorn src.api.main:app --host 0.0.0.0 --port 8001 --reload
```

Server: **http://localhost:8001**  
Swagger UI: **http://localhost:8001/docs**

---

## 7. API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness check |
| POST | `/ingest/trigger` | Trigger synthetic data generator + Redis ingest |
| GET | `/ingest/status` | Generator run status |
| GET | `/classify/status` | Classifier stream lag |
| GET | `/features/{user_id}` | Latest `BehaviouralFeatureVector` for a user |
| GET | `/windows/{user_id}` | Sliding-window aggregates (7d / 30d / 90d) |
| GET | `/users` | List all user IDs with cached features |
| POST | `/cohorts/build` | Rebuild peer cohort Parquet stats |

Quick smoke test:
```bash
curl http://localhost:8001/health
```

---

## 8. Run tests

```bash
bash scripts/run_tests.sh

# With coverage
bash scripts/run_tests.sh --cov=src --cov-report=term-missing

# Single tier
python -m pytest tests/test_tier1.py -v
python -m pytest tests/test_tier2.py -v
python -m pytest tests/test_tier3.py -v
```

---

## 9. Online streaming workers (for real-time path)

Long-lived workers consuming Redis Streams. Open each in a separate terminal
(or use `tmux`). Activate the env in each terminal first.

```bash
mamba activate airavat

# Terminal 1 — Tier 2: classify raw events → typed events
python -m src.classifier.event_processor

# Terminal 2 — Tier 3: compute features from typed events stream
python -m src.features.engine          # no "batch" arg = streaming mode

# Terminal 3 — rebuild peer cohort stats periodically
python -m src.features.peer_cohort
```

---

## 10. Data layout

```
airavat/
├── data/
│   ├── raw/                          # Phase 1 output
│   │   ├── bank_chunk_0000.parquet
│   │   ├── upi_chunk_0000.parquet
│   │   ├── sms_chunk_0000.parquet
│   │   ├── emi_chunk_0000.parquet
│   │   ├── open_banking_chunk_0000.parquet
│   │   ├── voice_chunk_0000.parquet
│   │   └── user_profiles.parquet
│   ├── features/                     # Phase 3 output
│   │   ├── user_id=usr_0000/
│   │   │   └── features.parquet
│   │   └── peer_cohorts.parquet
│   └── models/                       # Phase 4 output
│       ├── xgb_digital_twin.ubj
│       ├── xgb_digital_twin_income_heavy.ubj
│       ├── feature_columns.json
│       └── label_encoder.json
├── src/
│   ├── ingestion/    # Tier 1
│   ├── classifier/   # Tier 2
│   ├── features/     # Tier 3
│   ├── scoring/      # Tier 4
│   └── api/          # FastAPI
├── scripts/
│   ├── phase1_generate.sh

---

## 11. Stress Twin Workflow (Multi-Version + Monte Carlo)

Use this to force large risk fluctuations for a user, create many twin versions,
and run simulation at each step.

```bash
bash scripts/stress_twin_workflow.sh --user-id u_a22645da --gstin 24IEYIC0868X8Z8
```

Useful flags:

```bash
# auto-fix missing feature/twin setup before stress loop
bash scripts/stress_twin_workflow.sh --user-id u_a22645da --auto-fix

# custom API/Redis and longer experiment
bash scripts/stress_twin_workflow.sh \
    --user-id u_a22645da \
    --api-base http://127.0.0.1:8001 \
    --redis-url redis://localhost:6379/0 \
    --steps 12
```

Note:

- If `/features/<user_id>` returns 404 but `data/features/user_id=<user_id>/features.parquet` exists,
    the script now auto-seeds `twin:features:<user_id>` in Redis from local parquet before running updates.
- If `income_30d` is still missing/zero after hydration, simulation will still fail with 422 until upstream
    ingestion/classification data is available for that user.

### 422 Fix Guidance

If you see:

`Simulation snapshot missing income ... (422)`

it means the backend cannot derive required financial inputs for that user.

Fix sequence:

```bash
bash scripts/phase3_features.sh
curl -X POST http://127.0.0.1:8001/twin/bootstrap
curl http://127.0.0.1:8001/features/<user_id>
curl -X POST http://127.0.0.1:8001/twin/<user_id>/update
```

Then rerun simulation or the stress workflow script.
│   ├── phase2_redis_ingest.sh
│   ├── phase3_features.sh
│   ├── phase4_train.sh
│   ├── phase5_tests.sh
│   ├── phase6_api.sh
│   ├── run_offline.sh     # phases 1,3,4,5
│   ├── run_online.sh      # redis + phases 1-6
│   ├── start_server.sh    # API only
│   └── run_tests.sh       # tests only
└── tests/
    ├── test_tier1.py
    ├── test_tier2.py
    └── test_tier3.py
```

---

## 11. Troubleshooting

**`mamba: command not found`**
```bash
source "$HOME/miniforge3/etc/profile.d/conda.sh"
mamba activate airavat
```

**`conda activate` not working in a new shell**
```bash
conda init zsh    # or bash
exec $SHELL
```

**`ModuleNotFoundError: No module named 'polars'` (or any dep)**
```bash
mamba activate airavat
pip install -e ".[dev]"
```

**`sdv` install fails**
```bash
pip install sdv --no-deps
pip install sdv
```

**Redis connection refused**
```bash
mamba activate airavat
redis-server --daemonize yes
redis-cli ping   # should return PONG
```

**MiniLM model download slow (first run)**
`sentence-transformers` downloads `all-MiniLM-L6-v2` (~90 MB) on first use.
It caches to `~/.cache/huggingface/`. Subsequent runs are instant.

**Out of memory during Phase 1 (250 profiles)**
```bash
N_PROFILES=50 python -m src.ingestion.generator
```

**Tests fail with `warmup()` timeout**
Pre-download the model, then retry:
```bash
python -c "from src.classifier.merchant_classifier import warmup; warmup()"
python -m pytest tests/ -v
```

**Wrong Python version inside the env**
```bash
mamba activate airavat
python --version   # should be 3.11.x
# if not:
mamba install python=3.11 -y
```
