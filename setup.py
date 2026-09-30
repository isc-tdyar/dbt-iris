#!/usr/bin/env python
from setuptools import find_namespace_packages, setup

from pathlib import Path

package_name = "dbt-iris"
description = """The InterSystems IRIS adapter plugin for dbt"""

# used for this adapter's version and in determining the compatible dbt-core version
VERSION = Path(__file__).parent / "dbt/adapters/iris/__version__.py"


def _dbt_iris_version() -> str:
    """
    Pull the package version from the main package version file
    """
    attributes = {}
    exec(VERSION.read_text(), attributes)
    return attributes["version"]


setup(
    name=package_name,
    version=_dbt_iris_version(),
    description=description,
    long_description=description,
    license="MIT",
    author="CaretDev",
    author_email="info@caretdev.com",
    url="https://github.com/caretdev/dbt-iris",
    packages=find_namespace_packages(
        include=[
            "dbt",
            "dbt.*",
        ]
    ),
    include_package_data=True,
    install_requires=[
        "dbt-adapters>=1.1.1,<2.0",
        # add dbt-core to ensure backwards compatibility of installation, this is not a functional dependency
        "dbt-core>=1.8.0",
        "dbt-common>=1.0.4,<2.0",
        # InterSystems DB-API driver. Replaces the intersystems_iris 3.x wheel that
        # requirements-iris.txt used to download and bundle (that URL no longer resolves).
        # The bundled copy, if present, is still used when the profile sets `driver: vendored`.
        "intersystems-irispython>=5.4.0",
    ],
    extras_require={
        # Optional: connect through the InterSystems SQLAlchemy dialect (`driver: sqlalchemy`).
        "sqlalchemy": ["sqlalchemy>=2.0,<3", "sqlalchemy-intersystems-iris>=1.0.2"],
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
)
