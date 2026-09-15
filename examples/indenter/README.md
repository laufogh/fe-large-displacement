# Indenter models

One physical problem, five formulations. A rigid strip indenter is pushed into
a soil block. Geometry, mesh, material and contact stay the same except where
the formulation itself requires a change (Eulerian elements and void space for
CEL). Differences in the result are then caused by the formulation.

```bash
set FLD_WORKDIR=C:\abq\run
set FLD_SUBMIT=0
abaqus cae noGUI=examples/indenter/implicit/model.py
```

| Folder | Solver | What changes |
|---|---|---|
| [`implicit/`](implicit/) | Abaqus/Standard `*Static` | nothing. It stops on convergence. |
| [`implicit_ale/`](implicit_ale/) | Standard + ALE | an adaptive mesh domain on the static step. Standard ALE is limited. |
| [`explicit/`](explicit/) | Abaqus/Explicit `*Dynamic, Explicit` | no convergence to lose. Distorts instead. Cases B and C are the energy test and distortion control. |
| [`explicit_ale/`](explicit_ale/) | Explicit + ALE | nodes move relative to material. Topology is fixed. |
| [`explicit_cel/`](explicit_cel/) | Explicit CEL | material flows through a fixed mesh. |

Shared builder: [`examples/common/indenter_model.py`](../common/indenter_model.py).
What to change in the scripts is written in [`teaching/formulations.pdf`](../../teaching/formulations.pdf).
Measured ALE, section-control and CEL findings stay in [`docs/`](../../docs/).
