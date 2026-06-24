from __future__ import annotations

from .tyre_model import TyreLCAParams, update_params, calculate_lca


DEFAULT_SENSITIVITY_PARAMETERS = {
    "Annual ELT feed": "annual_elt_t",
    "Raw rCB yield": "rcb_yield_t_per_t_elt",
    "Virgin carbon black EF": "virgin_cb_ef_tco2e_per_t",
    "Raw rCB pyrolysis EF": "raw_rcb_pyrolysis_ef_tco2e_per_t",
    "Avoided shipping credit": "avoided_shipping_tco2e_per_year",
    "Oil credit": "oil_credit_tco2e_per_year",
    "Deashing purified yield": "deashing__purified_yield_t_per_t_feed",
    "HNO3 use": "deashing__hno3_kg_per_t_feed",
    "NaOH use": "deashing__naoh_kg_per_t_feed",
    "Deashing electricity": "deashing__electricity_kwh_per_t_feed",
}


def _get_value(params: TyreLCAParams, field: str) -> float:
    if field.startswith("deashing__"):
        attr = field.replace("deashing__", "", 1)
        return float(getattr(params.deashing, attr))
    return float(getattr(params, field))


def run_one_at_a_time_sensitivity(
    params: TyreLCAParams,
    variation_fraction: float = 0.20,
    parameters: dict[str, str] | None = None,
    output_metric: str = "net_saving_tco2e_per_year",
) -> list[dict]:
    parameters = parameters or DEFAULT_SENSITIVITY_PARAMETERS

    base_result = calculate_lca(params)
    base_output = float(base_result[output_metric])

    rows = []

    for label, field in parameters.items():
        try:
            base_param = _get_value(params, field)
        except Exception:
            continue

        if base_param == 0:
            continue

        low_param = base_param * (1.0 - variation_fraction)
        high_param = base_param * (1.0 + variation_fraction)

        if "yield" in field:
            low_param = max(0.0, min(1.0, low_param))
            high_param = max(0.0, min(1.0, high_param))

        low_params = update_params(params, **{field: low_param})
        high_params = update_params(params, **{field: high_param})

        low_result = calculate_lca(low_params)
        high_result = calculate_lca(high_params)

        low_output = float(low_result[output_metric])
        high_output = float(high_result[output_metric])

        rows.append(
            {
                "parameter": label,
                "field": field,
                "base_parameter_value": base_param,
                "low_parameter_value": low_param,
                "high_parameter_value": high_param,
                "base_result": base_output,
                "low_result": low_output,
                "high_result": high_output,
                "low_delta": low_output - base_output,
                "high_delta": high_output - base_output,
                "swing": abs(high_output - low_output),
                "variation_percent": variation_fraction * 100.0,
                "output_metric": output_metric,
            }
        )

    rows.sort(key=lambda r: r["swing"], reverse=True)
    return rows
