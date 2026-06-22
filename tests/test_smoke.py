import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine" / "opentyre_lca"))

from opentyre_lca import workbook_base_case, calculate_lca, mass_balance

class TestSmoke(unittest.TestCase):
    def test_base_case(self):
        p = workbook_base_case(False, False)
        r = calculate_lca(p)
        self.assertAlmostEqual(r["raw_rcb_tpy"], 21875.0, places=6)
        self.assertAlmostEqual(r["net_saving_tco2e_per_year"], 42077.025, places=3)
        self.assertAlmostEqual(r["net_saving_tco2e_per_t_elt"], 0.6732324, places=6)

    def test_deashing_mass(self):
        p = workbook_base_case(True, False)
        mb = mass_balance(p)
        self.assertAlmostEqual(mb["purified_rcb_tpy"], 18948.78125, places=3)

if __name__ == "__main__":
    unittest.main()
