from setuptools import setup

with open("README.md") as fp:
    long_description = fp.read()

setup(
    name="DGet",
    version="0.4",
    description="Calculates compound deuteration from ToF-MS data.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=["dget"],
    license="GPL3",
    author="djdt",
    url="https://github.com/djdt/dget",
    project_urls={
        "Source": "https://github.com/djdt/dget",
        "Web App": "https://djdt.github.io/dget",
    },
    install_requires=["numpy>=1.22", "molmass"],
    extras_require={"tests": ["pytest"]},
    entry_points={"console_scripts": ["dget=dget.__main__:main"]},
)
