from setuptools import setup

setup(
    name="DGet",
    version="0.2",
    description="Deuteration calculator for ToF-MS data.",
    packages=["dget"],
    license="LGPL",
    author="djdt",
    install_requires=["numpy>=1.22", "molmass"],
    entry_points={"console_scripts": ["dget=dget.__main__:main"]},
)
