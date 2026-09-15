"""Parameters with units, documentation and environment-variable overrides.

Why not a `shelve` database, or a module of module-level globals?

* A shelve is opaque: you cannot diff it, review it in a pull request, or see in
  the log what the run actually used.
* Module-level globals get shadowed and reassigned halfway down a 2000-line
  script, and by the time the job is submitted nobody knows what is in them.

A `Params` object is an explicit, printable, overridable record. Every example
prints its full parameter table into the log before it builds anything, so the
log alone tells you what was run.

Overrides come from the environment, which is what lets a batch of runs
sweep a study without editing a single file::

    set FLD_INDENT_VEL=2.0
    set FLD_ALE_FREQUENCY=2
    abaqus cae noGUI=model.py

Usage::

    P = Params('indenter_explicit_ale')
    P.add('soil_len',   0.30, 'm',   'soil block length (x)')
    P.add('indent_vel', 1.0,  'm/s', 'prescribed indenter velocity')
    P.add('ale_mode',  'box', '-',   'off | whole | box',
          choices=('off', 'whole', 'box'))
    P.resolve()          # applies env overrides, validates, freezes
    P.show()             # prints the table
    ...
    soil = make_block(P.soil_len, ...)
"""

from __future__ import print_function

import os


_PREFIX = 'FLD_'

# Environment variables that belong to the harness rather than to any one
# study, and so must not be reported as typos by resolve().
_HARNESS_VARS = ('REPO', 'WORKDIR', 'CASES', 'NCPU', 'NDOMAINS', 'SUBMIT',
                 'ABAQUS', 'SUBROUTINE', 'DOUBLE')


class ParamError(ValueError):
    pass


class _Entry(object):
    __slots__ = ('name', 'default', 'unit', 'doc', 'choices', 'cast',
                 'value', 'source')

    def __init__(self, name, default, unit, doc, choices, cast):
        self.name = name
        self.default = default
        self.unit = unit
        self.doc = doc
        self.choices = choices
        self.cast = cast
        self.value = default
        self.source = 'default'


def _to_bool(text):
    if isinstance(text, bool):
        return text
    t = str(text).strip().lower()
    if t in ('1', 'true', 'yes', 'on'):
        return True
    if t in ('0', 'false', 'no', 'off'):
        return False
    raise ParamError('cannot read %r as a boolean' % text)


def _infer_cast(default):
    # bool before int: bool is a subclass of int in Python.
    if isinstance(default, bool):
        return _to_bool
    if isinstance(default, int):
        return int
    if isinstance(default, float):
        return float
    return str


class Params(object):
    """An ordered, documented, environment-overridable parameter set."""

    def __init__(self, study, prefix=_PREFIX):
        self._study = study
        self._prefix = prefix
        self._order = []
        self._entries = {}
        self._frozen = False

    # -- definition ---------------------------------------------------------

    def add(self, name, default, unit, doc, choices=None, cast=None):
        """Declare one parameter. Returns self so calls can be chained."""
        if self._frozen:
            raise ParamError('cannot add %r after resolve()' % name)
        if name in self._entries:
            raise ParamError('duplicate parameter %r' % name)
        if name != name.lower():
            raise ParamError('parameter names are lower_snake_case: %r' % name)
        self._entries[name] = _Entry(name, default, unit, doc, choices,
                                     cast or _infer_cast(default))
        self._order.append(name)
        return self

    # -- resolution ---------------------------------------------------------

    def env_name(self, name):
        return self._prefix + name.upper()

    def _unknown_env(self):
        harness = set(self._prefix + v for v in _HARNESS_VARS)
        out = []
        for key in os.environ:
            if not key.startswith(self._prefix) or key in harness:
                continue
            if key[len(self._prefix):].lower() not in self._entries:
                out.append(key)
        return sorted(out)

    def resolve(self):
        """Apply environment overrides, validate choices, then freeze."""
        unknown = self._unknown_env()
        for name in self._order:
            entry = self._entries[name]
            raw = os.environ.get(self.env_name(name))
            if raw is not None:
                try:
                    entry.value = entry.cast(raw)
                except (TypeError, ValueError) as exc:
                    raise ParamError('%s=%r is not valid for %s: %s'
                                     % (self.env_name(name), raw, name, exc))
                entry.source = 'env'
            if entry.choices is not None and entry.value not in entry.choices:
                raise ParamError('%s=%r not in %r'
                                 % (name, entry.value, entry.choices))
        self._frozen = True
        if unknown:
            # Do not fail: a shared shell may carry unrelated FLD_* variables.
            # But do say so, loudly. A mistyped override is otherwise completely
            # silent, and you will not notice that the sweep did nothing.
            print('  *** WARNING: unrecognised %s* environment variables '
                  '(typo?): %s' % (self._prefix, ', '.join(unknown)))
        return self

    # -- access -------------------------------------------------------------

    def __getattr__(self, name):
        # Reached only when normal attribute lookup fails, so the private
        # attributes set in __init__ are unaffected.
        entries = self.__dict__.get('_entries', {})
        if name in entries:
            if not self.__dict__.get('_frozen'):
                raise ParamError('read %r before resolve(); call P.resolve() '
                                 'once all parameters are declared' % name)
            return entries[name].value
        raise AttributeError(name)

    def __contains__(self, name):
        return name in self._entries

    def get(self, name, default=None):
        entry = self._entries.get(name)
        return entry.value if entry is not None else default

    def as_dict(self):
        return dict((n, self._entries[n].value) for n in self._order)

    # -- reporting ----------------------------------------------------------

    def show(self, printer=print):
        line = '  {0:<26} {1:>16}  {2:<9} {3:<4} {4}'
        printer('')
        printer('=' * 95)
        printer('PARAMETERS  [%s]   (override any of these with %s<NAME>)'
                % (self._study, self._prefix))
        printer('=' * 95)
        printer(line.format('name', 'value', 'unit', 'src', 'meaning'))
        printer('  ' + '-' * 91)
        for name in self._order:
            e = self._entries[name]
            shown = ('%.6g' % e.value) if isinstance(e.value, float) else str(e.value)
            printer(line.format(name, shown, e.unit,
                                'ENV' if e.source == 'env' else '', e.doc))
        printer('  ' + '-' * 91)
        changed = [n for n in self._order if self._entries[n].source == 'env']
        tail = (': ' + ', '.join(changed)) if changed else ''
        printer('  %d parameters, %d overridden from the environment%s'
                % (len(self._order), len(changed), tail))
        printer('')

    def write_json(self, path):
        """Dump the resolved parameters next to the job files, for the record."""
        import json
        payload = {
            'study': self._study,
            'params': self.as_dict(),
            'sources': dict((n, self._entries[n].source) for n in self._order),
            'units': dict((n, self._entries[n].unit) for n in self._order),
        }
        fh = open(path, 'w')
        try:
            json.dump(payload, fh, indent=2, sort_keys=True)
        finally:
            fh.close()
        return path


def workdir(default_sub='run'):
    """Where job files go.

    Abaqus must be able to write here, and on Windows the path must not contain
    a space if you are compiling a user subroutine: the Intel Fortran driver
    that Abaqus invokes does not quote it, and the compile fails with a message
    that never mentions the space. See docs/abaqus-launch-guide.md.

    Override with FLD_WORKDIR.
    """
    d = os.environ.get(_PREFIX + 'WORKDIR')
    if not d:
        d = os.path.join(os.path.expanduser('~'), 'abaqus-fld', default_sub)
    d = os.path.abspath(d)
    if not os.path.isdir(d):
        os.makedirs(d)
    return d
