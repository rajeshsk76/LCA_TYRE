from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "engine" / "opentyre_lca"))

import pandas as pd
import streamlit as st

from opentyre_lca import calculate_lca, lci_records
from opentyre_lca.excel_import import (
    detect_workbook_structure,
    preview_sheet,
    extract_candidate_values,
    map_workbook_to_params,
)

st.set_page_config(page_title="LCA_TYRE Excel Mapping", page_icon="📘", layout="wide")

st.title("Excel workbook mapping")
st.caption("Upload your LCA workbook, detect sheets, extract assumptions, and convert them into TyreLCAParams.")

uploaded = st.file_uploader(
    "Upload LCA workbook (.xlsx)",
    type=["xlsx"],
)

if uploaded is None:
    st.info("Upload your LCA workbook to begin mapping.")
    st.stop()

try:
    structure = detect_workbook_structure(uploaded)
except Exception as exc:
    st.error(f"Could not read workbook: {exc}")
    st.stop()

st.success(f"Workbook loaded: {structure['sheet_count']} sheets detected.")

sheet_df = pd.DataFrame(
    [
        {"sheet": sheet, "classification": structure["classification"].get(sheet, "unknown")}
        for sheet in structure["sheets"]
    ]
)

left, right = st.columns([1, 1.3])

with left:
    st.subheader("Detected sheets")
    st.dataframe(sheet_df, use_container_width=True, hide_index=True)

with right:
    st.subheader("Sheet preview")
    selected_sheet = st.selectbox("Select sheet", structure["sheets"])
    try:
        preview_df = preview_sheet(uploaded, selected_sheet, nrows=40)
        st.dataframe(preview_df, use_container_width=True)
    except Exception as exc:
        st.warning(f"Could not preview sheet: {exc}")

st.divider()

tab_candidates, tab_mapping, tab_result = st.tabs(
    ["Candidate values", "Mapped assumptions", "Calculated result"]
)

with tab_candidates:
    st.subheader("Extracted candidate values")
    st.write(
        "The importer scans text labels and nearby numeric cells. This is transparent so you can check what it found."
    )

    candidates = extract_candidate_values(uploaded)
    cand_df = pd.DataFrame(candidates)

    if cand_df.empty:
        st.warning("No label-value candidates detected.")
    else:
        st.dataframe(cand_df, use_container_width=True, hide_index=True)

        st.download_button(
            "Download candidate values as CSV",
            cand_df.to_csv(index=False).encode("utf-8"),
            file_name="lca_tyre_excel_candidates.csv",
            mime="text/csv",
        )

with tab_mapping:
    st.subheader("Mapped assumptions")

    params, mapping_records = map_workbook_to_params(uploaded)
    mapping_df = pd.DataFrame(mapping_records)

    if mapping_df.empty:
        st.warning(
            "No assumptions were confidently mapped. You can still use candidate values to define exact mapping rules."
        )
    else:
        st.dataframe(mapping_df, use_container_width=True, hide_index=True)

        st.download_button(
            "Download mapped assumptions as CSV",
            mapping_df.to_csv(index=False).encode("utf-8"),
            file_name="lca_tyre_mapped_assumptions.csv",
            mime="text/csv",
        )

    st.info(
        "This mapping is an assistant layer, not a certified data import. Review each mapped value before using it for external claims."
    )

with tab_result:
    st.subheader("Result from mapped workbook assumptions")

    params, mapping_records = map_workbook_to_params(uploaded)
    result = calculate_lca(params)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("ELT feed", f"{result['annual_elt_t']:,.0f} t/y")
    k2.metric("Raw rCB", f"{result['raw_rcb_tpy']:,.0f} t/y")
    k3.metric("Net saving", f"{result['net_saving_tco2e_per_year']:,.0f} tCO₂e/y")
    k4.metric("Saving intensity", f"{result['net_saving_tco2e_per_t_elt']:.3f} tCO₂e/t ELT")

    result_df = pd.DataFrame([result])
    st.dataframe(result_df, use_container_width=True)

    st.subheader("LCI from mapped assumptions")
    lci_df = pd.DataFrame(lci_records(params))
    st.dataframe(lci_df, use_container_width=True, hide_index=True)

    st.download_button(
        "Download mapped LCI as CSV",
        lci_df.to_csv(index=False).encode("utf-8"),
        file_name="lca_tyre_mapped_lci.csv",
        mime="text/csv",
    )
