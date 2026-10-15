"""Import guard for the matplotlib code path IR-SIM depends on.

While matplotlib builds its class hierarchy it generates help text for the
auto-created ``Artist.set()`` methods.  ``ArtistInspector.get_valid_values``
runs a regular expression over a very long property docstring, and on CPython
3.14 with matplotlib 3.11 that search intermittently raises::

    RuntimeError: internal error in regular expression engine

The failure happens during ``import matplotlib.axes`` (and during the
``Artist`` import itself), so an IR-SIM run dies before the robot ever moves.
It is not deterministic: the same import succeeds most of the time, which is
why the pipeline only failed on some runs.

Only the human-readable "ACCEPTS:" help text is affected, so this module makes
that lookup total (falling back to matplotlib's own ``unknown`` placeholder)
and retries the import a few times if the regex engine fails before the guard
can be installed.  Import this module before ``matplotlib`` or ``irsim``::

    import matplotlib_compat  # noqa: F401
    import irsim
"""

import sys

_MATPLOTLIB_PREFIX = "matplotlib"


def _purge_matplotlib():
    """Drop partially imported matplotlib modules so a retry starts clean."""
    for name in [n for n in sys.modules
                 if n == _MATPLOTLIB_PREFIX or n.startswith(_MATPLOTLIB_PREFIX + ".")]:
        del sys.modules[name]


def _patch_inspector():
    """Make the flaky docstring regex non-fatal."""
    from matplotlib.artist import ArtistInspector

    original = ArtistInspector.get_valid_values

    def get_valid_values(self, attr):
        try:
            return original(self, attr)
        except RuntimeError:  # pragma: no cover - depends on the regex engine
            return "unknown"

    ArtistInspector.get_valid_values = get_valid_values


def install(attempts=4):
    """Import matplotlib with the guard installed, retrying the flaky import."""
    last_error = None
    for _ in range(max(1, attempts)):
        try:
            import matplotlib.artist  # noqa: F401
        except RuntimeError as error:  # regex engine failure during import
            last_error = error
            _purge_matplotlib()
            continue
        _patch_inspector()
        try:
            import matplotlib.axes  # noqa: F401  (class creation uses the regex)
            import matplotlib.pyplot  # noqa: F401
        except RuntimeError as error:  # pragma: no cover - environment dependent
            last_error = error
            _purge_matplotlib()
            continue
        return
    raise RuntimeError(
        "matplotlib could not be imported: the Python regular expression engine "
        f"failed repeatedly ({last_error})"
    )


install()
