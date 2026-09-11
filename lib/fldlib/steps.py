"""Steps, time scaling and the quasi-static question.

The central difficulty of explicit large-displacement geotechnics
-----------------------------------------------------------------
Abaqus/Explicit is a dynamic solver. Caisson installation is not a dynamic
problem. You are using a dynamic solver to get a quasi-static answer, and the
whole art is in making the dynamics negligible without making the run take a
month.

The stable time increment is roughly ``dt = L_min / c_d`` where ``L_min`` is the
smallest element dimension and ``c_d`` the dilatational wave speed. For a soil
with E = 20 MPa, nu = 0.3, rho = 1650 kg/m3, ``c_d`` is about 130 m/s, so a
10 mm element gives ``dt ~ 7.7e-5 s``. Installing a caisson 0.5 m at a realistic
1 mm/s takes 500 s of real time -- 6.5 million increments. That is not going to
happen.

Three levers, in order of how much they can hurt you:

1. **Load rate scaling** (run the event faster than reality). Cheap, and for a
   rate-independent material it is free *if* the run stays quasi-static.
2. **Mass scaling** (make the material artificially heavier so ``dt`` rises).
   Also effectively a rate change: scaling mass by f scales ``dt`` by sqrt(f)
   and inertial forces by f.
3. **Reducing stiffness or coarsening the mesh.** Changes the answer directly.
   Last resort.

Whichever you use, the *acceptance test is the same* and it is not optional:

* kinetic energy ALLKE must stay small against internal energy ALLIE -- below
  about **5 %**, and below **1 %** if you want to quote the result;
* artificial strain (hourglass) energy ALLAE likewise below ~5 % of ALLIE;
* the total energy balance ETOTAL must stay near zero.

`postproc.energy` extracts exactly these and applies the test. Every example in
this repository runs it, and it is the first thing to look at when a result
looks wrong.
"""

from __future__ import print_function


def explicit_step(model, name, previous, time_period, nlgeom=True,
                  improved_dt=True, description=''):
    """A geometrically nonlinear `*Dynamic, Explicit` step.

    `nlgeom` is ON by default and you should essentially never turn it off in
    this repository: without it there is no large displacement, the ALE
    formulation is meaningless, and contact will behave strangely.

    `improved_dt` (`improvedDtMethod=ON`) gives a less conservative stable
    increment estimate for hex elements. It is the CAE default and typically
    buys 10-40 % on run time for free.
    """
    from abaqusConstants import ON, OFF
    return model.ExplicitDynamicsStep(
        name=name, previous=previous, description=description,
        timePeriod=time_period,
        nlgeom=ON if nlgeom else OFF,
        improvedDtMethod=ON if improved_dt else OFF,
    )


def geostatic_step(model, name='Geostatic', previous='Initial', nlgeom=True):
    """An Abaqus/Standard `*Geostatic` step.

    The usual pattern for a penetration analysis is: establish equilibrium under
    self-weight implicitly, then import that state into the explicit job with
    `*Import` / `InitialState`. It is far cheaper and far better conditioned
    than letting an explicit domain settle dynamically under gravity, which
    rings for a long time and pollutes the start of your penetration curve.

    There is one important exception: an Eulerian (CEL) domain cannot do this,
    because `*Geostatic` has no Eulerian implementation. See `cel.py`.
    """
    from abaqusConstants import ON, OFF
    step = model.GeostaticStep(name=name, previous=previous,
                               nlgeom=ON if nlgeom else OFF)
    return step


def mass_scaling(step, target_dt=None, factor=None, region=None,
                 throughout=True):
    """Apply semi-automatic mass scaling to a step.

    Exactly one of `target_dt` (scale mass so the stable increment reaches this
    value) or `factor` (scale by a fixed multiplier) must be given.

    `target_dt` is almost always the right choice: it scales only the elements
    that need it, which is usually a handful of small elements near the
    structure, rather than making the whole domain heavier. `throughout=True`
    re-evaluates during the step, which matters here because the critical
    element changes as the mesh deforms.

    Then go and check ALLKE/ALLIE. Mass scaling does not warn you when it has
    turned your quasi-static problem into a dynamic one; it just gives you a
    wrong answer quickly.
    """
    from abaqusConstants import (SEMI_AUTOMATIC, BELOW_MIN, THROUGHOUT_STEP,
                                 AT_BEGINNING, UNIFORM)

    if (target_dt is None) == (factor is None):
        raise ValueError('give exactly one of target_dt or factor')

    when = THROUGHOUT_STEP if throughout else AT_BEGINNING
    if target_dt is not None:
        entry = (SEMI_AUTOMATIC, region, when, 0.0, target_dt, BELOW_MIN,
                 1, 0, 0.0, 0.0, 0, None)
    else:
        entry = (SEMI_AUTOMATIC, region, when, factor, 0.0, None,
                 1, 0, 0.0, 0.0, 0, None)
    step.setValues(massScaling=(entry,))
    return step


def smooth_ramp(model, name='Ramp', t_ramp=0.05, t_total=1.0):
    """A `SMOOTH STEP` amplitude ramping 0 -> 1 over the first `t_ramp` fraction.

    Applying a velocity boundary condition as a step change puts a stress wave
    through the whole model on the first increment. A smooth-step ramp over the
    first few percent of the step removes that, at negligible cost in run time,
    and it is the difference between a clean penetration curve and one with a
    large spurious spike at zero displacement.

    `SMOOTH STEP` (fifth-order polynomial, zero first and second derivatives at
    both ends) is preferred over a linear ramp because the acceleration is also
    continuous.
    """
    from abaqusConstants import STEP
    t1 = t_ramp * t_total
    return model.SmoothStepAmplitude(name=name, timeSpan=STEP,
                                     data=((0.0, 0.0), (t1, 1.0)))


def energy_output(model, step_name, interval=100):
    """Request the history output you need to judge whether the run was quasi-static.

    ALLIE  internal energy            -- the reference for everything else
    ALLKE  kinetic energy             -- must stay < ~5 % of ALLIE
    ALLAE  artificial strain energy   -- hourglass control; < ~5 % of ALLIE
    ALLDC  distortion control energy  -- normally ~0; nonzero means the penalty
                                         is doing real work, which is a warning
    ALLVD  viscous dissipation        -- bulk viscosity and material damping
    ALLWK  external work
    ETOTAL total energy balance       -- must stay near zero

    This is cheap and there is no reason ever to omit it.
    """
    return model.HistoryOutputRequest(
        name='Energies', createStepName=step_name,
        variables=('ALLIE', 'ALLKE', 'ALLAE', 'ALLDC', 'ALLVD', 'ALLWK',
                   'ALLPD', 'ALLSE', 'ETOTAL'),
        numIntervals=interval,
    )


def estimate_stable_increment(min_element_size, youngs, poisson, density):
    """Rough `dt_stable` from the dilatational wave speed. Use it to sanity-check
    the number Abaqus reports in the `.sta` header, and to work out up front
    whether a run is feasible before you queue it for three days.

    Returns ``(dt_seconds, wave_speed_m_per_s)``.
    """
    lam_factor = (1.0 - poisson) / ((1.0 + poisson) * (1.0 - 2.0 * poisson))
    c_d = (youngs * lam_factor / density) ** 0.5
    return min_element_size / c_d, c_d


def report_time_budget(min_element_size, youngs, poisson, density,
                       travel, velocity, printer=print):
    """Print the increment count a run will need, before you submit it.

    This single function has saved more machine-weeks than anything else in the
    library. Run it, look at the number, and if it is above a few million,
    change something now rather than in three days.
    """
    dt, c_d = estimate_stable_increment(min_element_size, youngs, poisson,
                                        density)
    t_event = travel / float(velocity)
    n_inc = t_event / dt
    printer('  wave speed           %10.1f m/s' % c_d)
    printer('  stable increment     %10.3e s   (L_min = %.4g m)'
            % (dt, min_element_size))
    printer('  event duration       %10.4g s   (%.4g m at %.4g m/s)'
            % (t_event, travel, velocity))
    printer('  increments required  %10.3e' % n_inc)
    if n_inc > 5.0e6:
        printer('  *** WARNING: %.1e increments. Raise the velocity, apply '
                'mass scaling, or coarsen the mesh -- and then check ALLKE. ***'
                % n_inc)
    return {'dt': dt, 'c_d': c_d, 't_event': t_event, 'n_inc': n_inc}
