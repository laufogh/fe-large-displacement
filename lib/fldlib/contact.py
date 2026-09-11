"""Contact for penetration problems.

General contact or surface-to-surface?
--------------------------------------
For large-displacement penetration, **general contact** is almost always right.
It builds an all-inclusive exterior surface, re-evaluates it as the model
deforms, and handles a soil surface that folds over onto itself -- which is
exactly what happens next to a penetrating skirt. Surface-to-surface pairs
require you to nominate the surfaces in advance, and the surface you nominated
stops being the surface in contact somewhere around 20 % penetration.

General contact is also mandatory for CEL: the Eulerian-Lagrangian interaction
is only available through it.

The reason to fall back to a pair is control. A pair lets you set the master,
the sliding formulation and the weighting explicitly, and it is much easier to
extract a clean contact force from. If you need a single well-defined
penetration resistance and the geometry is simple enough that the surfaces do
not change, a pair is fine.

Friction in a penetration problem
---------------------------------
The interface friction coefficient dominates skirt friction and therefore the
whole installation resistance. It is not a numerical parameter to be tuned for
convergence. A common starting point is ``mu = tan(delta)`` with
``delta ~ (0.5 to 0.8) * phi_critical_state``; for steel against silica sand
that lands around 0.3-0.5.

`PENALTY` friction is the practical choice in Explicit. `ROUGH` and exact
stick are expensive and fragile at large sliding.
"""

from __future__ import print_function


def friction_property(model, name='Interface', mu=0.4, hard=True,
                      stiffness=None):
    """Contact property with Coulomb friction and a normal behaviour.

    `hard=True` gives HARD pressure-overclosure, which is the default and is
    what you want unless you have a reason. A LINEAR penalty with an explicit
    `stiffness` is sometimes used to soften a very stiff interface and buy back
    some stable time increment; it also lets real penetration happen, so check
    it does not quietly let the structure sink into the soil.
    """
    from abaqusConstants import (PENALTY, ISOTROPIC, FRACTION, DEFAULT, HARD,
                                 LINEAR, ON, OFF)

    prop = model.ContactProperty(name)
    if hard:
        prop.NormalBehavior(pressureOverclosure=HARD,
                            allowSeparation=ON,
                            constraintEnforcementMethod=DEFAULT)
    else:
        if stiffness is None:
            raise ValueError('a LINEAR normal behaviour needs an explicit '
                             'contact stiffness')
        prop.NormalBehavior(pressureOverclosure=LINEAR,
                            contactStiffness=stiffness,
                            constraintEnforcementMethod=DEFAULT)
    prop.TangentialBehavior(
        formulation=PENALTY, directionality=ISOTROPIC,
        slipRateDependency=OFF, pressureDependency=OFF,
        temperatureDependency=OFF, dependencies=0,
        table=((mu,),), shearStressLimit=None,
        maximumElasticSlip=FRACTION, fraction=0.005,
        elasticSlipStiffness=None)
    return prop


def general_contact(model, step_name, prop_name, scale_penalty=None):
    """`*Contact, op=NEW` over the default all-exterior surface.

    `scale_penalty` scales the contact stiffness. Raising it reduces
    penetration of the structure into the soil but lowers the stable time
    increment; lowering it does the opposite. Leave it alone until you have
    measured actual penetration at the interface and found it unacceptable.
    """
    from abaqusConstants import GLOBAL, SELF

    interaction = model.ContactExp(name='GeneralContact',
                                   createStepName=step_name)
    interaction.includedPairs.setValuesInStep(stepName=step_name,
                                              useAllstar=True)
    interaction.contactPropertyAssignments.appendInStep(
        stepName=step_name, assignments=((GLOBAL, SELF, prop_name),))
    if scale_penalty:
        model.ExpContactControl(name='ContactControl',
                                scalePenalty=scale_penalty)
        interaction.setValues(contactControls='ContactControl')
    return interaction


def general_contact_std(model, step_name, prop_name):
    """General contact for Abaqus/Standard.

    Available since Abaqus 6.14 and much improved since; it is the right choice
    for the implicit baseline in example 01 so that the implicit and explicit
    runs differ in as few respects as possible.

    It is *not* free in Standard the way it is in Explicit -- the all-inclusive
    surface generation costs real time on a large model, and the contact
    stabilisation that Standard applies to get through the first increments is
    another fictitious force you have to check afterwards.
    """
    from abaqusConstants import GLOBAL, SELF

    interaction = model.ContactStd(name='GeneralContact',
                                   createStepName=step_name)
    interaction.includedPairs.setValuesInStep(stepName=step_name,
                                              useAllstar=True)
    interaction.contactPropertyAssignments.appendInStep(
        stepName=step_name, assignments=((GLOBAL, SELF, prop_name),))
    return interaction


def surface_pair(model, step_name, name, master, slave, prop_name,
                 weighting=1.0):
    """A surface-to-surface pair, master-dominated.

    `weighting=1.0` means pure master-slave with the master (normally the
    structure) controlling. That is the right choice when the structure is much
    stiffer than the soil, which it is here. Balanced weighting (0.5) is the
    Abaqus default and is better for contact between bodies of similar
    stiffness.
    """
    from abaqusConstants import FINITE, PENALTY, SPECIFIED, OMIT

    return model.SurfaceToSurfaceContactExp(
        name=name, createStepName=step_name,
        master=master, slave=slave,
        sliding=FINITE, interactionProperty=prop_name,
        mechanicalConstraint=PENALTY,
        weightingFactorType=SPECIFIED, weightingFactor=weighting,
        initialClearance=OMIT, datumAxis=None, clearanceRegion=None)
