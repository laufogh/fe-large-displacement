import pytest

from fldlib import config


def test_environment_overrides_are_cast_and_reported(monkeypatch):
    monkeypatch.setenv('FLD_SPEED', '2.5')
    params = config.Params('test')
    params.add('speed', 1.0, 'm/s', 'speed').resolve()

    assert params.speed == 2.5
    assert params.as_dict() == {'speed': 2.5}


def test_invalid_choice_is_rejected(monkeypatch):
    monkeypatch.setenv('FLD_MODE', 'invalid')
    params = config.Params('test')
    params.add('mode', 'ale', '-', 'method', choices=('ale', 'cel'))

    with pytest.raises(config.ParamError):
        params.resolve()


def test_values_cannot_be_read_before_resolution():
    params = config.Params('test')
    params.add('speed', 1.0, 'm/s', 'speed')

    with pytest.raises(config.ParamError):
        _ = params.speed
