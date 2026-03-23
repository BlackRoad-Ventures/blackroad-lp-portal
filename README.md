# blackroad-lp-portal

> Limited partner portal and fund reporting

Part of the [BlackRoad OS](https://blackroad.io) ecosystem — [BlackRoad-Ventures](https://github.com/BlackRoad-Ventures)

---

# blackroad-lp-portal

Limited partner portal and fund reporting system.

## Features
- Multi-fund management with vintage year tracking
- LP onboarding with type classification (institutional, family office, individual, corporate)
- Pro-rata capital call issuance across all LPs
- Distribution recording with type classification
- NAV tracking with historical updates
- Fund-level metrics: TVPI, DPI, RVPI
- Individual LP account statements
- Full capital account history

## Key Metrics
| Metric | Definition |
|--------|-----------|
| DPI | Distributions / Called Capital |
| RVPI | NAV / Called Capital |
| TVPI | DPI + RVPI (Total Value / Called Capital) |

## Fund Lifecycle
`fundraising` → `deploying` → `harvesting` → `closed`

## Usage
```bash
python lp_portal.py list-funds
python lp_portal.py metrics <fund_id>
python lp_portal.py statement <lp_id>
python lp_portal.py report <lp_id>
```

## Run Tests
```bash
pip install pytest
pytest tests/ -v
```
