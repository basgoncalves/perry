import unittest
import numpy as np
import pandas as pd
import build


class BuildTests(unittest.TestCase):
    def test_pick_shares(self):
        self.assertEqual(build.pick_shares(100, 10_100, 100), 100)
        self.assertAlmostEqual(build.pick_shares(50, 10_000, 100), 100)
        self.assertIsNone(build.pick_shares(None, None, 1))

    def test_build_end_to_end(self):
        idx = pd.bdate_range(end="2026-11-05", periods=1300)
        closes = pd.DataFrame({"NVDA": np.linspace(50, 200, 1300),
                               "MSFT": np.linspace(300, 500, 1300)}, index=idx)
        closes.loc[idx[:100], "MSFT"] = np.nan   # listed late -> trimmed
        d = build.build(closes, {"NVDA": {"sharesOutstanding": 10, "marketCap": 2000},
                                 "MSFT": {"marketCap": 5000}})
        self.assertEqual([t["s"] for t in d["tiles"]], ["MSFT", "NVDA"])
        self.assertEqual(d["tiles"][0]["sec"], "Technology")
        first = pd.Timestamp(d["total"][0][0])
        self.assertGreaterEqual(first, idx[100])
        # last point = 200*10 + 500*10, in billions
        self.assertAlmostEqual(d["total"][-1][1], round(7000 / 1e9, 1))
        # older than 2y is weekly
        gaps = pd.Series(pd.to_datetime([p[0] for p in d["total"]])).diff().dt.days
        self.assertGreaterEqual(gaps.iloc[1], 5)
        files = build.stock_files(closes, d)
        self.assertEqual(set(files), {"NVDA", "MSFT"})
        self.assertEqual(files["NVDA"]["px"][-1], ["2026-11-05", 200.0])
        self.assertEqual(files["NVDA"]["n"], "Nvidia")


if __name__ == "__main__":
    unittest.main()
