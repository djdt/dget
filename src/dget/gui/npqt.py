import ctypes

import numpy as np
import shiboken6
from PySide6 import QtGui


def array_to_polygonf(array: np.ndarray) -> QtGui.QPolygonF:
    """Converts a numpy array of shape (n, 2) to a Qt polygon."""
    assert array.ndim == 2
    assert array.shape[1] == 2

    polygon = QtGui.QPolygonF()
    polygon.resize(array.shape[0])

    buf = (ctypes.c_double * array.size).from_address(
        shiboken6.getCppPointer(polygon.data())[0]  # type: ignore
    )

    memory = np.frombuffer(buf, np.float64)
    memory[:] = array.ravel()
    return polygon
