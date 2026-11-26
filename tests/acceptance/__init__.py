"""Acceptance checks for the success criteria S1–S10 (CONTEXT §14).

The harness (``harness.py``, ``context.py``, ``__main__.py``) is M6's (tracker M6-07). Each
``s<N>_*.py`` module checks one criterion and belongs to the member in its ``OWNER``.

Run against a deployed stage:  ``make acceptance STAGE=prod [ONLY=S1,S10]``
"""
