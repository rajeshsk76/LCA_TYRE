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
