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

import glob
import os

from abaqus import *
from abaqusConstants import *
from driverUtils import executeOnCaeStartup
import visualization

executeOnCaeStartup()

odb_path = os.environ['FLD_ANIM_ODB'].strip()
var = os.environ.get('FLD_ANIM_VAR', 'U').strip().upper()
out_dir = os.environ['FLD_ANIM_OUT'].strip()
n_want = int(os.environ.get('FLD_ANIM_N', '21').strip())
sync_mode = os.environ.get('FLD_ANIM_SYNC', 'disp').strip().lower()
max_depth_target = float(os.environ.get('FLD_ANIM_MAX_DEPTH', '0.14625').strip())

if not os.path.isdir(out_dir):
    os.makedirs(out_dir)
else:
    for old_f in glob.glob(os.path.join(out_dir, 'frame_*.png')):
        try:
            os.remove(old_f)
        except Exception:
            pass

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

# Find indenter instance to query penetration depth
inst_keys = list(odb.rootAssembly.instances.keys())
ind_key = None
for k in inst_keys:
    if 'IND' in k.upper():
        ind_key = k
        break

frame_depths = []
for idx, fr in enumerate(frames):
    depth = None
    if 'U' in fr.fieldOutputs and ind_key:
        ind_inst = odb.rootAssembly.instances[ind_key]
        sub = fr.fieldOutputs['U'].getSubset(region=ind_inst)
        if sub.values:
            v = sub.values[0]
            try:
                d = v.dataDouble
            except Exception:
                d = v.data
            depth = -d[2]
    frame_depths.append(depth)

has_valid_depths = any(d is not None for d in frame_depths)

if sync_mode == 'disp' and has_valid_depths:
    clean_depths = [d if d is not None else 0.0 for d in frame_depths]
    target_depths = [i * max_depth_target / float(max(1, n_want - 1))
                     for i in range(n_want)]
    picked_indices = []
    for td in target_depths:
        best_idx = 0
        best_diff = 1e9
        for idx, fd in enumerate(clean_depths):
            diff = abs(fd - td)
            if diff < best_diff:
                best_diff = diff
                best_idx = idx
        picked_indices.append(best_idx)
    log.write('mode=disp nframes=%d target_frames=%d max_target=%.4f m\n'
              % (n, n_want, max_depth_target))
    log.write('target_depths_mm: %s\n'
              % [round(td * 1000.0, 2) for td in target_depths])
    log.write('actual_depths_mm: %s\n'
              % [round(clean_depths[idx] * 1000.0, 2) for idx in picked_indices])
else:
    stride = max(1, (n - 1) // max(1, n_want - 1))
    picked_indices = [i for i in range(0, n, stride)][:n_want]
    if picked_indices[-1] != n - 1:
        picked_indices[-1] = n - 1
    log.write('mode=time nframes=%d stride=%d picked=%d\n'
              % (n, stride, len(picked_indices)))

log.write('step=%s picked_indices=%s\n' % (step_name, picked_indices))

for i, f_idx in enumerate(picked_indices):
    fr = frames[f_idx]
    vp.odbDisplay.setFrame(step=step_name, frame=f_idx)
    path = os.path.join(out_dir, 'frame_%03d' % i)
    session.printToFile(fileName=path, format=PNG, canvasObjects=(vp,))
    depth_str = (' depth_mm=%.2f' % (frame_depths[f_idx] * 1000.0)
                 if frame_depths[f_idx] is not None else '')
    log.write('wrote %s frameIdx=%d frameId=%s t=%s%s\n'
              % (path, f_idx, fr.frameId, fr.frameValue, depth_str))

log.close()
odb.close()
print('wrote %d frames to %s' % (len(picked_indices), out_dir))
