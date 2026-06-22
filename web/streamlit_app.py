from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine" / "opentyre_lca"))

import pandas as pd
import streamlit as st

from opentyre_lca import (
    workbook_base_case,
    calculate_lca,
    lci_records,
    contribution_records,
    run_scenarios,
)
from opentyre_lca.tyre_model import update_params


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
        font-size: 1.65rem;
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
# Build base params
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
# Header KPIs
# ------------------------------------------------------------

k1, k2, k3, k4, k5 = st.columns(5)

k1.metric("ELT feed", f"{result['annual_elt_t']:,.0f} t/y")
k2.metric("Raw rCB", f"{result['raw_rcb_tpy']:,.0f} t/y")
k3.metric("rCB product", f"{result['cb_product_for_substitution_tpy']:,.0f} t/y")
k4.metric("Net saving", f"{result['net_saving_tco2e_per_year']:,.0f} tCO₂e/y")
k5.metric("Saving intensity", f"{result['net_saving_tco2e_per_t_elt']:.3f} tCO₂e/t ELT")


# ------------------------------------------------------------
# Scenario generation
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
# Tabs
# ------------------------------------------------------------

tab_overview, tab_scenarios, tab_lci, tab_method = st.tabs(
    ["Overview", "Scenarios", "LCI table", "Methodology"]
)


with tab_overview:
    left, right = st.columns([1.2, 1])

    with left:
        st.subheader("Life-cycle contribution by stage")
        if not contrib_df.empty:
            chart_df = contrib_df.set_index("stage")[["impact_tco2e_per_year"]]
            st.bar_chart(chart_df)
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
        pd.DataFrame(
            [{"metric": key, "value": value} for key, value in summary_rows.items()]
        ),
        use_container_width=True,
        hide_index=True,
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
        st.bar_chart(
            scenario_view.set_index("case")[["net_saving_tco2e_per_year"]]
        )

    with c2:
        st.markdown("#### Saving intensity by scenario")
        st.bar_chart(
            scenario_view.set_index("case")[["net_saving_tco2e_per_t_elt"]]
        )

    st.download_button(
        "Download scenario results as CSV",
        scenario_view.to_csv(index=False).encode("utf-8"),
        file_name="lca_tyre_scenario_results.csv",
        mime="text/csv",
    )


with tab_lci:
    st.subheader("Life-cycle inventory")

    filter_stage = st.multiselect(
        "Filter by stage",
        options=sorted(lci_df["stage"].unique()) if not lci_df.empty else [],
        default=sorted(lci_df["stage"].unique()) if not lci_df.empty else [],
    )

    filtered_lci = lci_df[lci_df["stage"].isin(filter_stage)] if filter_stage else lci_df

    st.dataframe(filtered_lci, use_container_width=True, hide_index=True)

    st.download_button(
        "Download LCI as CSV",
        filtered_lci.to_csv(index=False).encode("utf-8"),
        file_name="lca_tyre_lci.csv",
        mime="text/csv",
    )

    st.subheader("Top LCI contributors")
    top_lci = filtered_lci.copy()
    if not top_lci.empty:
        top_lci["absolute_impact"] = top_lci["impact_tco2e_per_year"].abs()
        top_lci = top_lci.sort_values("absolute_impact", ascending=False).head(10)
        st.bar_chart(top_lci.set_index("item")[["impact_tco2e_per_year"]])


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
        """
    )

    st.warning(
        "This is not yet a certified ISO 14040/14044 LCA or EPD model. All placeholder emission factors must be verified and referenced before external claims."
    )
