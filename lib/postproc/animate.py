"""PNG sequence of soil deformation, side view (XZ), penetration downward.

    set FLD_ANIM_ODB=C:\\abq\\run\\implicit.odb
    set FLD_ANIM_VAR=U
    set FLD_ANIM_OUT=...\\media\\frames\\implicit
    set FLD_ANIM_N=40
    abaqus viewer noGUI=lib/postproc/animate.py

FLD_ANIM_VAR is U (displacement magnitude) or EVF (Eulerian volume fraction).
Show soil and indenter. Camera looks along +Y so the strip is seen in plane
and the indenter moves down the page.
"""
from __future__ import print_function

import os

from abaqus import *
from abaqusConstants import *
from driverUtils import executeOnCaeStartup
import visualization

executeOnCaeStartup()

odb_path = os.environ['FLD_ANIM_ODB']
var = os.environ.get('FLD_ANIM_VAR', 'U').strip().upper()
out_dir = os.environ['FLD_ANIM_OUT']
n_want = int(os.environ.get('FLD_ANIM_N', '40'))

if not os.path.isdir(out_dir):
    os.makedirs(out_dir)

odb = visualization.openOdb(path=odb_path)
vp = session.viewports['Viewport: 1']
vp.setValues(displayedObject=odb)
try:
    vp.setValues(titleBar=OFF)
except Exception:
    pass
vp.viewportAnnotationOptions.setValues(
    triad=OFF, title=OFF, state=OFF, legend=ON, compass=OFF,
    legendBox=OFF)

log = open(os.path.join(out_dir, 'animate.log'), 'w')
fields = []
try:
    fields = list(odb.steps.values()[-1].frames[-1].fieldOutputs.keys())
except Exception:
    pass
log.write('fields: %s\n' % fields[:24])

vp.odbDisplay.display.setValues(plotState=(CONTOURS_ON_DEF,))
if var == 'EVF':
    evf = None
    for name in fields:
        u = name.upper()
        if 'EVF' in u and 'SOIL' in u:
            evf = name
            break
    if evf is None:
        for name in fields:
            if name.upper() == 'EVF_VOID':
                evf = name
                break
    if evf is None:
        log.write('no EVF field\n')
        log.close()
        raise RuntimeError('no EVF field in %s' % fields)
    vp.odbDisplay.setPrimaryVariable(
        variableLabel=evf, outputPosition=INTEGRATION_POINT)
    vp.odbDisplay.contourOptions.setValues(
        maxAutoCompute=OFF, maxValue=1.0,
        minAutoCompute=OFF, minValue=0.0)
    log.write('contour %s INTEGRATION_POINT 0-1\n' % evf)
else:
    vp.odbDisplay.setPrimaryVariable(
        variableLabel='U', outputPosition=NODAL,
        refinement=(INVARIANT, 'Magnitude'))
    vp.odbDisplay.contourOptions.setValues(
        maxAutoCompute=OFF, maxValue=0.16,
        minAutoCompute=OFF, minValue=0.0)
    log.write('contour U magnitude 0-0.16 m\n')

vp.odbDisplay.commonOptions.setValues(
    visibleEdges=EXTERIOR, renderStyle=SHADED,
    deformationScaling=UNIFORM, uniformScaleFactor=1.0)

# Look along +Y at the XZ plane. +Z is up, so penetration (-Z) is down.
vp.view.setValues(
    cameraPosition=(0.0, 1.0, 0.0),
    cameraTarget=(0.0, 0.0, 0.0),
    cameraUpVector=(0.0, 0.0, 1.0))
try:
    vp.view.setValues(projection=PARALLEL)
except Exception:
    pass
vp.view.fitView()

session.printOptions.setValues(vpDecorations=ON, reduceColors=False)
session.pngOptions.setValues(imageSize=(640, 400))

step_name = odb.steps.keys()[-1]
frames = odb.steps[step_name].frames
n = len(frames)
stride = max(1, (n - 1) // max(1, n_want - 1))
picked = [frames[i] for i in range(0, n, stride)][:n_want]
if picked[-1] is not frames[-1]:
    picked[-1] = frames[-1]

log.write('step=%s nframes=%d stride=%d picked=%d\n'
          % (step_name, n, stride, len(picked)))

for i, fr in enumerate(picked):
    vp.odbDisplay.setFrame(step=step_name, frame=fr.frameId)
    path = os.path.join(out_dir, 'frame_%03d' % i)
    session.printToFile(fileName=path, format=PNG, canvasObjects=(vp,))
    log.write('wrote %s frameId=%s t=%s\n' % (path, fr.frameId, fr.frameValue))

log.close()
print('wrote %d frames to %s' % (len(picked), out_dir))
