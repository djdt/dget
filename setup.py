from setuptools import setup

setup(
    name="DGet",
    version="0.1",
    description="Cacluator for isotopic abundances.",
    packages=["dget"],
    license="LGPL",
    author="djdt",
    install_requires=["numpy>=1.22"],
    entry_points={"console_scripts": ["dget=dget.__main__:main"]},
)
