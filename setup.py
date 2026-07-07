"""Quimera MarkX — Setup (backward compatibility shim).

Delegates to pyproject.toml for all metadata and dependencies.
Modern pip (>=21.3) reads pyproject.toml directly.
This file exists for tools that still require setup.py.
"""
from setuptools import setup

setup(
    name="quimera",
    version="3.0.0",
    description="Quimera MarkX — AI-driven vulnerability detection & auto-patching for C/C++/Kernel",
    python_requires=">=3.11",
    packages=[],
)
