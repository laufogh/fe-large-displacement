import math

import pytest

from postproc import energy


def test_ratios_are_pointwise_and_keep_early_dynamic_spike():
    histories = {
        'time': [0.0, 1.0],
        'ALLIE': [1.0, 100.0],
        'ALLKE': [1.0, 1.0],
    }

    ratio = energy.ratios(histories)['ALLKE/ALLIE']

    assert ratio['peak'] == 1.0
    assert ratio['final'] == 0.01
    assert ratio['peak_at'] == 0.0


def test_nonzero_energy_over_zero_internal_energy_is_not_hidden():
    histories = {
        'time': [0.0, 1.0],
        'ALLIE': [0.0, 10.0],
        'ALLKE': [1.0, 0.0],
    }

    ratio = energy.ratios(histories)['ALLKE/ALLIE']

    assert math.isinf(ratio['peak'])


def test_zero_over_zero_is_treated_as_zero_at_initial_frame():
    histories = {
        'time': [0.0, 1.0],
        'ALLIE': [0.0, 10.0],
        'ALLKE': [0.0, 0.5],
    }

    ratio = energy.ratios(histories)['ALLKE/ALLIE']

    assert ratio['peak'] == 0.05
    assert ratio['final'] == 0.05


def test_small_early_internal_energy_is_not_hidden_by_large_later_value():
    histories = {
        'time': [0.0, 1.0],
        'ALLIE': [0.1, 1.0e12],
        'ALLKE': [0.1, 0.0],
    }

    ratio = energy.ratios(histories)['ALLKE/ALLIE']

    assert ratio['peak'] == 1.0


def test_mismatched_history_lengths_are_rejected():
    histories = {
        'time': [0.0, 1.0],
        'ALLIE': [1.0, 2.0],
        'ALLKE': [1.0],
    }

    with pytest.raises(ValueError, match='different lengths'):
        energy.ratios(histories)
