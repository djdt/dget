from pathlib import Path

from setuptools import setup

with open("README.rst") as fp:
    long_description = fp.read()

with Path("dget", "__init__.py").open() as fp:
    version = None
    for line in fp:
        if line.startswith("__version__"):
            version = line.split("=")[1].strip().strip('"')
    if version is None:
        raise ValueError("Could not read version from __init__.py")

setup(
    name="DGet",
    version=version,
    description="Calculates compound deuteration from ToF-MS data.",
    long_description=long_description,
    long_description_content_type="text/x-rst",
    packages=["dget", "dget.io"],
    license="GPL3",
    author="djdt",
    url="https://github.com/djdt/dget",
    project_urls={
        "Documentation": "https://dget.readthedocs.io",
        "Source": "https://github.com/djdt/dget",
        "Web App": "https://djdt.github.io/dget",
    },
    install_requires=["numpy>=1.22", "molmass"],
    extras_require={"tests": ["pytest"]},
    entry_points={"console_scripts": ["dget=dget.__main__:main"]},
)
