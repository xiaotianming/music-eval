import hashlib
import subprocess
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
from math import gcd
from .config import DATA


def ffmpeg():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def read_audio(path):
    try:
        x, sr = sf.read(path, dtype="float32", always_2d=True)
    except Exception:
        key = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        decoded = DATA / "cache" / f"decoded-{key}.wav"
        if not decoded.exists():
            p = subprocess.run([ffmpeg(), "-v", "error", "-y", "-i", str(path),
                                "-c:a", "pcm_f32le", str(decoded)], capture_output=True, timeout=120)
            if p.returncode:
                raise ValueError("音频解码失败：" + p.stderr.decode(errors="replace")[-1000:])
        x, sr = sf.read(decoded, dtype="float32", always_2d=True)
    if not len(x):
        raise ValueError("音频为空")
    return x, int(sr)


def mono_resample(path, target):
    x, sr = read_audio(path)
    if not np.isfinite(x).all():
        raise ValueError("音频包含 NaN/Inf，无法运行模型")
    x = x.mean(axis=1)
    if sr != target:
        d = gcd(sr, target)
        x = resample_poly(x, target // d, sr // d)
    return np.asarray(x, dtype=np.float32)


def intervals(mask, step, duration):
    # Run-length encode diagnostics; retain the full affected timeline.
    edges = np.diff(np.r_[False, mask, False].astype(int))
    return [{"start": round(a * step, 4), "end": round(min(b * step, duration), 4)}
            for a, b in zip(np.where(edges == 1)[0], np.where(edges == -1)[0])]


def basic(path):
    import pyloudnorm as pyln
    x, sr = read_audio(path)
    finite = np.isfinite(x)
    invalid = int((~finite).sum())
    safe = np.where(finite, x, 0)
    duration = len(x) / sr
    size = max(1, int(sr * .1))
    rms = np.array([np.sqrt(np.mean(safe[i:i + size].astype(np.float64) ** 2))
                    for i in range(0, len(x), size)])
    quiet = rms < 10 ** (-60 / 20)
    near = np.abs(safe) >= .999
    clip_blocks = np.array([near[i:i + size].any() for i in range(0, len(x), size)])
    weights = np.minimum(size, len(x) - np.arange(len(rms)) * size)
    loudness = None
    loudness_reason = "音频含异常数值" if invalid else "音频过短或全静音，无法计算综合响度"
    if x.shape[1] > 5:
        loudness_reason = "超过五声道，不支持该布局的综合响度计算"
    if duration >= .4 and not invalid and x.shape[1] <= 5:
        try:
            value = float(pyln.Meter(sr).integrated_loudness(safe))
            if np.isfinite(value):
                loudness = value
                loudness_reason = None
        except ValueError:
            pass
    return {"duration": duration, "sample_rate": sr, "channels": x.shape[1],
            "silence_ratio": float(np.average(quiet, weights=weights)),
            "near_full_scale_ratio": float(near.mean()), "peak": float(np.max(np.abs(safe))),
            "invalid_values": invalid, "loudness_lufs": loudness,
            "loudness_reason": loudness_reason,
            "silence_intervals": intervals(quiet, size / sr, duration),
            "near_full_scale_intervals": intervals(clip_blocks, size / sr, duration),
            "protocol": {"silence_block_ms": 100, "silence_threshold_dbfs": -60,
                         "near_full_scale_threshold": .999, "loudness": "ITU-R BS.1770 / pyloudnorm"}}


def waveform(path, bins=900):
    x, sr = read_audio(path)
    if not np.isfinite(x).all():
        x = np.nan_to_num(x, nan=0, posinf=0, neginf=0)
    step = max(1, int(np.ceil(len(x) / bins)))
    return {"duration": len(x) / sr,
            "peaks": [float(np.max(np.abs(x[i:i + step]))) for i in range(0, len(x), step)]}


def windows(x, sr=48000, seconds=10):
    n = sr * seconds
    for start in range(0, len(x), n):
        chunk = x[start:start + n]
        valid = len(chunk) / sr
        yield start / sr, valid, np.pad(chunk, (0, n - len(chunk)))
