# fe-large-displacement

Abaqus models for large-displacement geotechnics. One strip-indenter problem
in five formulations, plus a suction caisson installation.

## Start here

1. [`teaching/software.pdf`](teaching/software.pdf) — how to read the software.
2. [`teaching/formulations.pdf`](teaching/formulations.pdf) — what to change at each formulation.
3. Run the implicit indenter and watch it fail.

```bash
set FLD_WORKDIR=C:\abq\run
set FLD_SUBMIT=0
abaqus cae noGUI=examples/indenter/implicit/model.py
```

`FLD_WORKDIR` must have no spaces if you compile a user subroutine.
`FLD_SUBMIT=0` writes and checks the deck without solving. Omit it to submit.

## Models

| | |
|---|---|
| [`examples/indenter/implicit`](examples/indenter/implicit/) | Abaqus/Standard, `*Static` |
| [`examples/indenter/implicit_ale`](examples/indenter/implicit_ale/) | Standard + ALE |
| [`examples/indenter/explicit`](examples/indenter/explicit/) | Abaqus/Explicit |
| [`examples/indenter/explicit_ale`](examples/indenter/explicit_ale/) | Explicit + ALE |
| [`examples/indenter/explicit_cel`](examples/indenter/explicit_cel/) | Explicit CEL |
| [`examples/suction_caisson`](examples/suction_caisson/) | jacked then suction. No seepage |

Each indenter script is complete. Open two and diff them. Further notes
are in [`docs/`](docs/). A single-element UMAT/VUMAT check is
[`constitutive/single_element/`](constitutive/single_element/).

## Licence

MIT for the repository-authored files, except `constitutive/`. Each model
there has its own terms. See [`NOTICE.md`](NOTICE.md).
