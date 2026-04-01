"""Regression tests for unsupported tuning data types."""

from __future__ import annotations

import numpy as np
import pytest

from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.models.component import load_components
from pvtcore.tuning.objectives import DataType, ExperimentalPoint
from pvtcore.tuning.parameters import create_kij_parameters
from pvtcore.tuning.regression import EOSRegressor


def test_unsupported_tuning_datatype_error_mentions_supported_types() -> None:
    components = load_components()
    pair = [components["C1"], components["C3"]]
    eos = PengRobinsonEOS(pair)
    params = create_kij_parameters(2, ["C1", "C3"])
    regressor = EOSRegressor(pair, eos, params)

    point = ExperimentalPoint(
        data_type=DataType.GOR,
        temperature=300.0,
        pressure=5_000_000.0,
        value=1.0,
        composition=np.array([0.5, 0.5]),
    )

    with pytest.raises(NotImplementedError) as excinfo:
        regressor._model_function(point, {})

    message = str(excinfo.value)
    assert "Unsupported DataType=GOR" in message
    assert "Supported:" in message
    assert "SATURATION_PRESSURE" in message
    assert "Filter the dataset" in message
