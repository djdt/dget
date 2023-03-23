from setuptools import setup


setup(
    name="DGet",
    version="0.1",
    description="Cacluator for isotopic abundances.",
    packages=["masscalc"],
    license="LGPL",
    author="djdt",
    install_requires=[
        "numpy",
    ],
    requires=["numpy>=1.22", "masscalc"],
    entry_points={"console_scripts": ["dget=dget.__main__:main"]},
)
