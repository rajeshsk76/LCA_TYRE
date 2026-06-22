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
