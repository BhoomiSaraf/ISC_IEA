"""Reproducible sequence generation for the frozen Ikeda-Sine-Chebyshev (ISC) map.

Modules
-------
isc_map      frozen map definition (canonical + legacy-exact evaluation)
trajectory   raw x/y trajectories with configurable transient removal
extract      digital (bit) extraction methods, evaluated separately
periodicity  finite-precision cycle detection (Brent) and quantised-state studies
stats        statistical diagnostics on raw trajectories and bitstreams
nist         subset of NIST SP 800-22 tests with the multi-sequence protocol
experiment   config-driven experiment runner and report writer
"""

__version__ = "0.1.0"
