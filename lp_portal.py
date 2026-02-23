#!/usr/bin/env python3
"""
BlackRoad LP Portal — Limited partner portal and fund reporting
"""

import sqlite3
import json
import uuid
import math
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional, List
from enum import Enum
from pathlib import Path


DB_PATH = Path("lp_portal.db")


class FundStatus(str, Enum):
    FUNDRAISING = "fundraising"
    DEPLOYING = "deploying"
    HARVESTING = "harvesting"
    CLOSED = "closed"


class LPType(str, Enum):
    INSTITUTIONAL = "institutional"
    FAMILY_OFFICE = "family_office"
    INDIVIDUAL = "individual"
    CORPORATE = "corporate"


@dataclass
class Fund:
    name: str
    vintage_year: int
    size: float
    focus: str
    status: FundStatus = FundStatus.FUNDRAISING
    fund_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    currency: str = "USD"
    management_fee_pct: float = 2.0
    carry_pct: float = 20.0
    hurdle_rate: float = 8.0
    gp_commit_pct: float = 1.0
    description: str = ""


@dataclass
class LP:
    fund_id: str
    name: str
    lp_type: LPType
    commitment: float
    called_capital: float = 0.0
    distributions: float = 0.0
    nav: float = 0.0
    lp_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    contact_email: str = ""
    contact_name: str = ""

    @property
    def uncalled_capital(self) -> float:
        return self.commitment - self.called_capital

    @property
    def total_value(self) -> float:
        return self.distributions + self.nav

    @property
    def dpi(self) -> float:
        if self.called_capital == 0:
            return 0.0
        return round(self.distributions / self.called_capital, 3)

    @property
    def rvpi(self) -> float:
        if self.called_capital == 0:
            return 0.0
        return round(self.nav / self.called_capital, 3)

    @property
    def tvpi(self) -> float:
        return round(self.dpi + self.rvpi, 3)


@dataclass
class CapitalCall:
    fund_id: str
    lp_id: str
    amount: float
    call_date: str
    due_date: str
    purpose: str
    call_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "pending"
    paid_date: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class Distribution:
    fund_id: str
    lp_id: str
    amount: float
    distribution_type: str
    date: str
    dist_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    notes: str = ""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Initialize the LP portal database."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS funds (
            fund_id             TEXT PRIMARY KEY,
            name                TEXT NOT NULL,
            vintage_year        INTEGER NOT NULL,
            size                REAL NOT NULL,
            focus               TEXT NOT NULL,
            status              TEXT DEFAULT 'fundraising',
            currency            TEXT DEFAULT 'USD',
            management_fee_pct  REAL DEFAULT 2.0,
            carry_pct           REAL DEFAULT 20.0,
            hurdle_rate         REAL DEFAULT 8.0,
            gp_commit_pct       REAL DEFAULT 1.0,
            description         TEXT DEFAULT '',
            created_at          TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS lps (
            lp_id           TEXT PRIMARY KEY,
            fund_id         TEXT NOT NULL,
            name            TEXT NOT NULL,
            lp_type         TEXT NOT NULL,
            commitment      REAL NOT NULL,
            called_capital  REAL DEFAULT 0.0,
            distributions   REAL DEFAULT 0.0,
            nav             REAL DEFAULT 0.0,
            contact_email   TEXT DEFAULT '',
            contact_name    TEXT DEFAULT '',
            created_at      TEXT NOT NULL,
            FOREIGN KEY (fund_id) REFERENCES funds(fund_id)
        );

        CREATE TABLE IF NOT EXISTS capital_calls (
            call_id     TEXT PRIMARY KEY,
            fund_id     TEXT NOT NULL,
            lp_id       TEXT NOT NULL,
            amount      REAL NOT NULL,
            call_date   TEXT NOT NULL,
            due_date    TEXT NOT NULL,
            purpose     TEXT NOT NULL,
            status      TEXT DEFAULT 'pending',
            paid_date   TEXT,
            created_at  TEXT NOT NULL,
            FOREIGN KEY (fund_id) REFERENCES funds(fund_id),
            FOREIGN KEY (lp_id) REFERENCES lps(lp_id)
        );

        CREATE TABLE IF NOT EXISTS distributions (
            dist_id             TEXT PRIMARY KEY,
            fund_id             TEXT NOT NULL,
            lp_id               TEXT NOT NULL,
            amount              REAL NOT NULL,
            distribution_type   TEXT NOT NULL,
            date                TEXT NOT NULL,
            notes               TEXT DEFAULT '',
            created_at          TEXT NOT NULL,
            FOREIGN KEY (fund_id) REFERENCES funds(fund_id),
            FOREIGN KEY (lp_id) REFERENCES lps(lp_id)
        );

        CREATE TABLE IF NOT EXISTS nav_updates (
            update_id   TEXT PRIMARY KEY,
            fund_id     TEXT NOT NULL,
            lp_id       TEXT NOT NULL,
            old_nav     REAL NOT NULL,
            new_nav     REAL NOT NULL,
            as_of_date  TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            notes       TEXT DEFAULT '',
            FOREIGN KEY (fund_id) REFERENCES funds(fund_id)
        );
    """)
    conn.commit()
    conn.close()


def add_fund(name: str, vintage_year: int, size: float, focus: str,
             management_fee_pct: float = 2.0, carry_pct: float = 20.0,
             hurdle_rate: float = 8.0, description: str = "") -> Fund:
    """Add a new fund."""
    init_db()
    fund = Fund(name=name, vintage_year=vintage_year, size=size, focus=focus,
                management_fee_pct=management_fee_pct, carry_pct=carry_pct,
                hurdle_rate=hurdle_rate, description=description)
    conn = get_connection()
    conn.execute(
        "INSERT INTO funds VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (fund.fund_id, name, vintage_year, size, focus, fund.status.value,
         fund.currency, management_fee_pct, carry_pct, hurdle_rate,
         fund.gp_commit_pct, description, fund.created_at)
    )
    conn.commit()
    conn.close()
    return fund


def add_lp(fund_id: str, lp_name: str, lp_type: LPType, commitment: float,
           contact_email: str = "", contact_name: str = "") -> LP:
    """Add a limited partner to a fund."""
    conn = get_connection()
    row = conn.execute("SELECT fund_id FROM funds WHERE fund_id=?", (fund_id,)).fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Fund {fund_id} not found")
    lp = LP(fund_id=fund_id, name=lp_name, lp_type=lp_type, commitment=commitment,
            contact_email=contact_email, contact_name=contact_name)
    conn.execute(
        "INSERT INTO lps VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (lp.lp_id, fund_id, lp_name, lp_type.value if isinstance(lp_type, LPType) else lp_type,
         commitment, 0.0, 0.0, 0.0, contact_email, contact_name, lp.created_at)
    )
    conn.commit()
    conn.close()
    return lp


def make_capital_call(fund_id: str, amount_per_lp: float, purpose: str,
                      call_date: Optional[str] = None, due_date: Optional[str] = None) -> List[CapitalCall]:
    """Issue a capital call to all LPs in a fund pro-rata."""
    conn = get_connection()
    fund = conn.execute("SELECT * FROM funds WHERE fund_id=?", (fund_id,)).fetchone()
    if not fund:
        conn.close()
        raise ValueError(f"Fund {fund_id} not found")
    lps = conn.execute("SELECT * FROM lps WHERE fund_id=?", (fund_id,)).fetchall()
    if not lps:
        conn.close()
        raise ValueError(f"No LPs found for fund {fund_id}")
    total_commitment = sum(lp["commitment"] for lp in lps)
    today = datetime.utcnow().isoformat()[:10]
    from datetime import timedelta, date
    due = due_date or (date.fromisoformat(call_date or today) + timedelta(days=10)).isoformat()
    calls = []
    for lp in lps:
        pro_rata = round((lp["commitment"] / total_commitment) * (amount_per_lp), 2) if total_commitment else 0
        call = CapitalCall(
            fund_id=fund_id, lp_id=lp["lp_id"], amount=pro_rata,
            call_date=call_date or today, due_date=due, purpose=purpose
        )
        conn.execute(
            "INSERT INTO capital_calls VALUES (?,?,?,?,?,?,?,?,?,?)",
            (call.call_id, fund_id, lp["lp_id"], pro_rata,
             call_date or today, due, purpose, "pending", None, call.created_at)
        )
        conn.execute(
            "UPDATE lps SET called_capital=called_capital+? WHERE lp_id=?",
            (pro_rata, lp["lp_id"])
        )
        calls.append(call)
    conn.commit()
    conn.close()
    return calls


def record_distribution(fund_id: str, lp_id: str, amount: float,
                        distribution_type: str = "realized", date: Optional[str] = None,
                        notes: str = "") -> Distribution:
    """Record a distribution to an LP."""
    conn = get_connection()
    row = conn.execute("SELECT lp_id FROM lps WHERE lp_id=? AND fund_id=?", (lp_id, fund_id)).fetchone()
    if not row:
        conn.close()
        raise ValueError(f"LP {lp_id} not found in fund {fund_id}")
    dist = Distribution(
        fund_id=fund_id, lp_id=lp_id, amount=amount,
        distribution_type=distribution_type,
        date=date or datetime.utcnow().isoformat()[:10],
        notes=notes
    )
    conn.execute(
        "INSERT INTO distributions VALUES (?,?,?,?,?,?,?,?)",
        (dist.dist_id, fund_id, lp_id, amount, distribution_type,
         dist.date, notes, dist.created_at)
    )
    conn.execute(
        "UPDATE lps SET distributions=distributions+? WHERE lp_id=?",
        (amount, lp_id)
    )
    conn.commit()
    conn.close()
    return dist


def update_nav(fund_id: str, lp_id: str, new_nav: float, as_of_date: Optional[str] = None,
               notes: str = "") -> bool:
    """Update the NAV for an LP's position."""
    conn = get_connection()
    row = conn.execute("SELECT nav FROM lps WHERE lp_id=? AND fund_id=?", (lp_id, fund_id)).fetchone()
    if not row:
        conn.close()
        raise ValueError(f"LP {lp_id} not found in fund {fund_id}")
    old_nav = row["nav"]
    conn.execute(
        "INSERT INTO nav_updates VALUES (?,?,?,?,?,?,?,?)",
        (str(uuid.uuid4()), fund_id, lp_id, old_nav, new_nav,
         as_of_date or datetime.utcnow().isoformat()[:10],
         datetime.utcnow().isoformat(), notes)
    )
    conn.execute("UPDATE lps SET nav=? WHERE lp_id=?", (new_nav, lp_id))
    conn.commit()
    conn.close()
    return True


def lp_statement(lp_id: str) -> dict:
    """Generate a full LP account statement."""
    conn = get_connection()
    lp = conn.execute("SELECT * FROM lps WHERE lp_id=?", (lp_id,)).fetchone()
    if not lp:
        conn.close()
        raise ValueError(f"LP {lp_id} not found")
    fund = conn.execute("SELECT * FROM funds WHERE fund_id=?", (lp["fund_id"],)).fetchone()
    calls = conn.execute(
        "SELECT * FROM capital_calls WHERE lp_id=? ORDER BY call_date", (lp_id,)
    ).fetchall()
    dists = conn.execute(
        "SELECT * FROM distributions WHERE lp_id=? ORDER BY date", (lp_id,)
    ).fetchall()
    nav_hist = conn.execute(
        "SELECT * FROM nav_updates WHERE lp_id=? ORDER BY as_of_date", (lp_id,)
    ).fetchall()
    conn.close()

    called = lp["called_capital"]
    distributions = lp["distributions"]
    nav = lp["nav"]
    dpi = round(distributions / called, 3) if called > 0 else 0.0
    rvpi = round(nav / called, 3) if called > 0 else 0.0
    tvpi = round(dpi + rvpi, 3)

    return {
        "lp_id": lp_id,
        "lp_name": lp["name"],
        "lp_type": lp["lp_type"],
        "fund_name": fund["name"] if fund else "Unknown",
        "fund_vintage": fund["vintage_year"] if fund else None,
        "commitment": lp["commitment"],
        "called_capital": called,
        "uncalled_capital": lp["commitment"] - called,
        "distributions": distributions,
        "nav": nav,
        "total_value": distributions + nav,
        "dpi": dpi,
        "rvpi": rvpi,
        "tvpi": tvpi,
        "capital_calls": [dict(c) for c in calls],
        "distributions_history": [dict(d) for d in dists],
        "nav_history": [dict(n) for n in nav_hist],
        "generated_at": datetime.utcnow().isoformat(),
    }


def fund_metrics(fund_id: str) -> dict:
    """Calculate fund-level metrics: TVPI, DPI, RVPI."""
    conn = get_connection()
    fund = conn.execute("SELECT * FROM funds WHERE fund_id=?", (fund_id,)).fetchone()
    if not fund:
        conn.close()
        raise ValueError(f"Fund {fund_id} not found")
    lps = conn.execute("SELECT * FROM lps WHERE fund_id=?", (fund_id,)).fetchall()
    calls = conn.execute("SELECT * FROM capital_calls WHERE fund_id=?", (fund_id,)).fetchall()
    conn.close()

    total_commitment = sum(lp["commitment"] for lp in lps)
    total_called = sum(lp["called_capital"] for lp in lps)
    total_distributions = sum(lp["distributions"] for lp in lps)
    total_nav = sum(lp["nav"] for lp in lps)
    total_value = total_distributions + total_nav

    dpi = round(total_distributions / total_called, 3) if total_called > 0 else 0.0
    rvpi = round(total_nav / total_called, 3) if total_called > 0 else 0.0
    tvpi = round(dpi + rvpi, 3)

    call_rate = round(total_called / total_commitment * 100, 1) if total_commitment > 0 else 0.0

    return {
        "fund_id": fund_id,
        "fund_name": fund["name"],
        "vintage_year": fund["vintage_year"],
        "fund_size": fund["size"],
        "focus": fund["focus"],
        "status": fund["status"],
        "lp_count": len(lps),
        "total_commitment": total_commitment,
        "total_called": total_called,
        "uncalled_capital": total_commitment - total_called,
        "call_rate_pct": call_rate,
        "total_distributions": total_distributions,
        "total_nav": total_nav,
        "total_value": total_value,
        "dpi": dpi,
        "rvpi": rvpi,
        "tvpi": tvpi,
        "management_fee_pct": fund["management_fee_pct"],
        "carry_pct": fund["carry_pct"],
        "hurdle_rate": fund["hurdle_rate"],
        "generated_at": datetime.utcnow().isoformat(),
    }


def generate_lp_report(lp_id: str) -> str:
    """Generate a printed LP statement."""
    stmt = lp_statement(lp_id)
    lines = [
        "=" * 65,
        "LP ACCOUNT STATEMENT",
        "=" * 65,
        f"LP Name       : {stmt['lp_name']}",
        f"LP Type       : {stmt['lp_type'].upper()}",
        f"Fund          : {stmt['fund_name']} ({stmt['fund_vintage']})",
        "",
        "CAPITAL ACCOUNT",
        "-" * 40,
        f"  Commitment       : ${stmt['commitment']:>15,.2f}",
        f"  Called Capital   : ${stmt['called_capital']:>15,.2f}",
        f"  Uncalled Capital : ${stmt['uncalled_capital']:>15,.2f}",
        f"  Distributions    : ${stmt['distributions']:>15,.2f}",
        f"  NAV              : ${stmt['nav']:>15,.2f}",
        f"  Total Value      : ${stmt['total_value']:>15,.2f}",
        "",
        "PERFORMANCE METRICS",
        "-" * 40,
        f"  DPI  (Distributions/Called) : {stmt['dpi']:.3f}x",
        f"  RVPI (NAV/Called)           : {stmt['rvpi']:.3f}x",
        f"  TVPI (Total/Called)         : {stmt['tvpi']:.3f}x",
        "",
        f"CAPITAL CALLS ({len(stmt['capital_calls'])})",
        "-" * 40,
    ]
    for c in stmt["capital_calls"]:
        lines.append(f"  {c['call_date']} | ${c['amount']:,.2f} | {c['purpose']} [{c['status'].upper()}]")
    lines += [
        "",
        f"DISTRIBUTIONS ({len(stmt['distributions_history'])})",
        "-" * 40,
    ]
    for d in stmt["distributions_history"]:
        lines.append(f"  {d['date']} | ${d['amount']:,.2f} | {d['distribution_type']}")
    lines += [
        "",
        f"Generated: {stmt['generated_at'][:19]}",
        "=" * 65,
    ]
    return "\n".join(lines)


def list_funds() -> List[dict]:
    """List all funds."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM funds ORDER BY vintage_year DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_lps(fund_id: str) -> List[dict]:
    """List all LPs for a fund."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM lps WHERE fund_id=? ORDER BY commitment DESC", (fund_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def cli():
    import sys
    if len(sys.argv) < 2:
        print("Usage: python lp_portal.py <command>")
        print("Commands: add-fund, list-funds, metrics, statement, report, list-lps")
        return
    init_db()
    cmd = sys.argv[1]
    if cmd == "list-funds":
        for f in list_funds():
            print(f"[{f['status'].upper()}] {f['name']} ({f['vintage_year']}) — ${f['size']:,.0f} — {f['focus']}")
    elif cmd == "metrics" and len(sys.argv) >= 3:
        m = fund_metrics(sys.argv[2])
        print(json.dumps(m, indent=2))
    elif cmd == "statement" and len(sys.argv) >= 3:
        stmt = lp_statement(sys.argv[2])
        print(json.dumps(stmt, indent=2))
    elif cmd == "report" and len(sys.argv) >= 3:
        print(generate_lp_report(sys.argv[2]))
    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    cli()
