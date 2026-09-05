# WHO Growth Chart Analyzer

> **Domain:** Clinical Decision Support & Biomedical Computing  
> **Standards:** Standard Clinical Formulations & ISO/IEC Quality Frameworks

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-3776AB.svg?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688.svg?logo=fastapi&logoColor=white)
![Audit Trail](https://img.shields.io/badge/Audit-HMAC--SHA256_Tamper--Evident-brightgreen.svg)
![Zero-PHI Guard](https://img.shields.io/badge/Guard-Zero--PHI_Outbound-blue.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg?logo=docker&logoColor=white)

</div>

---

## Overview

WHO Growth Chart Analyzer computes weight/height/head-circumference percentiles via LMS methodology with stunting/wasting flags. It also provides a multi-agent evaluation framework with HMAC-SHA256 tamper-evident audit trails and zero-PHI outbound protection.

---

## Key Features

### Analytical Functions
- **BMI-for-age calculation** — `calculate_bmi_z()` computes BMI from weight/height
- **HbA1c conversion** — `convert_hba1c()` converts between HbA1c (%) and estimated average glucose (mg/dL)
- **Generic scoring** — `calculate_score()` provides weighted-sum scoring for arbitrary inputs

### Enterprise Security
- **Zero-PHI Outbound Guard** — AST and regex inspection blocking SSNs, MRNs, phone numbers, and patient identifiers
- **HMAC-SHA256 Audit Trail** — Chained, cryptographically signed logs for every evaluation
- **Multi-Agent Evaluation** — Specialized workers (QC, Safety, Protocol Conformance) for task assessment

### REST API
- **FastAPI Server** — OpenAPI 3.1 REST endpoints for audit, chat, and logs
- **Prometheus Metrics** — Operational metrics at `/metrics`

---

## Installation

```bash
# Clone the repository
git clone https://github.com/abusuraihsakhri/who-growth-chart-analyzer.git
cd who-growth-chart-analyzer

# Install dependencies
pip install -e ".[dev]"

# Set the required audit key (generate a secure random key)
export AUDIT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
```

---

## Usage

### CLI Commands

```bash
# Single task evaluation
python cli.py audit --task-id TASK-01 --target SPECIMEN-01 --primary 28.5 --secondary 14.2

# Chat with the supervisor
python cli.py chat "Explain the evaluation"

# Batch CSV processing
python cli.py batch -i sample.csv -o results.csv

# Verify audit trail integrity
python cli.py verify-audit

# Start the FastAPI server
python cli.py serve --host 127.0.0.1 --port 8000
```

### Direct Growth Chart Calculations

```python
from growth_chart import calculate_bmi_z, convert_hba1c

# BMI calculation
result = calculate_bmi_z(weight_kg=70, height_cm=175, age_months=60, sex="M")
print(result)  # {'bmi': 22.86, 'weight_kg': 70.0, 'height_cm': 175.0}

# HbA1c conversion
result = convert_hba1c(hba1c_percent=6.5)
print(result)  # {'hba1c_percent': 6.5, 'eag_mgdl': 140.0}
```

### Batch CSV Processing

```bash
python growth_chart.py batch --input sample.csv --output results.csv
```

---

## API Endpoints

| Endpoint | Method | Description |
|:---------|:-------|:------------|
| `/health` | GET | Health check |
| `/metrics` | GET | Operational metrics |
| `/api/audit` | POST | Submit task for multi-agent evaluation |
| `/api/chat` | POST | Query the supervisory chat |
| `/api/audit/logs` | GET | Retrieve and verify HMAC audit trail |

---

## Security

The application requires the `AUDIT_SECRET_KEY` environment variable. **Never commit this key.** Generate a fresh key for each deployment:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

The docker-compose setup reads from a `.env` file that you must create:

```bash
# .env
AUDIT_SECRET_KEY=your-generated-key-here
```

---

## Testing

```bash
# Run all tests
pytest -v

# Run simulation benchmark
python simulator.py 1000
```

---

## Docker Deployment

```bash
# Build and run
docker build -t who-growth-chart-analyzer .
docker run -e AUDIT_SECRET_KEY=your-key -p 8000:8000 who-growth-chart-analyzer

# Or use docker-compose
echo "AUDIT_SECRET_KEY=$(python -c 'import secrets;print(secrets.token_hex(32)')" > .env
docker-compose up
```

---

## Project Structure

```
who-growth-chart-analyzer/
├── agents/              # Multi-agent evaluation framework
│   ├── api.py           # FastAPI REST server
│   ├── base.py          # Security, PHI guard, audit trail
│   ├── models.py        # Pydantic data models
│   ├── supervisor.py    # Master orchestrator
│   ├── workers.py       # Specialized evaluation workers
│   └── llm_factory.py   # LLM provider factory
├── tests/               # Test suite
├── growth_chart.py      # Core calculation engine
├── cli.py               # Command-line interface
├── simulator.py         # High-throughput simulation
├── enrichment.py        # Feature enrichment modules
├── web/index.html       # Operations dashboard
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.
