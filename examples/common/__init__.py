"""Shared machinery for the examples.

`indenter_model` builds the benchmark that examples 01-05 all use; `runner`
holds the per-case run loop and the summary table.

This file exists because Python 2.7 -- which is what Abaqus/CAE runs -- requires
an `__init__.py` for `from common import indenter_model` to resolve. Without it
the import fails with a bare ImportError that does not mention packages at all.
"""
