"""Dump a PNG sequence of the deformed mesh from an ODB.

    set FLD_ANIM_ODB=C:\\abq\\run\\implicit.odb
    set FLD_ANIM_INST=SoilInst
    set FLD_ANIM_OUT=C:\\abq\\run\\frames_soil
    set FLD_ANIM_N=40
    abaqus viewer noGUI=lib/postproc/animate.py

FLD_ANIM_INST is a substring match on the ODB instance name (blank = all).
"""
from __future__ import print_function

import os

from abaqus import *
from abaqusConstants import *
from driverUtils import executeOnCaeStartup
import visualization
import displayGroupOdbToolset as dgo

executeOnCaeStartup()

odb_path = os.environ['FLD_ANIM_ODB']
want_inst = os.environ.get('FLD_ANIM_INST', '').strip()
out_dir = os.environ['FLD_ANIM_OUT']
n_want = int(os.environ.get('FLD_ANIM_N', '40'))

if not os.path.isdir(out_dir):
    os.makedirs(out_dir)

odb = visualization.openOdb(path=odb_path)
vp = session.viewports['Viewport: 1']
vp.setValues(displayedObject=odb)
vp.viewportAnnotationOptions.setValues(
    triad=OFF, title=OFF, state=OFF, legend=OFF, compass=OFF)

inst_names = list(odb.rootAssembly.instances.keys())
log = open(os.path.join(out_dir, 'animate.log'), 'w')
log.write('instances: %s\n' % inst_names)

if want_inst:
    match = [n for n in inst_names if want_inst.upper() in n.upper()]
    if not match:
        log.write('no instance matching %r\n' % want_inst)
        log.close()
        raise RuntimeError('no instance matching %r in %s' % (want_inst, inst_names))
    leaf = dgo.LeafFromPartInstance(partInstanceName=(match[0],))
    vp.odbDisplay.displayGroup.replace(leaf=leaf)
    log.write('showing %s\n' % match[0])

fields = []
try:
    fields = list(odb.steps.values()[-1].frames[-1].fieldOutputs.keys())
except Exception:
    pass
log.write('fields: %s\n' % fields[:20])

vp.odbDisplay.display.setValues(plotState=(DEFORMED,))

vp.odbDisplay.commonOptions.setValues(
    visibleEdges=EXTERIOR, renderStyle=SHADED,
    deformationScaling=UNIFORM, uniformScaleFactor=1.0)
vp.view.setValues(session.views['Iso'])
vp.view.fitView()

session.printOptions.setValues(vpDecorations=OFF, reduceColors=False)
session.pngOptions.setValues(imageSize=(720, 480))

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
