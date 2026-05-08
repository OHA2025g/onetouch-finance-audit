from app.services.ca_india_compliance_engine import compute_gst_checks, compute_tds_checks


def test_gst_checks_flags():
    c = compute_gst_checks(
        {
            "gstr1_sales": 100.0,
            "gstr3b_sales": 90.0,
            "gstr2b_purchases": 50.0,
            "purchase_register": 48.0,
            "itc_claimed": 10.0,
            "itc_eligible": 9.0,
            "gstr3b_output_tax_liability": 18.0,
            "books_output_tax_liability": 17.0,
        }
    )
    assert c["gstr1_vs_3b_sales_delta"] == 10.0
    assert c["flags"]["gstr1_vs_3b_material"] is True
    assert c["tax_liability_mismatch"] == 1.0
    assert c["flags"]["tax_liability_material"] is True


def test_tds_rate_mismatch():
    c = compute_tds_checks(
        {
            "ledger_tds": 100.0,
            "challan_tds": 80.0,
            "delayed_payment_days": 3,
            "expected_deduction_rate_pct": 10.0,
            "applied_deduction_rate_pct": 7.5,
        }
    )
    assert c["unpaid_tds"] == 20.0
    assert c["flags"]["delayed_payment"] is True
    assert c["deduction_rate_delta_pct"] == -2.5
    assert c["flags"]["rate_mismatch"] is True
