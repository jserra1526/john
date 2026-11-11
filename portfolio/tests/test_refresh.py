"""Offline test of refresh.py using a fake data source. Run: python -m pytest tests (from the portfolio folder)."""
import datetime as dt
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import refresh as R  # noqa: E402
from openpyxl import load_workbook  # noqa: E402

D = dt.date
CSV = """Date,Reference,Details,Debit($),Credit($),Balance($)
14/08/2025,C123456,S 40 CBA @ 172.300000,,6872.05,6872.05
20/01/2025,C123400,B 150 WES @ 70.250000,10557.45,,0.00
15/01/2025,,Direct Credit 123456 COMMONWEALTH SEC,,10557.45,10557.45
12/02/2024,C120000,B 100 CBA @ 118.400000,11859.95,,0.00
"""


class Fake:
    def price(self, code):
        return {"CBA.AX": 170.0, "WES.AX": 82.0}[code], D(2026, 11, 10)

    def name(self, code):
        return None

    def dividends(self, code):
        return {"CBA.AX": [(D(2023, 8, 16), 2.40), (D(2024, 2, 13), 2.15), (D(2025, 8, 13), 2.60), (D(2027, 1, 1), 9.0)],
                "WES.AX": [(D(2025, 2, 18), 0.95)]}[code]


def test_parse_trade():
    assert R.parse_trade("B 1,000 VAS @ 101.500000") == ("Buy", 1000.0, "VAS", 101.5)
    assert R.parse_trade("S 40 CBA @ 172.30") == ("Sell", 40.0, "CBA", 172.3)
    assert R.parse_trade("Direct Credit 123") is None


def test_entitlement_rule():
    ex = D(2025, 8, 13)  # Wednesday
    assert R.entitled(D(2025, 8, 14), ex)        # settled day after ex -> traded before ex
    assert not R.entitled(D(2025, 8, 15), ex)
    assert R.entitled(D(2025, 8, 18), D(2025, 8, 15))  # Friday ex-date, Monday settlement


def test_refresh_end_to_end(tmp_path):
    exports = tmp_path / "CommSec Exports"
    exports.mkdir()
    (exports / "a.csv").write_text(CSV)
    (exports / "b.csv").write_text(CSV)  # duplicate export must not double count
    wbp = tmp_path / "share-portfolio-tracker.xlsx"
    for _ in range(2):  # second run must be identical (idempotent)
        res = R.refresh(wbp, exports, Fake(), today=D(2026, 11, 11), log=lambda *a: None)
    assert res["trades"] == 3 and res["shares"] == 2 and res["auto"] == 3
    d = load_workbook(wbp)["Dividends"]
    rows = [(d.cell(r, 1).value.date(), d.cell(r, 2).value, d.cell(r, 3).value) for r in range(5, 8)]
    assert rows == [(D(2024, 2, 13), "CBA", 100), (D(2025, 2, 18), "WES", 150), (D(2025, 8, 13), "CBA", 60)]
    assert d.cell(8, 2).value is None
