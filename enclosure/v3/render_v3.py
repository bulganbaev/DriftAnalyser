"""Offscreen VTK renders of the v3 enclosure concept (STL per part, colours, PNG 1600x1100)."""
import os
import tempfile

import cadquery as cq
import vtk

W, H = 1600, 1100
NO_LID = ("lid", "screws", "sleeve", "lug", "cable", "washer", "bolt", "cap")   # name prefixes (per-stud parts: lug_J2 ...)


def _stl(shape, path):
    cq.exporters.export(shape, path, tolerance=0.03, angularTolerance=0.15)
    return path


def _actor(path, col, offset=(0, 0, 0), opacity=1.0):
    r = vtk.vtkSTLReader()
    r.SetFileName(path)
    n = vtk.vtkPolyDataNormals()
    n.SetInputConnection(r.GetOutputPort())
    n.SetFeatureAngle(35)
    n.SplittingOn()
    m = vtk.vtkPolyDataMapper()
    m.SetInputConnection(n.GetOutputPort())
    a = vtk.vtkActor()
    a.SetMapper(m)
    p = a.GetProperty()
    p.SetColor(*col)
    p.SetOpacity(opacity)
    p.SetInterpolationToPhong()
    p.SetAmbient(0.12)
    p.SetDiffuse(0.85)
    p.SetSpecular(0.35)
    p.SetSpecularPower(30)
    a.SetPosition(*offset)
    return a


def _shot(actors, out, pos, focal, zoom=1.0, up=(0, 0, 1)):
    ren = vtk.vtkRenderer()
    ren.SetBackground(1, 1, 1)
    for a in actors:
        ren.AddActor(a)
    kit = vtk.vtkLightKit()
    kit.SetKeyLightIntensity(0.9)
    kit.AddLightsToRenderer(ren)
    try:
        ren.UseSSAOOn()
        ren.SetSSAORadius(6.0)
        ren.SetSSAOBias(0.05)
        ren.SetSSAOKernelSize(128)
    except AttributeError:
        pass
    cam = ren.GetActiveCamera()
    cam.SetFocalPoint(*focal)
    cam.SetPosition(*pos)
    cam.SetViewUp(*up)
    cam.SetViewAngle(25)
    ren.ResetCamera()
    cam.SetFocalPoint(*focal)
    cam.Zoom(zoom)
    ren.ResetCameraClippingRange()
    win = vtk.vtkRenderWindow()
    win.SetOffScreenRendering(1)
    win.SetMultiSamples(8)
    win.AddRenderer(ren)
    win.SetSize(W, H)
    win.Render()
    w2i = vtk.vtkWindowToImageFilter()
    w2i.SetInput(win)
    w2i.Update()
    wr = vtk.vtkPNGWriter()
    wr.SetFileName(out)
    wr.SetInputConnection(w2i.GetOutputPort())
    wr.Write()
    print("render", out)


def render_all(parts, out_dir):
    tmp = tempfile.mkdtemp(prefix="da3_render_")
    files = {name: (_stl(shp, os.path.join(tmp, name + ".stl")), col, off) for name, shp, col, off in parts}

    def actors(skip=(), exploded=False):
        return [_actor(f, c, o if exploded else (0, 0, 0)) for k, (f, c, o) in files.items()
                if not k.startswith(tuple(skip))]

    c = (27.5, -52.0, 18.0)
    _shot(actors(skip=("gasket", "tpads")), os.path.join(out_dir, "render-closed-connector.png"),
          (-110, 190, 120), (27.5, -30.0, 18.0), 2.0)
    _shot(actors(skip=("gasket", "tpads")), os.path.join(out_dir, "render-closed-stud-antenna.png"),
          (230, -280, 170), (27.5, -65.0, 30.0), 1.9)
    _shot(actors(skip=NO_LID + ("gasket",)), os.path.join(out_dir, "render-open.png"),
          (160, 120, 200), c, 1.9)
    _shot(actors(exploded=True), os.path.join(out_dir, "render-exploded.png"),
          (270, 200, 190), (35.0, -45.0, 70.0), 1.45)
    _shot(actors(skip=("gasket", "tpads")), os.path.join(out_dir, "render-top-studs.png"),
          (29.0, -95.0, 400.0), (29.0, -95.0, 30.0), 2.4, up=(0, 1, 0))
