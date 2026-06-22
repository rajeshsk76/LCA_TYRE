from pathlib import Path
import textwrap

ROOT = Path.cwd()

def write(path, text):
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")
    print("created", path)

dirs = [
    "engine/opentyre_lca/opentyre_lca",
    "data",
    "models",
    "web",
    "docs",
    "reports",
    "tests",
    "deployment",
]

for d in dirs:
    (ROOT / d).mkdir(parents=True, exist_ok=True)

write("README.md", """
# LCA_TYRE

Open engineering LCI/LCA platform for end-of-life tyre pyrolysis, recovered carbon black, deashing and circular carbon accounting.

Domain target: https://lca.calvyx.com

Status: early engineering model. Not certified ISO 14040/14044 LCA or EPD yet.

Emission factors are editable placeholders unless verified and referenced.

Install:

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -e engine/opentyre_lca
    pip install -r requirements.txt

Run tests:

    python -m unittest discover tests -v

Run dashboard:

    streamlit run web/streamlit_app.py
""")

write(".gitignore", """
.venv/
__pycache__/
*.pyc
.env
.env.*
*.log
.DS_Store
.pytest_cache/
reports/generated/
data/private/
.streamlit/secrets.toml
""")

write("LICENSE", """
MIT License

Copyright (c) 2026 Rajesh S. Kempegowda

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files to deal in the Software
without restriction.

THE SOFTWARE IS PROVIDED AS IS, WITHOUT WARRANTY OF ANY KIND.
""")

write("requirements.txt", """
pandas>=2.0
streamlit>=1.30
openpyxl>=3.1
""")

write("pyproject.toml", """
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "lca-tyre"
version = "0.1.0"
description = "Open engineering LCI/LCA platform for end-of-life tyre pyrolysis and recovered carbon black"
readme = "README.md"
requires-python = ">=3.11"
""")

write("engine/opentyre_lca/pyproject.toml", """
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "opentyre-lca"
version = "0.1.0"
description = "Tyre pyrolysis LCI/LCA calculation engine"
requires-python = ">=3.11"

[tool.setuptools.packages.find]
where = ["."]
include = ["opentyre_lca*"]
""")

write("engine/opentyre_lca/opentyre_lca/__init__.py", """
from .core import Flow
from .tyre_model import (
    DeashingParams,
    TyreLCAParams,
    update_params,
    mass_balance,
    build_lci,
    calculate_lca,
    lci_records,
    contribution_records,
    run_scenarios,
    workbook_base_case,
)
""")

write("engine/opentyre_lca/opentyre_lca/core.py", """
from dataclasses import dataclass

@dataclass(frozen=True)
class Flow:
    stage: str
    process: str
    item: str
    amount: float
    unit: str
    emission_factor_kg_per_unit: float
    factor_unit: str
    sign: int = 1
    source: str = ""
    notes: str = ""

    @property
    def impact_kgco2e(self) -> float:
        return self.amount * self.emission_factor_kg_per_unit * self.sign

    @property
    def impact_tco2e(self) -> float:
        return self.impact_kgco2e / 1000.0

    @property
    def direction(self) -> str:
        return "burden" if self.sign >= 0 else "credit"
""")

write("engine/opentyre_lca/opentyre_lca/tyre_model.py", """
from dataclasses import dataclass, field, replace
from typing import Dict, List, Union

from .core import Flow

Number = Union[int, float]

@dataclass
class DeashingParams:
    enabled: bool = False
    feed_fraction_of_raw_rcb: float = 1.0
    purified_yield_t_per_t_feed: float = 3.46492 / 4.0

    hno3_kg_per_t_feed: float = 39.3825
    naoh_kg_per_t_feed: float = 181.956
    electricity_kwh_per_t_feed: float = 166.306
    fresh_water_m3_per_t_feed: float = 5.0
    wastewater_m3_per_t_feed: float = 5.0

    hno3_ef_kgco2e_per_kg: float = 2.50
    naoh_ef_kgco2e_per_kg: float = 1.97
    electricity_ef_kgco2e_per_kwh: float = 0.0181
    water_ef_kgco2e_per_m3: float = 0.066
    wastewater_ef_kgco2e_per_m3: float = 0.55

    include_zinc_credit: bool = False
    zinc_recovered_kg_per_t_feed: float = 24.309
    zinc_oxide_avoided_ef_kgco2e_per_kg: float = 2.89

@dataclass
class TyreLCAParams:
    case_name: str = "Base"

    annual_elt_t: float = 62500.0
    rcb_yield_t_per_t_elt: float = 0.35

    virgin_cb_ef_tco2e_per_t: float = 2.37
    raw_rcb_pyrolysis_ef_tco2e_per_t: float = 0.605

    include_shipping_credit: bool = True
    avoided_shipping_tco2e_per_year: float = 3467.65

    include_oil_credit: bool = False
    oil_credit_tco2e_per_year: float = 4609.6872

    substitution_ratio_t_virgin_cb_per_t_rcb_product: float = 1.0
    deashing: DeashingParams = field(default_factory=DeashingParams)

def update_params(params: TyreLCAParams, **changes) -> TyreLCAParams:
    main = {}
    deashing = {}
    for key, value in changes.items():
        if key.startswith("deashing__"):
            deashing[key.replace("deashing__", "", 1)] = value
        else:
            main[key] = value
    new_deashing = replace(params.deashing, **deashing) if deashing else params.deashing
    return replace(params, deashing=new_deashing, **main)

def mass_balance(params: TyreLCAParams) -> Dict[str, float]:
    raw_rcb_tpy = params.annual_elt_t * params.rcb_yield_t_per_t_elt

    if params.deashing.enabled:
        deashing_feed_tpy = raw_rcb_tpy * params.deashing.feed_fraction_of_raw_rcb
        raw_rcb_sold_tpy = raw_rcb_tpy - deashing_feed_tpy
        purified_rcb_tpy = deashing_feed_tpy * params.deashing.purified_yield_t_per_t_feed
        cb_product_tpy = raw_rcb_sold_tpy + purified_rcb_tpy
    else:
        deashing_feed_tpy = 0.0
        raw_rcb_sold_tpy = raw_rcb_tpy
        purified_rcb_tpy = 0.0
        cb_product_tpy = raw_rcb_tpy

    virgin_cb_avoided_tpy = cb_product_tpy * params.substitution_ratio_t_virgin_cb_per_t_rcb_product

    return {
        "annual_elt_t": params.annual_elt_t,
        "raw_rcb_tpy": raw_rcb_tpy,
        "deashing_feed_tpy": deashing_feed_tpy,
        "raw_rcb_sold_without_deashing_tpy": raw_rcb_sold_tpy,
        "purified_rcb_tpy": purified_rcb_tpy,
        "cb_product_for_substitution_tpy": cb_product_tpy,
        "virgin_cb_avoided_tpy": virgin_cb_avoided_tpy,
    }

def build_lci(params: TyreLCAParams) -> List[Flow]:
    mb = mass_balance(params)
    flows = []

    flows.append(Flow(
        stage="Pyrolysis",
        process="Tyre pyrolysis",
        item="Raw rCB production emissions",
        amount=mb["raw_rcb_tpy"],
        unit="t raw rCB/year",
        emission_factor_kg_per_unit=params.raw_rcb_pyrolysis_ef_tco2e_per_t * 1000.0,
        factor_unit="kg CO2e/t raw rCB",
        sign=1,
        source="placeholder",
        notes="Replace with verified plant LCI."
    ))

    flows.append(Flow(
        stage="Product substitution",
        process="Avoided virgin carbon black",
        item="Virgin carbon black avoided",
        amount=mb["virgin_cb_avoided_tpy"],
        unit="t virgin CB/year",
        emission_factor_kg_per_unit=params.virgin_cb_ef_tco2e_per_t * 1000.0,
        factor_unit="kg CO2e/t virgin CB",
        sign=-1,
        source="placeholder",
        notes="Replace with verified LCI/EPD."
    ))

    if params.include_shipping_credit:
        flows.append(Flow(
            stage="Avoided logistics",
            process="Avoided shipping",
            item="Avoided ELT shipping",
            amount=1.0,
            unit="year",
            emission_factor_kg_per_unit=params.avoided_shipping_tco2e_per_year * 1000.0,
            factor_unit="kg CO2e/year",
            sign=-1,
            source="placeholder"
        ))

    if params.include_oil_credit:
        flows.append(Flow(
            stage="Co-product credit",
            process="Pyrolysis oil substitution",
            item="Avoided fuel",
            amount=1.0,
            unit="year",
            emission_factor_kg_per_unit=params.oil_credit_tco2e_per_year * 1000.0,
            factor_unit="kg CO2e/year",
            sign=-1,
            source="placeholder"
        ))

    d = params.deashing
    if d.enabled:
        feed = mb["deashing_feed_tpy"]
        items = [
            ("Nitric acid", feed * d.hno3_kg_per_t_feed, "kg HNO3/year", d.hno3_ef_kgco2e_per_kg, "kg CO2e/kg HNO3"),
            ("Sodium hydroxide", feed * d.naoh_kg_per_t_feed, "kg NaOH/year", d.naoh_ef_kgco2e_per_kg, "kg CO2e/kg NaOH"),
            ("Electricity", feed * d.electricity_kwh_per_t_feed, "kWh/year", d.electricity_ef_kgco2e_per_kwh, "kg CO2e/kWh"),
            ("Fresh water", feed * d.fresh_water_m3_per_t_feed, "m3/year", d.water_ef_kgco2e_per_m3, "kg CO2e/m3"),
            ("Wastewater treatment", feed * d.wastewater_m3_per_t_feed, "m3/year", d.wastewater_ef_kgco2e_per_m3, "kg CO2e/m3"),
        ]
        for item, amount, unit, ef, factor_unit in items:
            flows.append(Flow("Deashing", "rCB demineralisation", item, amount, unit, ef, factor_unit, 1, "placeholder"))

        if d.include_zinc_credit:
            flows.append(Flow(
                "Recovered minerals",
                "Zinc recovery",
                "Avoided zinc oxide production",
                feed * d.zinc_recovered_kg_per_t_feed,
                "kg ZnO-equivalent/year",
                d.zinc_oxide_avoided_ef_kgco2e_per_kg,
                "kg CO2e/kg ZnO",
                -1,
                "placeholder"
            ))

    return flows

def calculate_lca(params: TyreLCAParams) -> Dict[str, float]:
    mb = mass_balance(params)
    flows = build_lci(params)

    burdens_t = sum(f.impact_tco2e for f in flows if f.sign >= 0)
    credits_t = -sum(f.impact_tco2e for f in flows if f.sign < 0)
    net_impact_t = burdens_t - credits_t
    net_saving_t = -net_impact_t

    return {
        **mb,
        "gross_burdens_tco2e_per_year": burdens_t,
        "gross_credits_tco2e_per_year": credits_t,
        "net_impact_tco2e_per_year": net_impact_t,
        "net_saving_tco2e_per_year": net_saving_t,
        "net_saving_tco2e_per_t_elt": net_saving_t / mb["annual_elt_t"] if mb["annual_elt_t"] else 0.0,
    }

def lci_records(params: TyreLCAParams) -> List[dict]:
    rows = []
    for f in build_lci(params):
        rows.append({
            "case": params.case_name,
            "stage": f.stage,
            "process": f.process,
            "item": f.item,
            "direction": f.direction,
            "amount": f.amount,
            "unit": f.unit,
            "emission_factor": f.emission_factor_kg_per_unit,
            "factor_unit": f.factor_unit,
            "impact_tco2e_per_year": f.impact_tco2e,
            "source": f.source,
            "notes": f.notes,
        })
    return rows

def contribution_records(params: TyreLCAParams, group_by: str = "stage") -> List[dict]:
    totals = {}
    for row in lci_records(params):
        key = row[group_by]
        totals[key] = totals.get(key, 0.0) + row["impact_tco2e_per_year"]
    return [{group_by: k, "impact_tco2e_per_year": v} for k, v in sorted(totals.items())]

def run_scenarios(base_params: TyreLCAParams, scenarios: Dict[str, Dict[str, Number]]) -> List[dict]:
    rows = []
    for name, changes in scenarios.items():
        p = update_params(base_params, case_name=name, **changes)
        rows.append({"case": name, **calculate_lca(p)})
    return rows

def workbook_base_case(include_deashing: bool = False, include_oil_credit: bool = False) -> TyreLCAParams:
    return TyreLCAParams(
        include_oil_credit=include_oil_credit,
        deashing=DeashingParams(enabled=include_deashing),
    )
""")

write("tests/test_smoke.py", """
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
""")

write("data/lci_factors_template.csv", """
key,name,region,unit,impact_category,factor_kgco2e_per_unit,source,license,notes
virgin_carbon_black,Virgin carbon black,GLO,kg,GWP100,2.37,placeholder,to_verify,Replace with verified LCI/EPD
raw_rcb_pyrolysis,Raw recovered carbon black production,NOR,kg,GWP100,0.605,placeholder,to_verify,Allocated burden per kg raw rCB
nitric_acid,Nitric acid,GLO,kg,GWP100,2.50,placeholder,to_verify,Replace with verified LCI
sodium_hydroxide,Sodium hydroxide,GLO,kg,GWP100,1.97,placeholder,to_verify,Replace with verified LCI
electricity,Electricity grid,NOR,kWh,GWP100,0.0181,placeholder,to_verify,Norway electricity placeholder
water_supply,Fresh water supply,GLO,m3,GWP100,0.066,placeholder,to_verify,Replace with local factor
wastewater_treatment,Wastewater treatment,GLO,m3,GWP100,0.55,placeholder,to_verify,Replace with local factor
zinc_oxide,Zinc oxide production,GLO,kg,GWP100,2.89,placeholder,to_verify,Optional zinc credit
""")

write("data/tyre_inventory_template.csv", "parameter,value,unit,source,notes\nannual_elt_feed,62500,t/year,engineering_model,base value\nraw_rcb_yield,0.35,t/t ELT,engineering_model,base value\n")
write("data/transport_routes_template.csv", "route_id,origin,destination,mode,distance_km,mass_t,ef_kgco2e_per_tkm,source,notes\nplaceholder,Norway,TBD,ship,0,62500,0,placeholder,to update\n")
write("data/references_template.csv", "id,title,owner,year,url,notes\nREF001,Placeholder,TBD,TBD,TBD,replace\n")

for m in ["pyrolysis_rcb", "deashing", "transport", "oil_substitution", "asphalt_substitution"]:
    write(f"models/{m}.py", f"# Placeholder for {m} model.\\n")

write("web/streamlit_app.py", """
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine" / "opentyre_lca"))

import pandas as pd
import streamlit as st

from opentyre_lca import workbook_base_case, calculate_lca, lci_records, contribution_records
from opentyre_lca.tyre_model import update_params

st.set_page_config(page_title="LCA_TYRE", layout="wide")
st.title("LCA_TYRE")

with st.sidebar:
    annual_elt_t = st.number_input("Annual ELT feed, t/y", value=62500.0)
    rcb_yield = st.number_input("Raw rCB yield, t/t ELT", value=0.35)
    include_deashing = st.checkbox("Enable deashing", value=False)
    include_oil = st.checkbox("Include oil credit", value=False)

p = workbook_base_case(include_deashing=include_deashing, include_oil_credit=include_oil)
p = update_params(p, annual_elt_t=annual_elt_t, rcb_yield_t_per_t_elt=rcb_yield)

r = calculate_lca(p)

c1, c2, c3 = st.columns(3)
c1.metric("Raw rCB", f"{r['raw_rcb_tpy']:,.0f} t/y")
c2.metric("Net saving", f"{r['net_saving_tco2e_per_year']:,.0f} tCO2e/y")
c3.metric("Saving per ELT", f"{r['net_saving_tco2e_per_t_elt']:.3f} tCO2e/t")

st.subheader("LCI")
st.dataframe(pd.DataFrame(lci_records(p)), use_container_width=True)

st.subheader("Contribution")
contrib = pd.DataFrame(contribution_records(p))
st.dataframe(contrib, use_container_width=True)
""")

write("docs/methodology.md", "# Methodology\\n\\nOpen engineering LCI/LCA model. Initial category: GWP100.\\n")
write("docs/system_boundary.md", "# System Boundary\\n\\nELT pyrolysis, rCB, deashing, substitution credits, avoided shipping, optional oil credit.\\n")
write("docs/assumptions.md", "# Assumptions\\n\\nAll emission factors are placeholders unless verified.\\n")
write("docs/data_sources.md", "# Data Sources\\n\\nTrack references, licenses, regions, and data quality here.\\n")
write("docs/validation.md", "# Validation\\n\\nInitial validation by unit tests and workbook comparison.\\n")
write("reports/README.md", "# Reports\\n\\nGenerated reports go here.\\n")
write("deployment/README.md", "# Deployment\\n\\nTarget path: /opt/lca_tyre. Target domain: lca.calvyx.com.\\n")
write("deployment/lca-tyre.service.template", "[Unit]\\nDescription=LCA_TYRE dashboard\\n")
write("deployment/nginx-lca.calvyx.com.template", "server {\\n    server_name lca.calvyx.com;\\n}\\n")

print("\\nClean LCA_TYRE scaffold created.")
