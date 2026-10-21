"""Numerically stable Fréchet distance for singular finite-sample covariances."""
import numpy as np


def frechet_psd(mu_a, cov_a, mu_b, cov_b):
    a = (np.atleast_2d(cov_a) + np.atleast_2d(cov_a).T) / 2
    b = (np.atleast_2d(cov_b) + np.atleast_2d(cov_b).T) / 2
    eigenvalues, vectors = np.linalg.eigh(a)
    root = (vectors * np.sqrt(np.maximum(eigenvalues, 0))) @ vectors.T
    middle = root @ b @ root
    cross = np.sqrt(np.maximum(np.linalg.eigvalsh((middle + middle.T) / 2), 0)).sum()
    delta = np.asarray(mu_a) - np.asarray(mu_b)
    value = float(delta @ delta + np.trace(a) + np.trace(b) - 2 * cross)
    if not np.isfinite(value) or value < -1e-4:
        raise ValueError("FAD 数值异常")
    return max(0, value)
