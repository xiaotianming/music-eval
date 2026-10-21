import numpy as np
import soundfile as sf
import pytest
from backend.audio import basic, windows, mono_resample


def test_silence_and_tail_windows(tmp_path):
    path = tmp_path / "中文 空格.wav"
    sr = 8000
    sf.write(path, np.zeros(sr * 21 + sr // 2), sr)
    result = basic(path)
    assert result["silence_ratio"] == 1
    assert result["loudness_lufs"] is None
    assert result["duration"] == 21.5
    chunks = list(windows(mono_resample(path, 48000)))
    assert [valid for _, valid, _ in chunks] == [10, 10, 1.5]
    assert [start for start, _, _ in chunks] == [0, 10, 20]
    assert all(len(chunk) == 480000 for _, _, chunk in chunks)


def test_stereo_near_full_scale_and_nonfinite(tmp_path):
    sr = 8000
    x = np.full((sr, 2), .2, dtype=np.float32)
    x[:sr // 2, 0] = 1
    path = tmp_path / "peak.wav"
    sf.write(path, x, sr, subtype="FLOAT")
    result = basic(path)
    assert result["near_full_scale_ratio"] == pytest.approx(.25)
    assert result["channels"] == 2
    assert result["near_full_scale_intervals"] == [{"start": 0, "end": .5}]
    x[0, 0] = np.nan
    sf.write(path, x, sr, subtype="FLOAT")
    result = basic(path)
    assert result["invalid_values"] == 1
    assert result["loudness_lufs"] is None
    with pytest.raises(ValueError, match="NaN"):
        mono_resample(path, sr)


def test_short_and_corrupt(tmp_path):
    p = tmp_path / "short.wav"
    sf.write(p, np.ones(80) * .1, 8000)
    assert basic(p)["loudness_lufs"] is None
    p.write_bytes(b"not an audio file")
    with pytest.raises(ValueError, match="解码失败"):
        basic(p)


def test_fad_psd_distance_with_rank_deficient_covariance():
    from backend.distance import frechet_psd
    rng = np.random.default_rng(0)
    a = rng.normal(size=(4, 32))
    mean, cov = a.mean(axis=0), np.cov(a, rowvar=False)
    assert frechet_psd(mean, cov, mean, cov) < 1e-5
    # A pure translation changes the distance by the squared mean displacement.
    assert frechet_psd(mean, cov, mean + .1, cov) == pytest.approx(.32, abs=1e-5)
