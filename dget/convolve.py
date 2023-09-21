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
