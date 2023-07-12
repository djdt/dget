from typing import List

import numpy as np


def scale_to_match(
    rx: np.ndarray, ry: np.ndarray, x: np.ndarray, y: np.ndarray, width: float = 0.0
):
    """Scales data.

    Applies a factor to ``y`` to match maximum height of ``ry``.

    Args:
        rx: x data of reference
        ry: y data fo reference
        x: x data of points to be scaled
        y: y data to be scaled, to match ``ry``
        width: area around ``rx`` points to search for maximum height

    Returns:
        scaled ``y``
    """
    if y.ndim == 2:
        sum_y = np.sum(y, axis=1)  # Deal with any stacked data
    else:
        sum_y = y

    max = x[np.argmax(sum_y)]
    start, end = np.searchsorted(rx, [max - width, max + width])
    if start == end:
        return y
    return y * np.amax(ry[start:end]) / sum_y.max()


def stacked_stem(
    ax: "matplotlib.axes.Axes",
    x: np.ndarray,
    ys: np.ndarray,
    bottom: float | np.ndarray = 0.0,
    stack_kws: List[dict] | None = None,
    **kwargs,
):
    """Plots stacked vertical lines.

    Additional ``kwargs`` are passed to ``Axes.vlines``.

    Args:
        ax: axes to plot on
        x: x data
        y: y data, shape (x.size, N)
        bottom: initial minimum y values
        stack_kwargs: kwargs for each stack
    """
    if isinstance(bottom, float):
        bottom = np.full(x.size, bottom)

    for i in range(ys.shape[1]):
        kws = {} if stack_kws is None else stack_kws[i]

        ax.vlines(x, bottom, bottom + ys[:, i], **kws, **kwargs)
        bottom += ys[:, i]
