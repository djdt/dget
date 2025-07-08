Usage
=====

DGet! is a command line tool for calculating molecule deuteration. To see a full list of CLI options, run the help::

    $ dget --help

Basic Usage
-----------

To use DGet! pass a molecular formula, mass spectra text file and optionally the adduct formed::

    $ dget C12HD8N <path-to-ms-file.csv> --adduct "[M-H]-"

This will print the deuteration of the base molecule ``%Deuteration`` and the predicted deuteration of every possible deuteration state from ``D0`` (no deuterium) to ``Dn`` (full deuterium)::

    Formula          : C12HD8N
    Adduct           : [M-H]-
    M/Z              : 175.1237
    Adduct M/Z       : 174.1164
    Deuteration      : 93.73 %

    Deuteration Ratio Spectra
    D0               :  0.07 %
    D1               :  0.19 %
    D2               :  0.20 %
    D3               :  0.26 %
    D4               :  0.39 %
    D5               :  1.41 %
    D6               :  6.05 %
    D7               : 27.80 %
    D8               : 63.62 %

Plotting
--------

To visualise the deuteration and mass spectrum pass ``--plot``::

    $ dget C12HD8N <path-to-ms-file.csv> --adduct "[M-H]-" --plot

This will show the de-convolved deuteration spectra in red and the predicted adduct spectra in blue.
These spectra are scaled to fit the mass data so absolute heights will not be indicative of good fit.

.. image:: https://github.com/djdt/djdt.github.io/raw/main/img/dget_c12hd8n.png

Plotting depends on `matplotlib <https://matplotlib.org>`_.

GUI
---

A Qt based GUI is also available and can be started using::

    $ dget-gui

.. image:: https://github.com/djdt/djdt.github.io/raw/main/img/gui_mainwindow_v1.0.0.png

Windows executables are available for each release on the DGet! GitHub `<https://github.com/djdt/dget/releases>`_.

Basic usage on the GUI can be found in the `Documentation <https://dget.readthedocs.io/en/latest/usage.html#gui>`_.


Web App
-------

A web application of DGet! is available at `<https://dget.app>`_.

Details on its usage can be found on the `Help <https://dget.app/help>`_ page.


Installation
============

DGet! is available on PyPI and can be installed via ``pip``::

    $ pip install dget

To install the GUI::

    $ pip install dget[gui]

To install DGet! from source first clone the repository::

    $ git clone https://github.com/djdt/dget

Then install using ``pip``::

    $ cd dget
    $ pip install .


Requirements
------------

* `numpy <https://numpy.org>`_
* `molmass <https://github.com/cgohlke/molmass>`_
* `matplotlib <https://matplotlib.org>`_ (optional, for plotting)
* `PySide6 <https://https://doc.qt.io/qtforpython-6>`_ (optional, for GUI)
* `pyqtgraph <https://www.pyqtgraph.org/>`_ (optional, for GUI)


Documentation
=============

Documentation is available at `<https://dget.readthedocs.io>`_.


Citation
========

When using DGet! in your research please cite:

`Lockwood, T.E., Angeloski, A. DGet! An open source deuteration calculator for mass spectrometry data. J Cheminform 16, 36 (2024). <https://doi.org/10.1186/s13321-024-00828-x>`_
