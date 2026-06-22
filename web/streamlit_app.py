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
