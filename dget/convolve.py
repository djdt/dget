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
        mode: if same, return same size as `x` {'valid', 'same'}

    Returns:
        recovered data
        remainder

    Notes:
        Based on https://rosettacode.org/wiki/Deconvolution/1D
    """

    def shift_bit_length(x: int) -> int:
        return 1 << (x - 1).bit_length()

    r = shift_bit_length(max(x.size, psf.size))
    y = np.fft.irfft(np.fft.rfft(x, r) / np.fft.rfft(psf, r), r)
    rec = np.trim_zeros(np.real(y))[: x.size - (psf.size - 1)]
    rem = x - np.convolve(rec, psf, mode="full")
    return rec, rem
