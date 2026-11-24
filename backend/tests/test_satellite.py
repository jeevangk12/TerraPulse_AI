from app.services.satellite import _EVALSCRIPT, _stats_for_output


def test_multiband_output_never_falls_back_to_wrong_band():
    outputs = {"quality": {"bands": {"B0": {"stats": {"mean": 0.9}}, "B1": {"stats": {"mean": 0.1}}}}}
    assert _stats_for_output(outputs, "quality", "B1") == {"mean": 0.1}
    assert _stats_for_output(outputs, "quality", "B0") == {"mean": 0.9}
    only_valid = {"quality": {"bands": {"B0": {"stats": {"mean": 0.9}}}}}
    only_valid["quality"]["bands"]["B2"] = {"stats": {"mean": 0.5}}
    assert _stats_for_output(only_valid, "quality", "B1") is None  # cloud stats must not equal valid stats


def test_single_band_output_may_use_sole_band():
    outputs = {"ndvi": {"bands": {"B0": {"stats": {"mean": 0.5}}}}}
    assert _stats_for_output(outputs, "ndvi", "anything") == {"mean": 0.5}


def test_unclassified_scl_class_is_not_counted_as_cloud():
    assert "[3, 8, 9, 10].includes(sample.SCL)" in _EVALSCRIPT
