# Indenter models

One strip pushed into a soil block. Five complete scripts. Open two and diff
them. That is how you see what each formulation adds.

```bash
set FLD_WORKDIR=C:\abq\run
set FLD_SUBMIT=0
abaqus cae noGUI=examples/indenter/implicit/model.py
```

| Folder | What it is |
|---|---|
| [`implicit/`](implicit/) | Abaqus/Standard `*Static`. Stops on convergence. |
| [`implicit_ale/`](implicit_ale/) | the same, plus ALE |
| [`explicit/`](explicit/) | Abaqus/Explicit. Distorts instead. |
| [`explicit_ale/`](explicit_ale/) | Explicit plus ALE |
| [`explicit_cel/`](explicit_cel/) | Explicit CEL |

The notes that go with the diffs are in [`teaching/formulations.pdf`](../../teaching/formulations.pdf).
