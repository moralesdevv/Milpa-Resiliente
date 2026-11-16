"""Errores tipados (apartado 10). La API los traduce a RFC 7807 con ``code``."""


class MilpaError(Exception):
    code = "VALIDATION_ERROR"


class MixedCycleLengthError(MilpaError):
    code = "MIXED_CYCLE_LENGTH"


class MultipleSweepCycles(MilpaError):
    code = "MULTIPLE_SWEEP_CYCLES"


class MissingThresholdCitation(MilpaError):
    code = "MISSING_THRESHOLD_CITATION"


class InsufficientSoilData(MilpaError):
    code = "INSUFFICIENT_SOIL_DATA"


class NotComparable(MilpaError):
    code = "NOT_COMPARABLE"


class ScenarioNotApplicable(MilpaError):
    code = "SCENARIO_NOT_COMPUTED"


class StrategyValidationError(MilpaError):
    code = "VALIDATION_ERROR"


class IndicatorContractError(MilpaError):
    """Indicator inválido: sin procedencia, etiqueta de modo cruzada, provisional sin razón."""

    code = "VALIDATION_ERROR"
