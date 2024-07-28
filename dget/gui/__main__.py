import argparse
import logging
import sys

from PySide6 import QtCore, QtWidgets

from dget.gui.mainwindow import DGetMainWindow

__gui_version__ = "0.1"

logging.captureWarnings(True)
logger = logging.getLogger("dget")
logger.setLevel(logging.INFO)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="dget",
        description="Qt GUI for DGet!, an HRMS deuteration calculator",
    )
    parser.add_argument(
        "--nohook", action="store_true", help="don't install the exception hook"
    )
    parser.add_argument("--version", action="version", version=__gui_version__)
    parser.add_argument(
        "qtargs", nargs=argparse.REMAINDER, help="arguments to pass to Qt"
    )
    args = parser.parse_args(argv)
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    app = QtWidgets.QApplication()
    app.setApplicationName("DGet!")
    app.setOrganizationName("DGet!")
    app.setApplicationVersion(__gui_version__)

    window = DGetMainWindow()

    if not args.nohook:
        sys.excepthook = window.exceptHook

    logger.addHandler(window.log.handler)
    logger.info(f"DGet! {app.applicationVersion()} started.")

    window.show()

    # Keep event loop active with timer
    timer = QtCore.QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(100)

    return app.exec_()


if __name__ == "__main__":
    main(sys.argv[1:])
