"""Convolution implementations.

Deconvolution is used by DGet to recover the original deuteration
pattern from a given mass spectrum.
"""
from typing import Tuple

import numpy as np


def deconvolve(x: np.ndarray, psf: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Inverse of convolution.

    Deconvolution is performed in frequency domain.

    Args:
        x: array
        psf: point spread function

    Returns:
        recovered data
        remainder

    Notes:
        Based on https://rosettacode.org/wiki/Deconvolution/1D
    """

    r = max(x.size, psf.size)
    X = np.fft.rfft(x, r)
    P = np.fft.rfft(psf, r)
    y = np.fft.irfft(X / P, r)
    rec = y[: x.size - (psf.size - 1)]
    rem = x - np.convolve(rec, psf, mode="full")
    return rec, rem


def autocorrelate(x: np.ndarray) -> np.ndarray:
    """Calulate the auto-correlation of ``x``.

    Args:
        x: array

    Returns:
        convolution of ``x`` with itself
    """
    return np.convolve(x, x)


def recovery_autocorrelated(x: np.ndarray, fft_size: int = 1000) -> np.ndarray:
    """Recover the original distribution self convolved.

    Self convolution is raising to a power in the frequency domain,
    so to recover the original distribution we can simply take the sqrt.

    Args:
        x: self convolved array
        fft_size: size of FFT, larger sizes decrease change of error

    Returns:
        recovered array
    """

    size = (x.size - 1) // 2

    X = np.fft.rfft(x, fft_size)
    R = np.sqrt(X)
    Q = -R
    P = R.copy()

    for i in range(1, R.size - 1):  # Choose correct (1st or 2nd) root based on gradient
        if np.abs((P[i - 1] - P[i]) - (P[i] - Q[i + 1])) < np.abs(
            (P[i - 1] - P[i]) - (P[i] - R[i + 1])
        ):
            P[i + 1] = Q[i + 1]

    return np.fft.irfft(P, fft_size)[:size]
