# Brief 04 - example 05, ALE and parallel decomposition

**Cost:** moderate; the cases are short by design. **Needs:** **15 CPUs** to
reproduce the documented result. Fewer works, but the numbers will not match.

```bash
set FLD_NCPU=15
set FLD_NDOMAINS=15
abaqus cae noGUI=examples/ex05_ale_parallel/model.py
```

## Replication against docs/03-ale-multi-region-parallel.md

| Documented | Reproduced? |
|---|---|
| A (no ALE): balanced, all weights ~6.67 | |
| B (one region): one domain inflated to weight ~15.1 | |
| C (two separated): two domains inflated to ~8.2 each, on **different** ranks | |
| **D (four separated): perfectly balanced, ~6.67** | |
| E (two adjacent): identical to B | |
| NONADAPTIVE node counts rise with fragmentation (1922 -> 3048) | |

The per-domain weights come from the packager's decomposition report in the
`.sta`. Extract them and put the table in the report.

## Method note

`parse_domain_map()` scans `<job>.msg*` and reports which domains contain
adaptive diagnostics. Confirm the `.msg.N` files exist and are per-domain. If
your Abaqus version writes a single combined `.msg`, the region-to-domain
mapping cannot be recovered this way and the function needs rewriting - say so
rather than working around it.

## If you have fewer than 15 CPUs

Run it anyway with `FLD_NCPU` set to what you have, and report the numbers. The
qualitative result - separated regions distribute, adjacent regions do not -
should hold at any core count, and confirming that is still worth having.

## Report

The decomposition weight table, the region-to-domain mapping, and the
NONADAPTIVE node counts.
