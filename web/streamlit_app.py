from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine" / "opentyre_lca"))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from opentyre_lca import (
    workbook_base_case,
    calculate_lca,
    lci_records,
    contribution_records,
    run_scenarios,
)
from opentyre_lca.tyre_model import update_params
from opentyre_lca.reporting import build_customer_workbook


# ------------------------------------------------------------
# Page config
# ------------------------------------------------------------

st.set_page_config(
    page_title="LCA_TYRE",
    page_icon="♻️",
    layout="wide",
)

st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.4rem;
        font-weight: 800;
        margin-bottom: 0rem;
    }
    .subtitle {
        color: #6b7280;
        font-size: 1.05rem;
        margin-top: 0rem;
        margin-bottom: 1.2rem;
    }
    .small-note {
        color: #6b7280;
        font-size: 0.85rem;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.55rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="main-title">LCA_TYRE</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">Open engineering LCI/LCA dashboard for end-of-life tyre pyrolysis, recovered carbon black, deashing and circular carbon accounting.</div>',
    unsafe_allow_html=True,
)


# ------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------

def make_sankey(result: dict, include_deashing: bool, include_oil: bool) -> go.Figure:
    """Create simple material-credit Sankey for the current case."""

    raw_rcb = result["raw_rcb_tpy"]
    purified_rcb = result["purified_rcb_tpy"]
    cb_product = result["cb_product_for_substitution_tpy"]
    virgin_avoided = result["virgin_cb_avoided_tpy"]

    burden = result["gross_burdens_tco2e_per_year"]
    credit = result["gross_credits_tco2e_per_year"]
    saving = max(result["net_saving_tco2e_per_year"], 0)

    labels = [
        "ELT feed",
        "Tyre pyrolysis",
        "Raw rCB",
        "rCB product",
        "Virgin CB avoided",
        "Gross burdens",
        "Gross credits",
        "Net saving",
    ]

    source = [0, 1, 2, 3, 1, 4, 5, 6]
    target = [1, 2, 3, 4, 5, 6, 7, 7]
    value = [
        result["annual_elt_t"],
        raw_rcb,
        cb_product,
        virgin_avoided,
        burden,
        credit,
        burden,
        saving,
    ]

    if include_deashing:
        labels.insert(3, "Deashing")
        labels.insert(4, "Purified rCB")

        # Rebuild with deashing path
        source = [0, 1, 2, 3, 4, 5, 1, 6, 7, 8]
        target = [1, 2, 3, 4, 5, 6, 7, 8, 9, 9]
        value = [
            result["annual_elt_t"],
            raw_rcb,
            result["deashing_feed_tpy"],
            purified_rcb,
            cb_product,
            virgin_avoided,
            burden,
            credit,
            burden,
            saving,
        ]

        labels = [
            "ELT feed",
            "Tyre pyrolysis",
            "Raw rCB",
            "Deashing",
            "Purified rCB",
            "rCB product",
            "Virgin CB avoided",
            "Gross burdens",
            "Gross credits",
            "Net saving",
        ]

    if include_oil:
        labels.append("Oil credit included")

    fig = go.Figure(
        data=[
            go.Sankey(
                arrangement="snap",
                node=dict(
                    pad=18,
                    thickness=18,
                    line=dict(width=0.4),
                    label=labels,
                ),
                link=dict(
                    source=source,
                    target=target,
                    value=value,
                ),
            )
        ]
    )

    fig.update_layout(
        title_text="Material and climate-credit flow",
        font_size=12,
        height=520,
        margin=dict(l=10, r=10, t=50, b=10),
    )
    return fig


def make_waterfall_like_df(lci_df: pd.DataFrame) -> pd.DataFrame:
    """Prepare ordered contribution table for charting."""
    df = lci_df.copy()
    if df.empty:
        return df
    df["absolute_impact"] = df["impact_tco2e_per_year"].abs()
    df = df.sort_values("absolute_impact", ascending=False)
    return df


# ------------------------------------------------------------
# Sidebar inputs
# ------------------------------------------------------------

with st.sidebar:
    st.header("Model inputs")

    st.subheader("Plant basis")
    annual_elt_t = st.number_input(
        "Annual ELT feed, t/y",
        min_value=0.0,
        value=62500.0,
        step=1000.0,
    )
    rcb_yield = st.number_input(
        "Raw rCB yield, t/t ELT",
        min_value=0.0,
        max_value=1.0,
        value=0.35,
        step=0.01,
        format="%.3f",
    )

    st.subheader("LCI factors")
    virgin_cb_ef = st.number_input(
        "Virgin carbon black EF, tCO₂e/t",
        min_value=0.0,
        value=2.37,
        step=0.05,
        format="%.3f",
    )
    raw_rcb_ef = st.number_input(
        "Raw rCB pyrolysis EF, tCO₂e/t",
        min_value=0.0,
        value=0.605,
        step=0.05,
        format="%.3f",
    )

    st.subheader("Credits")
    include_shipping = st.checkbox("Include avoided shipping credit", value=True)
    shipping_credit = st.number_input(
        "Avoided shipping, tCO₂e/y",
        min_value=0.0,
        value=3467.65,
        step=100.0,
    )

    include_oil = st.checkbox("Include pyrolysis oil credit", value=False)
    oil_credit = st.number_input(
        "Oil substitution credit, tCO₂e/y",
        min_value=0.0,
        value=4609.6872,
        step=100.0,
    )

    st.subheader("Deashing")
    include_deashing = st.checkbox("Enable deashing", value=False)
    purified_yield = st.number_input(
        "Purified rCB yield, t/t CBp",
        min_value=0.0,
        max_value=1.0,
        value=3.46492 / 4.0,
        step=0.01,
        format="%.4f",
    )
    hno3 = st.number_input(
        "HNO₃, kg/t CBp feed",
        min_value=0.0,
        value=39.3825,
        step=1.0,
    )
    naoh = st.number_input(
        "NaOH, kg/t CBp feed",
        min_value=0.0,
        value=181.956,
        step=5.0,
    )
    electricity = st.number_input(
        "Electricity, kWh/t CBp feed",
        min_value=0.0,
        value=166.306,
        step=5.0,
    )
    include_zinc_credit = st.checkbox("Include zinc recovery credit", value=False)

    st.divider()
    st.caption("All emission factors are placeholders unless verified and referenced.")


# ------------------------------------------------------------
# Build case
# ------------------------------------------------------------

params = workbook_base_case(
    include_deashing=include_deashing,
    include_oil_credit=include_oil,
)

params = update_params(
    params,
    case_name="Dashboard case",
    annual_elt_t=annual_elt_t,
    rcb_yield_t_per_t_elt=rcb_yield,
    virgin_cb_ef_tco2e_per_t=virgin_cb_ef,
    raw_rcb_pyrolysis_ef_tco2e_per_t=raw_rcb_ef,
    include_shipping_credit=include_shipping,
    avoided_shipping_tco2e_per_year=shipping_credit,
    include_oil_credit=include_oil,
    oil_credit_tco2e_per_year=oil_credit,
    deashing__enabled=include_deashing,
    deashing__purified_yield_t_per_t_feed=purified_yield,
    deashing__hno3_kg_per_t_feed=hno3,
    deashing__naoh_kg_per_t_feed=naoh,
    deashing__electricity_kwh_per_t_feed=electricity,
    deashing__include_zinc_credit=include_zinc_credit,
)

result = calculate_lca(params)
lci_df = pd.DataFrame(lci_records(params))
contrib_df = pd.DataFrame(contribution_records(params, group_by="stage"))


# ------------------------------------------------------------
# KPI row
# ------------------------------------------------------------

k1, k2, k3, k4, k5 = st.columns(5)

k1.metric("ELT feed", f"{result['annual_elt_t']:,.0f} t/y")
k2.metric("Raw rCB", f"{result['raw_rcb_tpy']:,.0f} t/y")
k3.metric("rCB product", f"{result['cb_product_for_substitution_tpy']:,.0f} t/y")
k4.metric("Net saving", f"{result['net_saving_tco2e_per_year']:,.0f} tCO₂e/y")
k5.metric("Saving intensity", f"{result['net_saving_tco2e_per_t_elt']:.3f} tCO₂e/t ELT")


# ------------------------------------------------------------
# Scenarios
# ------------------------------------------------------------

scenario_definitions = {
    "Base rCB + shipping": {
        "deashing__enabled": False,
        "include_oil_credit": False,
        "include_shipping_credit": True,
    },
    "Base + oil credit": {
        "deashing__enabled": False,
        "include_oil_credit": True,
        "include_shipping_credit": True,
    },
    "With deashing": {
        "deashing__enabled": True,
        "include_oil_credit": False,
        "include_shipping_credit": True,
    },
    "Deashing + oil": {
        "deashing__enabled": True,
        "include_oil_credit": True,
        "include_shipping_credit": True,
    },
    "No shipping credit": {
        "deashing__enabled": include_deashing,
        "include_oil_credit": include_oil,
        "include_shipping_credit": False,
    },
    "Optimised deashing": {
        "deashing__enabled": True,
        "include_oil_credit": True,
        "include_shipping_credit": True,
        "deashing__hno3_kg_per_t_feed": 30.0,
        "deashing__naoh_kg_per_t_feed": 130.0,
        "deashing__electricity_kwh_per_t_feed": 120.0,
        "deashing__include_zinc_credit": True,
    },
}


scenario_df = pd.DataFrame(run_scenarios(params, scenario_definitions))

# ------------------------------------------------------------
# Customer Excel report export
# ------------------------------------------------------------

report_bytes = build_customer_workbook(
    params,
    scenario_definitions=scenario_definitions,
    customer_name="Customer",
    project_name="End-of-life tyre LCA screening",
    prepared_by="LCA_TYRE / Calvyx",
)

st.download_button(
    label="📥 Download customer Excel report",
    data=report_bytes,
    file_name="LCA_TYRE_customer_report.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)



# ------------------------------------------------------------
# Tabs
# ------------------------------------------------------------

tab_overview, tab_flow, tab_scenarios, tab_lci, tab_excel, tab_method = st.tabs(
    ["Overview", "Flow Sankey", "Scenarios", "LCI table", "Excel import", "Methodology"]
)


with tab_overview:
    left, right = st.columns([1.2, 1])

    with left:
        st.subheader("Life-cycle contribution by stage")
        if not contrib_df.empty:
            st.bar_chart(contrib_df.set_index("stage")[["impact_tco2e_per_year"]])
        else:
            st.info("No contribution data available.")

    with right:
        st.subheader("Burden vs credit")
        burden_credit = pd.DataFrame(
            {
                "category": ["Gross burdens", "Gross credits", "Net saving"],
                "tCO2e_per_year": [
                    result["gross_burdens_tco2e_per_year"],
                    result["gross_credits_tco2e_per_year"],
                    result["net_saving_tco2e_per_year"],
                ],
            }
        )
        st.bar_chart(burden_credit.set_index("category"))

    st.divider()

    st.subheader("Top LCI contributors")
    top_df = make_waterfall_like_df(lci_df).head(10)
    if not top_df.empty:
        st.bar_chart(top_df.set_index("item")[["impact_tco2e_per_year"]])

    st.subheader("Key calculated values")
    summary_rows = {
        "Annual ELT feed, t/y": result["annual_elt_t"],
        "Raw rCB production, t/y": result["raw_rcb_tpy"],
        "Purified rCB, t/y": result["purified_rcb_tpy"],
        "Carbon black product for substitution, t/y": result["cb_product_for_substitution_tpy"],
        "Virgin carbon black avoided, t/y": result["virgin_cb_avoided_tpy"],
        "Gross burdens, tCO₂e/y": result["gross_burdens_tco2e_per_year"],
        "Gross credits, tCO₂e/y": result["gross_credits_tco2e_per_year"],
        "Net impact, tCO₂e/y": result["net_impact_tco2e_per_year"],
        "Net saving, tCO₂e/y": result["net_saving_tco2e_per_year"],
        "Net saving, tCO₂e/t ELT": result["net_saving_tco2e_per_t_elt"],
    }
    st.dataframe(
        pd.DataFrame([{"metric": k, "value": v} for k, v in summary_rows.items()]),
        use_container_width=True,
        hide_index=True,
    )


with tab_flow:
    st.subheader("Material and climate-credit flow")
    st.plotly_chart(
        make_sankey(result, include_deashing=include_deashing, include_oil=include_oil),
        use_container_width=True,
    )

    st.info(
        "The Sankey is a screening visualisation. It mixes material flows and climate-credit magnitudes, so it should be used for communication, not as a strict physical balance diagram."
    )


with tab_scenarios:
    st.subheader("Scenario comparison")

    scenario_view = scenario_df[
        [
            "case",
            "gross_burdens_tco2e_per_year",
            "gross_credits_tco2e_per_year",
            "net_saving_tco2e_per_year",
            "net_saving_tco2e_per_t_elt",
            "raw_rcb_tpy",
            "purified_rcb_tpy",
        ]
    ].copy()

    st.dataframe(scenario_view, use_container_width=True, hide_index=True)

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("#### Net saving by scenario")
        st.bar_chart(scenario_view.set_index("case")[["net_saving_tco2e_per_year"]])

    with c2:
        st.markdown("#### Saving intensity by scenario")
        st.bar_chart(scenario_view.set_index("case")[["net_saving_tco2e_per_t_elt"]])

    st.download_button(
        "Download scenario results as CSV",
        scenario_view.to_csv(index=False).encode("utf-8"),
        file_name="lca_tyre_scenario_results.csv",
        mime="text/csv",
    )


with tab_lci:
    st.subheader("Life-cycle inventory")

    if not lci_df.empty:
        filter_stage = st.multiselect(
            "Filter by stage",
            options=sorted(lci_df["stage"].unique()),
            default=sorted(lci_df["stage"].unique()),
        )
        filtered_lci = lci_df[lci_df["stage"].isin(filter_stage)] if filter_stage else lci_df
    else:
        filtered_lci = lci_df

    st.dataframe(filtered_lci, use_container_width=True, hide_index=True)

    st.download_button(
        "Download LCI as CSV",
        filtered_lci.to_csv(index=False).encode("utf-8"),
        file_name="lca_tyre_lci.csv",
        mime="text/csv",
    )


with tab_excel:
    st.subheader("Excel workbook import / preview")

    uploaded = st.file_uploader(
        "Upload LCA workbook (.xlsx)",
        type=["xlsx"],
        help="This first version previews sheets. Later we will map exact workbook cells into model inputs.",
    )

    if uploaded is None:
        st.info("Upload your LCA workbook to inspect sheets and preview data.")
    else:
        try:
            xls = pd.ExcelFile(uploaded)
            st.success(f"Workbook loaded. Sheets found: {len(xls.sheet_names)}")

            selected_sheet = st.selectbox("Select sheet", xls.sheet_names)
            preview_df = pd.read_excel(uploaded, sheet_name=selected_sheet, nrows=50)

            st.markdown("#### Sheet preview")
            st.dataframe(preview_df, use_container_width=True)

            sheet_summary = pd.DataFrame(
                {
                    "sheet": xls.sheet_names,
                }
            )
            st.markdown("#### Workbook sheet list")
            st.dataframe(sheet_summary, use_container_width=True, hide_index=True)

            st.warning(
                "Next development step: map known workbook sheets such as summary, ELT, LCI-inventory and deashing directly into TyreLCAParams."
            )

        except Exception as exc:
            st.error(f"Could not read workbook: {exc}")


with tab_method:
    st.subheader("Goal and scope")
    st.write(
        """
        This dashboard is an open engineering LCI/LCA calculator for end-of-life tyre
        pyrolysis pathways. It is intended for scenario screening, model development,
        and transparent carbon accounting.
        """
    )

    st.subheader("Functional unit")
    st.write(
        """
        The current functional unit is annual treatment of end-of-life tyres, with
        results normalised per tonne of ELT input.
        """
    )

    st.subheader("Included in this version")
    st.markdown(
        """
        - ELT feed basis
        - Raw recovered carbon black production
        - Virgin carbon black substitution credit
        - Avoided shipping credit
        - Optional pyrolysis oil substitution credit
        - Optional rCB deashing / demineralisation
        - Optional zinc recovery credit
        - Excel workbook preview
        - Sankey-style flow visualisation
        """
    )

    st.warning(
        "This is not yet a certified ISO 14040/14044 LCA or EPD model. All placeholder emission factors must be verified and referenced before external claims."
    )
