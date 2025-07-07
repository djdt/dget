from typing import List

import numpy as np


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
