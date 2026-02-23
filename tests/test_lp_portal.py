"""Tests for lp_portal.py"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import lp_portal as lp
lp.DB_PATH = Path("/tmp/test_lp_portal.db")


@pytest.fixture(autouse=True)
def clean_db():
    if lp.DB_PATH.exists():
        lp.DB_PATH.unlink()
    lp.init_db()
    yield
    if lp.DB_PATH.exists():
        lp.DB_PATH.unlink()


def make_fund(**kwargs):
    defaults = dict(name="BlackRoad Fund I", vintage_year=2024, size=50_000_000.0, focus="Early Stage Tech")
    defaults.update(kwargs)
    return lp.add_fund(**defaults)


def test_add_fund():
    fund = make_fund()
    assert fund.name == "BlackRoad Fund I"
    assert fund.status == lp.FundStatus.FUNDRAISING
    assert fund.size == 50_000_000.0


def test_add_lp():
    fund = make_fund()
    limited_partner = lp.add_lp(fund.fund_id, "State Pension Fund", lp.LPType.INSTITUTIONAL, 5_000_000.0)
    assert limited_partner.commitment == 5_000_000.0
    assert limited_partner.called_capital == 0.0


def test_capital_call():
    fund = make_fund()
    lp1 = lp.add_lp(fund.fund_id, "LP Alpha", lp.LPType.FAMILY_OFFICE, 2_000_000.0)
    lp2 = lp.add_lp(fund.fund_id, "LP Beta", lp.LPType.INSTITUTIONAL, 8_000_000.0)
    calls = lp.make_capital_call(fund.fund_id, 1_000_000.0, "Initial portfolio deployment")
    assert len(calls) == 2
    lps = lp.list_lps(fund.fund_id)
    total_called = sum(l["called_capital"] for l in lps)
    assert total_called == pytest.approx(1_000_000.0, rel=1e-3)


def test_record_distribution():
    fund = make_fund()
    lp_obj = lp.add_lp(fund.fund_id, "LP Gamma", lp.LPType.INDIVIDUAL, 1_000_000.0)
    lp.make_capital_call(fund.fund_id, 500_000.0, "Investment deployment")
    dist = lp.record_distribution(fund.fund_id, lp_obj.lp_id, 200_000.0, "realized", notes="Exit from Portfolio Co A")
    assert dist.amount == 200_000.0
    stmt = lp.lp_statement(lp_obj.lp_id)
    assert stmt["distributions"] == 200_000.0


def test_lp_metrics():
    fund = make_fund()
    lp_obj = lp.add_lp(fund.fund_id, "LP Delta", lp.LPType.CORPORATE, 2_000_000.0)
    lp.make_capital_call(fund.fund_id, 1_000_000.0, "Deployment")
    lp.record_distribution(fund.fund_id, lp_obj.lp_id, 500_000.0, "realized")
    lp.update_nav(fund.fund_id, lp_obj.lp_id, 800_000.0)
    stmt = lp.lp_statement(lp_obj.lp_id)
    assert stmt["dpi"] == pytest.approx(0.5, rel=0.05)
    assert stmt["rvpi"] == pytest.approx(0.8, rel=0.05)
    assert stmt["tvpi"] == pytest.approx(1.3, rel=0.05)


def test_fund_metrics():
    fund = make_fund()
    lp.add_lp(fund.fund_id, "LP1", lp.LPType.INSTITUTIONAL, 10_000_000.0)
    lp.add_lp(fund.fund_id, "LP2", lp.LPType.FAMILY_OFFICE, 5_000_000.0)
    metrics = lp.fund_metrics(fund.fund_id)
    assert metrics["lp_count"] == 2
    assert metrics["total_commitment"] == 15_000_000.0
    assert "tvpi" in metrics
    assert "dpi" in metrics


def test_update_nav():
    fund = make_fund()
    lp_obj = lp.add_lp(fund.fund_id, "LP NAV", lp.LPType.INDIVIDUAL, 1_000_000.0)
    result = lp.update_nav(fund.fund_id, lp_obj.lp_id, 1_200_000.0)
    assert result is True
    stmt = lp.lp_statement(lp_obj.lp_id)
    assert stmt["nav"] == 1_200_000.0


def test_generate_report():
    fund = make_fund()
    lp_obj = lp.add_lp(fund.fund_id, "Report LP", lp.LPType.INSTITUTIONAL, 3_000_000.0)
    report = lp.generate_lp_report(lp_obj.lp_id)
    assert "LP ACCOUNT STATEMENT" in report
    assert "Report LP" in report
    assert "DPI" in report


def test_list_funds():
    make_fund(name="Fund A", vintage_year=2022)
    make_fund(name="Fund B", vintage_year=2023)
    funds = lp.list_funds()
    assert len(funds) >= 2
