# Reading list — suction caisson

The script [`suction_caisson.py`](suction_caisson.py) is a dry, total-stress
introduction. It applies suction as a lid force and does not model seepage
through the plug. These papers are the next step: installation, drainage, and
what that does to later cyclic response. BibTeX is in
[`suction_caisson.bib`](suction_caisson.bib).

Read in this order.

**Staubach et al. (2020)** — installation in sand.
Impact driving and jacking in CEL with hypoplasticity, drained or partially
drained. Quarter model. Pore pressure carried in the constitutive subroutine.
The wished-in-place assumption is conservative in medium dense sand and
unconservative in dense sand.

Staubach, P., Machaček, J., Moscoso, M. C. and Wichtmann, T. (2020). Impact of
the installation on the long-term cyclic behaviour of piles in sand: a numerical
study. *Soil Dynamics and Earthquake Engineering* 138, 106223.
https://doi.org/10.1016/j.soildyn.2020.106223

**Staubach et al. (2023)** — installation in clay, then many lateral cycles.
Hydro-mechanically coupled CEL, then a high-cycle accumulation model.
Wished-in-place is usually conservative for rotation. Installation still
changes small-rotation stiffness, which matters for a later macro-element.

Staubach, P., Tschirschky, L., Machaček, J. and Wichtmann, T. (2023). Monopile
installation in clay and subsequent response to millions of lateral load cycles.
*Computers and Geotechnics* 155, 105221.
https://doi.org/10.1016/j.compgeo.2022.105221

**Tschirschky et al. (2025)** — suction caisson under high-cyclic vertical load.
Hydro-mechanically coupled FE, hypoplasticity with intergranular strain and a
high-cycle accumulation model, checked against a centrifuge test. Pore pressure
governs load transfer in a storm. Drainage conditions control the long-term
settlement.

Tschirschky, L., Staubach, P., Machaček, J., Bienen, B. and Wichtmann, T.
(2025). Numerical investigations on the long-term behaviour of suction-caisson
foundations under high-cyclic loading. In *Proceedings of ISFOG 2025*,
pp. 2048–2053. https://doi.org/10.53243/ISFOG2025-195

**Kazemi Esfeh et al. (2026)** — large-deformation hydro-mechanics in saturated
sand.
Vibro-driving of open-ended piles, not a caisson, but the same class of model:
permeability, excess pore pressure, and how the soil state evolves during
penetration.

Kazemi Esfeh, P., Bienen, B., Bransby, M. F. and Staubach, P. (2026). A
numerical study on effects of soil permeability and vibratory parameters on
vibro-driving of open-ended piles in saturated sand. *Ocean Engineering* 351,
124407. https://doi.org/10.1016/j.oceaneng.2026.124407
