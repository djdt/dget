Usage
=====

DGet is a command line tool for calculating molecule deuteration. To see a full list of CLI options, run the help::

    $ dget --help

Basic Usage
-----------

To use DGet pass a molecular formula, mass spectra text file and optionally the adduct formed::

    $ dget C12HD8N <path-to-ms-file.csv> --adduct "[M-H]-"

This will print the deuteration of the base molecule ``%Deuteration`` and the predicted deuteration of every possible deuteration state from ``D0`` (no deuterium) to ``Dn`` (full deuterium):: 

    Formula          : C12H[2H]8N
    Adduct           : [M-H]-
    M/Z              : 175.1237
    Adduct M/Z       : 174.1164
    %Deuteration     : 93.66 %

    Deuteration Ratio Spectra
    D0               :  0.15 %
    D1               :  0.18 %
    D2               :  0.20 %
    D3               :  0.26 %
    D4               :  0.39 %
    D5               :  1.41 %
    D6               :  6.05 %
    D7               : 27.79 %
    D8               : 63.56 %

Plotting
--------

To visualise the deuteration and mass spectrum pass ``--plot``::

    $ dget C12HD8N <path-to-ms-file.csv> --adduct "[M-H]-" --plot

This will show the de-convolved deuteration spectra in red and the predicted adduct spectra in blue.
These spectra are scaled to fit the mass data so absolute heights will not be indicative of good fit.

.. image:: https://github.com/djdt/djdt.github.io/raw/main/img/dget_c12hd8n.png

Plotting depends on `matplotlib <https://matplotlib.org>`_.

Web App
-------

A web application of DGet is available at `<https://dget.app>`_.

Details on its usage can be found on the `Help <https://dget.app/help>`_ page.


Installation
============

DGet is available on PyPI and can be installed via ``pip``::

    $ pip install dget

To install DGet from source first clone the repository::

    $ git clone https://github.com/djdt/dget

Then install using ``pip``::

    $ cd dget
    $ pip install .


Requirements
------------

* `numpy >= 1.22 <https://numpy.org>`_
* `molmass <https://github.com/cgohlke/molmass>`_
* `matplotlib <https://matplotlib.org>`_ (optional, for plotting)


Documentation
=============

Documentation is available at `<https://dget.readthedocs.io>`_.
