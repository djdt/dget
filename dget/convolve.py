import numpy as np


def deconvolve(x: np.ndarray, psf: np.ndarray, mode: str = "valid"):
    """Inverse of convolution.

    Deconvolution is performed in frequency domain.

    Args:
        x: array
        psf: point spread function
        mode: if same, return same size as `x` {'valid', 'same'}

    Notes:
        Based on https://rosettacode.org/wiki/Deconvolution/1D
    """

    def shift_bit_length(x: int) -> int:
        return 1 << (x - 1).bit_length()

    r = shift_bit_length(max(x.size, psf.size))
    y = np.fft.irfft(np.fft.rfft(x, r) / np.fft.rfft(psf, r), r)
    rec = np.trim_zeros(np.real(y))[: x.size - psf.size - 1]
    if mode == "valid":
        return rec
    elif mode == "same":
        return np.hstack((rec, x[rec.size :]))
    else:  # pragma: no cover
        raise ValueError("Valid modes are 'valid', 'same'.")
