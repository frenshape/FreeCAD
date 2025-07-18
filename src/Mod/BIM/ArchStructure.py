# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2011 Yorik van Havre <yorik@uncreated.net>              *
# *                                                                         *
# *   This file is part of FreeCAD.                                         *
# *                                                                         *
# *   FreeCAD is free software: you can redistribute it and/or modify it    *
# *   under the terms of the GNU Lesser General Public License as           *
# *   published by the Free Software Foundation, either version 2.1 of the  *
# *   License, or (at your option) any later version.                       *
# *                                                                         *
# *   FreeCAD is distributed in the hope that it will be useful, but        *
# *   WITHOUT ANY WARRANTY; without even the implied warranty of            *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU      *
# *   Lesser General Public License for more details.                       *
# *                                                                         *
# *   You should have received a copy of the GNU Lesser General Public      *
# *   License along with FreeCAD. If not, see                               *
# *   <https://www.gnu.org/licenses/>.                                      *
# *                                                                         *
# ***************************************************************************

#Modified 2016-01-03 JAndersM

__title__= "FreeCAD Structure"
__author__ = "Yorik van Havre"
__url__ = "https://www.freecad.org"

## @package ArchStructure
#  \ingroup ARCH
#  \brief The Structure object and tools
#
#  This module provides tools to build Structure objects.
#  Structure elements are beams, columns, slabs, and other
#  elements that have a structural function, that is, that
#  support other parts of the building.

import FreeCAD
import ArchComponent
import ArchCommands
import ArchProfile
import Draft
import DraftVecUtils

from FreeCAD import Vector
from draftutils import params
from draftutils import gui_utils

if FreeCAD.GuiUp:
    from PySide import QtCore, QtGui
    from PySide.QtCore import QT_TRANSLATE_NOOP
    import FreeCADGui
    import ArchPrecast
    import draftguitools.gui_trackers as DraftTrackers
    from draftutils.translate import translate
else:
    # \cond
    def translate(ctxt,txt):
        return txt
    def QT_TRANSLATE_NOOP(ctxt,txt):
        return txt
    # \endcond


#Reads preset profiles and categorizes them
Categories=[]
Presets=ArchProfile.readPresets()
for pre in Presets:
    if pre[1] not in Categories:
        Categories.append(pre[1])


def makeStructure(baseobj=None,length=None,width=None,height=None,name=None):

    '''makeStructure([baseobj],[length],[width],[height],[name]): creates a
    structure element based on the given profile object and the given
    extrusion height. If no base object is given, you can also specify
    length and width for a cubic object.'''

    if not FreeCAD.ActiveDocument:
        FreeCAD.Console.PrintError("No active document. Aborting\n")
        return
    obj = FreeCAD.ActiveDocument.addObject("Part::FeaturePython","Structure")
    _Structure(obj)
    if FreeCAD.GuiUp:
        _ViewProviderStructure(obj.ViewObject)
    if baseobj:
        obj.Base = baseobj
        if FreeCAD.GuiUp:
            obj.Base.ViewObject.hide()
    if width:
        obj.Width = width
    else:
        obj.Width = params.get_param_arch("StructureWidth")
    if height:
        obj.Height = height
    else:
        if not length:
            obj.Height = params.get_param_arch("StructureHeight")
    if length:
        obj.Length = length
    else:
        if not baseobj:
            # don't set the length if we have a base object, otherwise the length X height calc
            # gets wrong
            obj.Length = params.get_param_arch("StructureLength")
    if baseobj:
        w = 0
        h = 0
        if hasattr(baseobj,"Width") and hasattr(baseobj,"Height"):
            w = baseobj.Width.Value
            h = baseobj.Height.Value
        elif hasattr(baseobj,"Length") and hasattr(baseobj,"Width"):
            w = baseobj.Length.Value
            h = baseobj.Width.Value
        elif hasattr(baseobj,"Length") and hasattr(baseobj,"Height"):
            w = baseobj.Length.Value
            h = baseobj.Height.Value
        if w and h:
            if length and not height:
                obj.Width = w
                obj.Height = h
            elif height and not length:
                obj.Width = w
                obj.Length = h

    if not height and not length:
        obj.IfcType = "Building Element Proxy"
        obj.Label = name if name else translate("Arch","Structure")
    elif obj.Length > obj.Height:
        obj.IfcType = "Beam"
        obj.Label = name if name else translate("Arch","Beam")
    elif obj.Height > obj.Length:
        obj.IfcType = "Column"
        obj.Label = name if name else translate("Arch","Column")
    return obj

def makeStructuralSystem(objects=[],axes=[],name=None):

    '''makeStructuralSystem([objects],[axes],[name]): makes a structural system
    based on the given objects and axes'''

    if not FreeCAD.ActiveDocument:
        FreeCAD.Console.PrintError("No active document. Aborting\n")
        return
    result = []
    if not axes:
        print("At least one axis must be given")
        return
    if objects:
        if not isinstance(objects,list):
            objects = [objects]
    else:
        objects = [None]
    for o in objects:
        obj = FreeCAD.ActiveDocument.addObject("Part::FeaturePython","StructuralSystem")
        obj.Label = name if name else translate("Arch","StructuralSystem")
        _StructuralSystem(obj)
        if FreeCAD.GuiUp:
            _ViewProviderStructuralSystem(obj.ViewObject)
        if o:
            obj.Base = o
        obj.Axes = axes
        result.append(obj)
        if FreeCAD.GuiUp and o:
            o.ViewObject.hide()
            Draft.formatObject(obj,o)
    FreeCAD.ActiveDocument.recompute()
    if len(result) == 1:
        return result[0]
    else:
        return result

def placeAlongEdge(p1,p2,horizontal=False):

    """placeAlongEdge(p1,p2,[horizontal]): returns a Placement positioned at p1, with Z axis oriented towards p2.
    If horizontal is True, then the X axis is oriented towards p2, not the Z axis"""

    pl = FreeCAD.Placement()
    pl.Base = p1
    import WorkingPlane
    up = WorkingPlane.get_working_plane(update=False).axis
    zaxis = p2.sub(p1)
    yaxis = up.cross(zaxis)
    if yaxis.Length > 0:
        xaxis = zaxis.cross(yaxis)
        if horizontal:
            pl.Rotation = FreeCAD.Rotation(zaxis,yaxis,xaxis,"ZXY")
        else:
            pl.Rotation = FreeCAD.Rotation(xaxis,yaxis,zaxis,"ZXY")
            pl.Rotation = FreeCAD.Rotation(pl.Rotation.multVec(FreeCAD.Vector(0,0,1)),90).multiply(pl.Rotation)
    return pl


class CommandStructuresFromSelection:
    """ The Arch Structures from selection command definition. """

    def __init__(self):
        pass

    def GetResources(self):
        return {'Pixmap': 'Arch_MultipleStructures',
                'MenuText': QT_TRANSLATE_NOOP("Arch_StructuresFromSelection", "Multiple Structures"),
                'ToolTip': QT_TRANSLATE_NOOP("Arch_StructuresFromSelection", "Create multiple BIM Structures from a selected base, using each selected edge as an extrusion path")}

    def IsActive(self):
        v = hasattr(FreeCADGui.getMainWindow().getActiveWindow(), "getSceneGraph")
        return v

    def Activated(self):
        selex = FreeCADGui.Selection.getSelectionEx()
        if len(selex) >= 2:
            FreeCAD.ActiveDocument.openTransaction(translate("Arch", "Create Structures From Selection"))
            FreeCADGui.addModule("Arch")
            FreeCADGui.addModule("Draft")
            base = selex[0].Object # The first selected object is the base for the Structure objects
            for selexi in selex[1:]: # All the edges from the other objects are used as a Tool (extrusion paths)
                if len(selexi.SubElementNames) == 0:
                    subelement_names = ["Edge" + str(i) for i in range(1, len(selexi.Object.Shape.Edges) + 1)]
                else:
                    subelement_names = [sub for sub in selexi.SubElementNames if sub.startswith("Edge")]
                for sub in subelement_names:
                    FreeCADGui.doCommand("structure = Arch.makeStructure(FreeCAD.ActiveDocument." + base.Name + ")")
                    FreeCADGui.doCommand("structure.Tool = (FreeCAD.ActiveDocument." + selexi.Object.Name + ", '" + sub + "')")
                    FreeCADGui.doCommand("structure.BasePerpendicularToTool = True")
                    FreeCADGui.doCommand("Draft.autogroup(structure)")
            FreeCAD.ActiveDocument.commitTransaction()
            FreeCAD.ActiveDocument.recompute()
        else:
            FreeCAD.Console.PrintError(translate("Arch", "Please select the base object first and then the edges to use as extrusion paths") + "\n")


class CommandStructuralSystem:
    """ The Arch Structural System command definition. """

    def __init__(self):
        pass

    def GetResources(self):
        return {'Pixmap': 'Arch_StructuralSystem',
                'MenuText': QT_TRANSLATE_NOOP("Arch_StructuralSystem", "Structural System"),
                'ToolTip': QT_TRANSLATE_NOOP("Arch_StructuralSystem", "Create a structural system from a selected structure and axis")}

    def IsActive(self):
        return not FreeCAD.ActiveDocument is None

    def Activated(self):
        sel = FreeCADGui.Selection.getSelection()
        if sel:
            st = Draft.getObjectsOfType(sel, "Structure")
            ax = Draft.getObjectsOfType(sel, "Axis")
            if ax:
                FreeCAD.ActiveDocument.openTransaction(translate("Arch", "Create Structural System"))
                FreeCADGui.addModule("Arch")
                if st:
                    FreeCADGui.doCommand("obj = Arch.makeStructuralSystem(" + ArchCommands.getStringList(st) + ", " + ArchCommands.getStringList(ax) + ")")
                else:
                    FreeCADGui.doCommand("obj = Arch.makeStructuralSystem(axes = " + ArchCommands.getStringList(ax) + ")")
                FreeCADGui.addModule("Draft")
                FreeCADGui.doCommand("Draft.autogroup(obj)")
                FreeCAD.ActiveDocument.commitTransaction()
                FreeCAD.ActiveDocument.recompute()
            else:
                FreeCAD.Console.PrintError(translate("Arch", "Please select at least an axis object") + "\n")


class _CommandStructure:

    "the Arch Structure command definition"

    def __init__(self):

        self.beammode = False

    def GetResources(self):

        return {'Pixmap'  : 'Arch_Structure',
                'MenuText': QT_TRANSLATE_NOOP("Arch_Structure","Structure"),
                'Accel': "S, T",
                'ToolTip': QT_TRANSLATE_NOOP("Arch_Structure","Creates a structure from scratch or from a selected object (sketch, wire, face or solid)")}

    def IsActive(self):

        return not FreeCAD.ActiveDocument is None

    def Activated(self):

        self.doc = FreeCAD.ActiveDocument
        self.Width = params.get_param_arch("StructureWidth")
        if self.beammode:
            self.Height = params.get_param_arch("StructureLength")
            self.Length = params.get_param_arch("StructureHeight")
        else:
            self.Length = params.get_param_arch("StructureLength")
            self.Height = params.get_param_arch("StructureHeight")
        self.Profile = None
        self.bpoint = None
        self.bmode = False
        self.precastvalues = None
        self.wp = None
        sel = FreeCADGui.Selection.getSelection()
        if sel:
            st = Draft.getObjectsOfType(sel,"Structure")
            ax = Draft.getObjectsOfType(sel,"Axis")
            if ax:
                FreeCADGui.runCommand("Arch_StructuralSystem")
                return
            elif not(ax) and not(st):
                self.doc.openTransaction(translate("Arch","Create Structure"))
                FreeCADGui.addModule("Arch")
                for obj in sel:
                    FreeCADGui.doCommand("obj = Arch.makeStructure(FreeCAD.ActiveDocument." + obj.Name + ")")
                    FreeCADGui.addModule("Draft")
                    FreeCADGui.doCommand("Draft.autogroup(obj)")
                self.doc.commitTransaction()
                self.doc.recompute()
                return

        # interactive mode
        import WorkingPlane

        FreeCAD.activeDraftCommand = self  # register as a Draft command for auto grid on/off
        self.wp = WorkingPlane.get_working_plane()
        self.points = []
        self.tracker = DraftTrackers.boxTracker()
        self.tracker.width(self.Width)
        self.tracker.height(self.Height)
        self.tracker.length(self.Length)
        self.tracker.setRotation(self.wp.get_placement().Rotation)
        self.tracker.on()
        self.precast = ArchPrecast._PrecastTaskPanel()
        self.dents = ArchPrecast._DentsTaskPanel()
        self.precast.Dents = self.dents
        if self.beammode:
            title=translate("Arch","First point of the beam")+":"
        else:
            title=translate("Arch","Base point of column")+":"
        FreeCADGui.Snapper.getPoint(callback=self.getPoint,movecallback=self.update,extradlg=[self.taskbox(),self.precast.form,self.dents.form],title=title)
        FreeCADGui.draftToolBar.continueCmd.show()

    def getPoint(self,point=None,obj=None):

        "this function is called by the snapper when it has a 3D point"

        self.bmode = self.modeb.isChecked()
        if point is None:
            FreeCAD.activeDraftCommand = None
            FreeCADGui.Snapper.off()
            self.tracker.finalize()
            return
        if self.bmode and (self.bpoint is None):
            self.bpoint = point
            FreeCADGui.Snapper.getPoint(last=point,callback=self.getPoint,movecallback=self.update,extradlg=[self.taskbox(),self.precast.form,self.dents.form],title=translate("Arch","Next point")+":",mode="line")
            return
        FreeCAD.activeDraftCommand = None
        FreeCADGui.Snapper.off()
        self.tracker.off()
        horiz = True # determines the type of rotation to apply to the final object
        self.doc.openTransaction(translate("Arch","Create Structure"))
        FreeCADGui.addModule("Arch")
        FreeCADGui.addModule("WorkingPlane")
        if self.bmode:
            self.Length = point.sub(self.bpoint).Length
            params.set_param_arch("StructureHeight",self.Length)
        if self.Profile is not None:
            try: # try to update latest precast values - fails if dialog has been destroyed already
                self.precastvalues = self.precast.getValues()
            except Exception:
                pass
            if ("Precast" in self.Profile) and self.precastvalues:
                # precast concrete
                self.precastvalues["PrecastType"] = self.Profile.split("_")[1]
                self.precastvalues["Length"] = self.Length
                self.precastvalues["Width"] = self.Width
                self.precastvalues["Height"] = self.Height
                argstring = ""
                # fix for precast placement, since their (0,0) point is the lower left corner
                if self.bmode:
                    delta = FreeCAD.Vector(0,0-self.Width/2,0)
                else:
                    delta = FreeCAD.Vector(-self.Length/2,-self.Width/2,0)
                delta = self.wp.get_global_coords(delta,as_vector=True)
                point = point.add(delta)
                if self.bpoint:
                    self.bpoint = self.bpoint.add(delta)
                # build the string definition
                for pair in self.precastvalues.items():
                    argstring += pair[0].lower() + "="
                    if isinstance(pair[1],str):
                        argstring += '"' + pair[1] + '",'
                    else:
                        argstring += str(pair[1]) + ","
                FreeCADGui.addModule("ArchPrecast")
                FreeCADGui.doCommand("s = ArchPrecast.makePrecast("+argstring+")")
            else:
                # metal profile
                FreeCADGui.doCommand('p = Arch.makeProfile('+str(self.Profile)+')')
                if (abs(self.Length - self.Profile[4]) >= 0.1) or self.bmode: # forgive rounding errors
                    # horizontal
                    FreeCADGui.doCommand('s = Arch.makeStructure(p,length='+str(self.Length)+')')
                    horiz = False
                else:
                    # vertical
                    FreeCADGui.doCommand('s = Arch.makeStructure(p,height='+str(self.Height)+')')
                    #if not self.bmode:
                    #    FreeCADGui.doCommand('s.Placement.Rotation = FreeCAD.Rotation(-0.5,0.5,-0.5,0.5)')
                FreeCADGui.doCommand('s.Profile = "'+self.Profile[2]+'"')
        else :
            FreeCADGui.doCommand('s = Arch.makeStructure(length='+str(self.Length)+',width='+str(self.Width)+',height='+str(self.Height)+')')

        # calculate rotation
        if self.bmode and self.bpoint:
            FreeCADGui.doCommand('s.Placement = Arch.placeAlongEdge('+DraftVecUtils.toString(self.bpoint)+","+DraftVecUtils.toString(point)+","+str(horiz)+")")
        else:
            FreeCADGui.doCommand('s.Placement.Base = '+DraftVecUtils.toString(point))
            FreeCADGui.doCommand('wp = WorkingPlane.get_working_plane()')
            FreeCADGui.doCommand('s.Placement.Rotation = s.Placement.Rotation.multiply(wp.get_placement().Rotation)')

        FreeCADGui.addModule("Draft")
        FreeCADGui.doCommand("Draft.autogroup(s)")
        self.doc.commitTransaction()
        self.doc.recompute()
        # gui_utils.end_all_events()  # Causes a crash on Linux.
        self.tracker.finalize()
        if FreeCADGui.draftToolBar.continueMode:
            self.Activated()

    def _createItemlist(self, baselist):

        "create nice labels for presets in the task panel"

        ilist=[]
        for p in baselist:
            f = FreeCAD.Units.Quantity(p[4],FreeCAD.Units.Length).getUserPreferred()
            d = params.get_param("Decimals",path="Units")
            s1 = str(round(p[4]/f[1],d))
            s2 = str(round(p[5]/f[1],d))
            s3 = str(f[2])
            ilist.append(p[2]+" ("+s1+"x"+s2+s3+")")
        return ilist

    def taskbox(self):

        "sets up a taskbox widget"

        w = QtGui.QWidget()
        ui = FreeCADGui.UiLoader()
        w.setWindowTitle(translate("Arch","Structure options"))
        grid = QtGui.QGridLayout(w)

        # mode box
        labelmode = QtGui.QLabel(translate("Arch","Parameters of the structure")+":")
        self.modeb = QtGui.QRadioButton(translate("Arch","Beam"))
        self.modec = QtGui.QRadioButton(translate("Arch","Column"))
        if self.bpoint or self.beammode:
            self.modeb.setChecked(True)
        else:
            self.modec.setChecked(True)
        grid.addWidget(labelmode,0,0,1,2)
        grid.addWidget(self.modeb,1,0,1,1)
        grid.addWidget(self.modec,1,1,1,1)

        # categories box
        labelc = QtGui.QLabel(translate("Arch","Category"))
        self.valuec = QtGui.QComboBox()
        self.valuec.addItems([" ","Precast concrete"]+Categories)
        grid.addWidget(labelc,2,0,1,1)
        grid.addWidget(self.valuec,2,1,1,1)

        # presets box
        labelp = QtGui.QLabel(translate("Arch","Preset"))
        self.vPresets = QtGui.QComboBox()
        self.pSelect = [None]
        fpresets = [" "]
        self.vPresets.addItems(fpresets)
        grid.addWidget(labelp,3,0,1,1)
        grid.addWidget(self.vPresets,3,1,1,1)

        # length
        label1 = QtGui.QLabel(translate("Arch","Length"))
        self.vLength = ui.createWidget("Gui::InputField")
        if self.modeb.isChecked():
            self.vLength.setText(FreeCAD.Units.Quantity(self.Height,FreeCAD.Units.Length).UserString)
        else:
            self.vLength.setText(FreeCAD.Units.Quantity(self.Length,FreeCAD.Units.Length).UserString)
        grid.addWidget(label1,4,0,1,1)
        grid.addWidget(self.vLength,4,1,1,1)

        # width
        label2 = QtGui.QLabel(translate("Arch","Width"))
        self.vWidth = ui.createWidget("Gui::InputField")
        self.vWidth.setText(FreeCAD.Units.Quantity(self.Width,FreeCAD.Units.Length).UserString)
        grid.addWidget(label2,5,0,1,1)
        grid.addWidget(self.vWidth,5,1,1,1)

        # height
        label3 = QtGui.QLabel(translate("Arch","Height"))
        self.vHeight = ui.createWidget("Gui::InputField")
        if self.modeb.isChecked():
            self.vHeight.setText(FreeCAD.Units.Quantity(self.Length,FreeCAD.Units.Length).UserString)
        else:
            self.vHeight.setText(FreeCAD.Units.Quantity(self.Height,FreeCAD.Units.Length).UserString)
        grid.addWidget(label3,6,0,1,1)
        grid.addWidget(self.vHeight,6,1,1,1)

        # horizontal button
        value4 = QtGui.QPushButton(translate("Arch","Switch Length/Height"))
        grid.addWidget(value4,7,0,1,1)
        value5 = QtGui.QPushButton(translate("Arch","Switch Length/Width"))
        grid.addWidget(value5,7,1,1,1)

        # connect slots
        QtCore.QObject.connect(self.valuec,QtCore.SIGNAL("currentIndexChanged(int)"),self.setCategory)
        QtCore.QObject.connect(self.vPresets,QtCore.SIGNAL("currentIndexChanged(int)"),self.setPreset)
        QtCore.QObject.connect(self.vLength,QtCore.SIGNAL("valueChanged(double)"),self.setLength)
        QtCore.QObject.connect(self.vWidth,QtCore.SIGNAL("valueChanged(double)"),self.setWidth)
        QtCore.QObject.connect(self.vHeight,QtCore.SIGNAL("valueChanged(double)"),self.setHeight)
        QtCore.QObject.connect(value4,QtCore.SIGNAL("pressed()"),self.rotateLH)
        QtCore.QObject.connect(value5,QtCore.SIGNAL("pressed()"),self.rotateLW)
        QtCore.QObject.connect(self.modeb,QtCore.SIGNAL("toggled(bool)"),self.switchLH)

        # restore preset
        stored = params.get_param_arch("StructurePreset")
        if stored:
            if stored.lower().startswith("precast_"):
                self.valuec.setCurrentIndex(1)
                tp = stored.split("_")[1]
                if tp and (tp in self.precast.PrecastTypes):
                    self.vPresets.setCurrentIndex(self.precast.PrecastTypes.index(tp))
            elif ";" in stored:
                stored = stored.split(";")
                if len(stored) >= 3:
                    if stored[1] in Categories:
                        self.valuec.setCurrentIndex(2+Categories.index(stored[1]))
                        ps = [p[2] for p in self.pSelect]
                        if stored[2] in ps:
                            self.vPresets.setCurrentIndex(ps.index(stored[2]))
        return w

    def update(self,point,info):

        "this function is called by the Snapper when the mouse is moved"

        if FreeCADGui.Control.activeDialog():
            try: # try to update latest precast values - fails if dialog has been destroyed already
                self.precastvalues = self.precast.getValues()
            except Exception:
                pass
            if self.Height >= self.Length:
                delta = Vector(0,0,self.Height/2)
            else:
                delta = Vector(self.Length/2,0,0)
            delta = self.wp.get_global_coords(delta,as_vector=True)
            if self.modec.isChecked():
                self.tracker.pos(point.add(delta))
                self.tracker.on()
            else:
                if self.bpoint:
                    delta = Vector(0,0,-self.Height/2)
                    delta = self.wp.get_global_coords(delta,as_vector=True)
                    self.tracker.update([self.bpoint.add(delta),point.add(delta)])
                    self.tracker.on()
                    l = (point.sub(self.bpoint)).Length
                    self.vLength.setText(FreeCAD.Units.Quantity(l,FreeCAD.Units.Length).UserString)
                else:
                    self.tracker.off()

    def setWidth(self,d):

        self.Width = d
        self.tracker.width(d)
        params.set_param_arch("StructureWidth",d)

    def setHeight(self,d):

        self.Height = d
        self.tracker.height(d)
        if self.modeb.isChecked():
            params.set_param_arch("StructureLength",d)
        else:
            params.set_param_arch("StructureHeight",d)

    def setLength(self,d):

        self.Length = d
        self.tracker.length(d)
        if self.modeb.isChecked():
            params.set_param_arch("StructureHeight",d)
        else:
            params.set_param_arch("StructureLength",d)

    def setCategory(self,i):

        self.vPresets.clear()
        if i > 1:
            self.precast.form.hide()
            self.pSelect = [p for p in Presets if p[1] == Categories[i-2]]
            fpresets = self._createItemlist(self.pSelect)
            self.vPresets.addItems(fpresets)
            self.setPreset(0)
        elif i == 1:
            self.precast.form.show()
            self.pSelect = self.precast.PrecastTypes
            fpresets = self.precast.PrecastTypes
            self.vPresets.addItems(fpresets)
            self.setPreset(0)
        else:
            self.precast.form.hide()
            self.pSelect = [None]
            fpresets = [" "]
            self.vPresets.addItems(fpresets)
            params.set_param_arch("StructurePreset","")

    def setPreset(self,i):

        self.Profile = None
        elt = self.pSelect[i]
        if elt:
            if elt in self.precast.PrecastTypes:
                self.precast.setPreset(elt)
                self.Profile = "Precast_" + elt
                if elt in ["Pillar","Beam"]:
                    self.dents.form.show()
                else:
                    self.dents.form.hide()
                params.set_param_arch("StructurePreset",self.Profile)
            else:
                p=elt[0]-1 # Presets indexes are 1-based
                self.vLength.setText(FreeCAD.Units.Quantity(float(Presets[p][4]),FreeCAD.Units.Length).UserString)
                self.vWidth.setText(FreeCAD.Units.Quantity(float(Presets[p][5]),FreeCAD.Units.Length).UserString)
                self.Profile = Presets[p]
                params.set_param_arch("StructurePreset",";".join([str(i) for i in self.Profile]))

    def switchLH(self,bmode):

        if bmode:
            self.bmode = True
            if self.Height > self.Length:
                self.rotateLH()
        else:
            self.bmode = False
            if self.Length > self.Height:
                self.rotateLH()
                self.tracker.setRotation(FreeCAD.Rotation())

    def rotateLH(self):

        l = self.vLength.text()
        h = self.vHeight.text()
        self.vLength.setText(h)
        self.vHeight.setText(l)

    def rotateLW(self):

        l = self.vLength.text()
        w = self.vWidth.text()
        self.vLength.setText(w)
        self.vWidth.setText(l)


class _Structure(ArchComponent.Component):

    "The Structure object"

    def __init__(self,obj):

        ArchComponent.Component.__init__(self,obj)
        self.setProperties(obj)
        obj.IfcType = "Beam"

    def setProperties(self,obj):

        pl = obj.PropertiesList
        if not "Tool" in pl:
            obj.addProperty("App::PropertyLinkSubList", "Tool", "ExtrusionPath", QT_TRANSLATE_NOOP("App::Property", "An optional extrusion path for this element"), locked=True)
        if not "ComputedLength" in pl:
            obj.addProperty("App::PropertyDistance", "ComputedLength", "ExtrusionPath", QT_TRANSLATE_NOOP("App::Property", "The computed length of the extrusion path"), 1, locked=True)
        if not "ToolOffsetFirst" in pl:
            obj.addProperty("App::PropertyDistance", "ToolOffsetFirst", "ExtrusionPath", QT_TRANSLATE_NOOP("App::Property", "Start offset distance along the extrusion path (positive: extend, negative: trim)"), locked=True)
        if not "ToolOffsetLast" in pl:
            obj.addProperty("App::PropertyDistance", "ToolOffsetLast", "ExtrusionPath", QT_TRANSLATE_NOOP("App::Property", "End offset distance along the extrusion path (positive: extend, negative: trim)"), locked=True)
        if not "BasePerpendicularToTool" in pl:
            obj.addProperty("App::PropertyBool", "BasePerpendicularToTool", "ExtrusionPath", QT_TRANSLATE_NOOP("App::Property", "Automatically align the Base of the Structure perpendicular to the Tool axis"), locked=True)
        if not "BaseOffsetX" in pl:
            obj.addProperty("App::PropertyDistance", "BaseOffsetX", "ExtrusionPath", QT_TRANSLATE_NOOP("App::Property", "X offset between the Base origin and the Tool axis (only used if BasePerpendicularToTool is True)"), locked=True)
        if not "BaseOffsetY" in pl:
            obj.addProperty("App::PropertyDistance", "BaseOffsetY", "ExtrusionPath", QT_TRANSLATE_NOOP("App::Property", "Y offset between the Base origin and the Tool axis (only used if BasePerpendicularToTool is True)"), locked=True)
        if not "BaseMirror" in pl:
            obj.addProperty("App::PropertyBool", "BaseMirror", "ExtrusionPath", QT_TRANSLATE_NOOP("App::Property", "Mirror the Base along its Y axis (only used if BasePerpendicularToTool is True)"), locked=True)
        if not "BaseRotation" in pl:
            obj.addProperty("App::PropertyAngle", "BaseRotation", "ExtrusionPath", QT_TRANSLATE_NOOP("App::Property", "Base rotation around the Tool axis (only used if BasePerpendicularToTool is True)"), locked=True)
        if not "Length" in pl:
            obj.addProperty("App::PropertyLength","Length","Structure",QT_TRANSLATE_NOOP("App::Property","The length of this element, if not based on a profile"), locked=True)
        if not "Width" in pl:
            obj.addProperty("App::PropertyLength","Width","Structure",QT_TRANSLATE_NOOP("App::Property","The width of this element, if not based on a profile"), locked=True)
        if not "Height" in pl:
            obj.addProperty("App::PropertyLength","Height","Structure",QT_TRANSLATE_NOOP("App::Property","The height or extrusion depth of this element. Keep 0 for automatic"), locked=True)
        if not "Normal" in pl:
            obj.addProperty("App::PropertyVector","Normal","Structure",QT_TRANSLATE_NOOP("App::Property","The normal extrusion direction of this object (keep (0,0,0) for automatic normal)"), locked=True)
        if not "Nodes" in pl:
            obj.addProperty("App::PropertyVectorList","Nodes","Structure",QT_TRANSLATE_NOOP("App::Property","The structural nodes of this element"), locked=True)
        if not "Profile" in pl:
            obj.addProperty("App::PropertyString","Profile","Structure",QT_TRANSLATE_NOOP("App::Property","A description of the standard profile this element is based upon"), locked=True)
        if not "NodesOffset" in pl:
            obj.addProperty("App::PropertyDistance","NodesOffset","Structure",QT_TRANSLATE_NOOP("App::Property","Offset distance between the centerline and the nodes line"), locked=True)
        if not "FaceMaker" in pl:
            obj.addProperty("App::PropertyEnumeration","FaceMaker","Structure",QT_TRANSLATE_NOOP("App::Property","The facemaker type to use to build the profile of this object"), locked=True)
            obj.FaceMaker = ["None","Simple","Cheese","Bullseye"]
        if not "ArchSketchData" in pl:
            obj.addProperty("App::PropertyBool","ArchSketchData","Structure",QT_TRANSLATE_NOOP("App::Property","Use Base ArchSketch (if used) data (e.g. widths, aligns, offsets) instead of Wall's properties"), locked=True)
            obj.ArchSketchData = True
        if not "ArchSketchEdges" in pl:  # PropertyStringList
            obj.addProperty("App::PropertyStringList","ArchSketchEdges","Structure",QT_TRANSLATE_NOOP("App::Property","Selected edges (or group of edges) of the base ArchSketch, to use in creating the shape of this BIM Structure (instead of using all the Base shape's edges by default).  Input are index numbers of edges or groups."), locked=True)
        else:
            # test if the property was added but as IntegerList, then update;
            type = obj.getTypeIdOfProperty('ArchSketchEdges')
            if type == "App::PropertyIntegerList":
                oldIntValue = obj.ArchSketchEdges
                newStrValue = [str(x) for x in oldIntValue]
                obj.removeProperty("ArchSketchEdges")
                obj.addProperty("App::PropertyStringList","ArchSketchEdges","Structure",QT_TRANSLATE_NOOP("App::Property","Selected edges (or group of edges) of the base ArchSketch, to use in creating the shape of this BIM Structure (instead of using all the Base shape's edges by default).  Input are index numbers of edges or groups."), locked=True)
                obj.ArchSketchEdges = newStrValue
        if not hasattr(obj,"ArchSketchPropertySet"):
            obj.addProperty("App::PropertyEnumeration","ArchSketchPropertySet","Structure",QT_TRANSLATE_NOOP("App::Property","Select User Defined PropertySet to use in creating variant shape, with same ArchSketch "), locked=True)
            obj.ArchSketchPropertySet = ['Default']
        if not hasattr(self,"ArchSkPropSetPickedUuid"):
            self.ArchSkPropSetPickedUuid = ''
        if not hasattr(self,"ArchSkPropSetListPrev"):
            self.ArchSkPropSetListPrev = []

        self.Type = "Structure"


    def dumps(self):  # Supercede Arch.Component.dumps()
        dump = super().dumps()
        if not isinstance(dump, tuple):
           dump = (dump,)  #Python Tuple With One Item
        dump = dump + (self.ArchSkPropSetPickedUuid, self.ArchSkPropSetListPrev)
        return dump


    def loads(self,state):
        super().loads(state)  # do nothing as of 2024.11.28
        if state == None:
            return
        elif state[0] == 'S':  # state[1] == 't', behaviour before 2024.11.28
            return
        elif state[0] == 'Structure':
            self.ArchSkPropSetPickedUuid = state[1]
            self.ArchSkPropSetListPrev = state[2]
        elif state[0] != 'Structure':  # model before merging super.dumps/loads()
            self.ArchSkPropSetPickedUuid = state[0]
            self.ArchSkPropSetListPrev = state[1]


    def onDocumentRestored(self,obj):

        ArchComponent.Component.onDocumentRestored(self,obj)
        self.setProperties(obj)

        if hasattr(obj,"ArchSketchData") and obj.ArchSketchData and Draft.getType(obj.Base) == "ArchSketch":
            if hasattr(obj,"ArchSketchEdges"):
                obj.setEditorMode("ArchSketchEdges", ["ReadOnly"])
            if hasattr(obj,"ArchSketchPropertySet"):
                obj.setEditorMode("ArchSketchPropertySet", 0)
        else:
            if hasattr(obj,"ArchSketchEdges"):
                obj.setEditorMode("ArchSketchEdges", 0)
            if hasattr(obj,"ArchSketchPropertySet"):
                obj.setEditorMode("ArchSketchPropertySet", ["ReadOnly"])

        # set a flag to indicate onDocumentRestored() is run


    def execute(self,obj):

        "creates the structure shape"

        import Part
        import DraftGeomUtils

        if self.clone(obj):
            return
        if obj.Base and not self.ensureBase(obj):
            return

        base = None
        pl = obj.Placement

        # PropertySet support
        propSetPickedUuidPrev = self.ArchSkPropSetPickedUuid
        propSetListPrev = self.ArchSkPropSetListPrev
        propSetSelectedNamePrev = obj.ArchSketchPropertySet
        propSetSelectedNameCur = None
        propSetListCur = None
        if Draft.getType(obj.Base) == "ArchSketch":
            baseProxy = obj.Base.Proxy
            if hasattr(baseProxy,"getPropertySet"):
                # get full list of PropertySet
                propSetListCur = baseProxy.getPropertySet(obj.Base)
                # get updated name (if any) of the selected PropertySet
                propSetSelectedNameCur = baseProxy.getPropertySet(obj.Base,
                                         propSetUuid=propSetPickedUuidPrev)
        if propSetSelectedNameCur:  # True if selection is not deleted
            if propSetListPrev != propSetListCur:
                obj.ArchSketchPropertySet = propSetListCur
                obj.ArchSketchPropertySet = propSetSelectedNameCur
                self.ArchSkPropSetListPrev = propSetListCur
            #elif propSetListPrev == propSetListCur:
                #pass  #nothing to do in this case
            # but if below, though (propSetListPrev == propSetListCur)
            elif propSetSelectedNamePrev != propSetSelectedNameCur:
                obj.ArchSketchPropertySet = propSetSelectedNameCur
        else:  # True if selection is deleted
            if propSetListCur:
                if propSetListPrev != propSetListCur:
                    obj.ArchSketchPropertySet = propSetListCur
                    obj.ArchSketchPropertySet = 'Default'
                #else:  # Seems no need ...
                    #obj.PropertySet = 'Default'

        extdata = self.getExtrusionData(obj)

        if extdata:
            sh = extdata[0]
            if not isinstance(sh,list):
                sh = [sh]
            ev = extdata[1]
            if not isinstance(ev,list):
                ev = [ev]
            pla = extdata[2]
            if not isinstance(pla,list):
                pla = [pla]
            base = []
            extrusion_length = 0.0
            for i in range(len(sh)):
                shi = sh[i]
                if i < len(ev):
                    evi = ev[i]
                else:
                    evi = ev[-1]
                    if isinstance(evi, FreeCAD.Vector):
                        evi = FreeCAD.Vector(evi)
                    else:
                        evi = evi.copy()
                if i < len(pla):
                    pli = pla[i]
                else:
                    pli = pla[-1].copy()
                shi.Placement = pli.multiply(shi.Placement)
                if isinstance(evi, FreeCAD.Vector):
                    extv = pla[0].Rotation.multVec(evi)
                    shi = shi.extrude(extv)
                else:
                    try:
                        shi = evi.makePipe(shi)
                    except Part.OCCError:
                        FreeCAD.Console.PrintError(translate("Arch","Error: The base shape couldn't be extruded along this tool object")+"\n")
                        return
                base.append(shi)
                extrusion_length += evi.Length
            if len(base) == 1:
                base = base[0]
            else:
                base = Part.makeCompound(base)
            obj.ComputedLength = FreeCAD.Units.Quantity(extrusion_length, FreeCAD.Units.Length)
        if obj.Base:
            if hasattr(obj.Base,'Shape'):
                if obj.Base.Shape.isNull():
                    return
                if not obj.Base.Shape.isValid():
                    if not obj.Base.Shape.Solids:
                        # let pass invalid objects if they have solids...
                        return
                elif obj.Base.Shape.Solids:
                    base = obj.Base.Shape.copy()
            elif obj.Base.isDerivedFrom("Mesh::Feature"):
                if obj.Base.Mesh.isSolid():
                    if obj.Base.Mesh.countComponents() == 1:
                        sh = ArchCommands.getShapeFromMesh(obj.Base.Mesh)
                        if sh.isClosed() and sh.isValid() and sh.Solids and (not sh.isNull()):
                            base = sh
                        else:
                            FreeCAD.Console.PrintWarning(translate("Arch","This mesh is an invalid solid")+"\n")
                            obj.Base.ViewObject.show()
        if (not base) and (not obj.Additions):
            #FreeCAD.Console.PrintError(translate("Arch","Error: Invalid base object")+"\n")
            return

        base = self.processSubShapes(obj,base,pl)
        self.applyShape(obj,base,pl)

    def getExtrusionData(self,obj):
        """returns (shape,extrusion vector or path,placement) or None"""
        if hasattr(obj,"IfcType"):
            IfcType = obj.IfcType
        else:
            IfcType = None
        import Part
        import DraftGeomUtils
        data = ArchComponent.Component.getExtrusionData(self,obj)
        if data:
            if not isinstance(data[0],list):
                # multifuses not considered here
                return data
        length  = obj.Length.Value
        width = obj.Width.Value
        height = obj.Height.Value
        if not height:
            height = self.getParentHeight(obj)
        baseface = None
        extrusion = None
        normal = None
        if obj.Base:
            if hasattr(obj.Base,'Shape'):
                if obj.Base.Shape:
                    if obj.Base.Shape.Solids:
                        return None
                    elif obj.Base.Shape.Faces:
                        if not DraftGeomUtils.isCoplanar(obj.Base.Shape.Faces,tol=0.01):
                            return None
                        else:
                            baseface = obj.Base.Shape.copy()
                    elif obj.Base.Shape.Wires:
                        # ArchSketch feature :
                        # Get base shape wires, and faceMaker, for Structure (slab. etc.) from Base Objects if they store and provide by getStructureBaseShapeWires()
                        # (thickness, normal/extrusion, length, width, baseface maybe for later) of structure (slab etc.)
                        structureBaseShapeWires = []
                        baseShapeWires = []                   #baseSlabWires / baseSlabOpeningWires = None
                        faceMaker = None

                        if hasattr(obj.Base, 'Proxy') and obj.ArchSketchData and \
                        hasattr(obj.Base.Proxy, 'getStructureBaseShapeWires'):
                            propSetUuid = self.ArchSkPropSetPickedUuid

                            # provide selected edges, or groups, in obj.ArchSketchEdges for processing in getStructureBaseShapeWires() (getSortedClusters) as override
                            structureBaseShapeWires = obj.Base.Proxy.getStructureBaseShapeWires(obj.Base,
                                                          propSetUuid=propSetUuid)
                            # get slab wires; use original wires if structureBaseShapeWires() provided none
                            if structureBaseShapeWires:  # would be false (none) if both base ArchSketch and obj do not have the edges stored / inputted by user
                                # if structureBaseShapeWires is {dict}
                                baseShapeWires = structureBaseShapeWires.get('slabWires')
                                faceMaker = structureBaseShapeWires.get('faceMaker')
                        elif obj.Base.isDerivedFrom("Sketcher::SketchObject"):
                            skGeom = obj.Base.GeometryFacadeList
                            skGeomEdges = []
                            skPlacement = obj.Base.Placement  # Get Sketch's placement to restore later
                            # Get ArchSketch edges to construct ArchStructure
                            # No need to test obj.ArchSketchData ...
                            for ig, geom  in enumerate(skGeom):
                                # Construction mode edges should be ignored if
                                # ArchSketchEdges, otherwise, ArchSketchEdges data
                                # needs to take out those in Construction before
                                # using as parameters.
                                if (not obj.ArchSketchEdges and not geom.Construction) or str(ig) in obj.ArchSketchEdges:
                                    # support Line, Arc, Circle, Ellipse, BSplineCurve for Sketch
                                    # as Base at the moment
                                    if isinstance(geom.Geometry, (Part.LineSegment,
                                                  Part.Circle, Part.ArcOfCircle,
                                                  Part.Ellipse, Part.BSplineCurve)):
                                        skGeomEdgesI = geom.Geometry.toShape()
                                        skGeomEdges.append(skGeomEdgesI)
                            clusterTransformed = []
                            for cluster in Part.getSortedClusters(skGeomEdges):
                                edgesTransformed = []
                                for edge in cluster:
                                    edge.Placement = edge.Placement.multiply(skPlacement)
                                    edgesTransformed.append(edge)
                                clusterTransformed.append(edgesTransformed)
                            for clusterT in clusterTransformed:
                                baseShapeWires.append(Part.Wire(clusterT))
                            faceMaker = 'Bullseye'

                        if not baseShapeWires:
                            baseShapeWires = obj.Base.Shape.Wires
                        if faceMaker or (obj.FaceMaker != "None"):
                            if not faceMaker:
                                faceMaker = obj.FaceMaker
                            try:
                                baseface = Part.makeFace(baseShapeWires,"Part::FaceMaker"+str(faceMaker))
                            except Exception:
                                FreeCAD.Console.PrintError(translate("Arch","Facemaker returned an error")+"\n")
                                # Not returning even Part.makeFace fails, fall back to 'non-Part.makeFace' method
                        if not baseface:
                            for w in baseShapeWires:
                                if not w.isClosed():
                                    p0 = w.OrderedVertexes[0].Point
                                    p1 = w.OrderedVertexes[-1].Point
                                    if p0 != p1:
                                        e = Part.LineSegment(p0,p1).toShape()
                                        w.add(e)
                                w.fix(0.1,0,1) # fixes self-intersecting wires
                                f = Part.Face(w)
                                # check if it is 1st face (f) created from w in baseShapeWires; if not, fuse()
                                if baseface:
                                    baseface = baseface.fuse(f)
                                else:
                                    # TODO use Part.Shape() rather than shape.copy() ... ?
                                    baseface = f.copy()
        elif length and width and height:
            if (length > height) and (IfcType in ["Beam", "Column"]):
                h2 = height/2 or 0.5
                w2 = width/2 or 0.5
                v1 = Vector(0,-w2,-h2)
                v4 = Vector(0,-w2,h2)
                v3 = Vector(0,w2,h2)
                v2 = Vector(0,w2,-h2)
            else:
                l2 = length/2 or 0.5
                w2 = width/2 or 0.5
                v1 = Vector(-l2,-w2,0)
                v2 = Vector(l2,-w2,0)
                v3 = Vector(l2,w2,0)
                v4 = Vector(-l2,w2,0)
            import Part
            baseface = Part.Face(Part.makePolygon([v1,v2,v3,v4,v1]))
        if baseface:
            if hasattr(obj, "Tool") and obj.Tool:
                tool = obj.Tool
                edges = DraftGeomUtils.get_referenced_edges(tool)
                if len(edges) > 0:
                    extrusion = Part.Wire(Part.__sortEdges__(edges))
                    if hasattr(obj, "ToolOffsetFirst"):
                        offset_start = float(obj.ToolOffsetFirst.getValueAs("mm"))
                    else:
                        offset_start = 0.0
                    if hasattr(obj, "ToolOffsetLast"):
                        offset_end = float(obj.ToolOffsetLast.getValueAs("mm"))
                    else:
                        offset_end = 0.0
                    if offset_start  != 0.0 or offset_end != 0.0:
                        extrusion = DraftGeomUtils.get_extended_wire(extrusion, offset_start, offset_end)
                    if hasattr(obj, "BasePerpendicularToTool") and obj.BasePerpendicularToTool:
                        pl = FreeCAD.Placement()
                        if hasattr(obj, "BaseRotation"):
                            pl.rotate(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 0, 1), -obj.BaseRotation)
                        if hasattr(obj, "BaseOffsetX") and hasattr(obj, "BaseOffsetY"):
                            pl.translate(FreeCAD.Vector(obj.BaseOffsetX, obj.BaseOffsetY, 0))
                        if hasattr(obj, "BaseMirror") and obj.BaseMirror:
                            pl.rotate(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 1, 0), 180)
                        baseface.Placement = DraftGeomUtils.get_placement_perpendicular_to_wire(extrusion).multiply(pl)
            else:
                if obj.Normal.Length:
                    normal = Vector(obj.Normal).normalize()
                else:
                    normal = baseface.Faces[0].normalAt(0, 0)  # TODO to use ArchSketch's 'normal' for consistency
            base = None
            placement = None
            inverse_placement = None
            if len(baseface.Faces) > 1:
                base = []
                placement = []
                hint = baseface.Faces[0].normalAt(0, 0)  # TODO anything to do ?
                for f in baseface.Faces:
                    bf, pf = self.rebase(f, hint)
                    base.append(bf)
                    placement.append(pf)
                inverse_placement = placement[0].inverse()
            else:
                base, placement = self.rebase(baseface)
                inverse_placement = placement.inverse()
            if extrusion:
                if len(extrusion.Edges) == 1 and DraftGeomUtils.geomType(extrusion.Edges[0]) == "Line":
                    extrusion = DraftGeomUtils.vec(extrusion.Edges[0], True)
                if isinstance(extrusion, FreeCAD.Vector):
                    extrusion = inverse_placement.Rotation.multVec(extrusion)
            elif normal:
                normal = inverse_placement.Rotation.multVec(normal)
                if not normal:
                    normal = Vector(0,0,1)
                if not normal.Length:
                    normal = Vector(0,0,1)
                extrusion = normal
                if (length > height) and (IfcType in ["Beam", "Column"]):
                    if length:
                        extrusion = normal.multiply(length)
                else:
                    if height:
                        extrusion = normal.multiply(height)
            if extrusion:
                return (base, extrusion, placement)
        return None

    def onChanged(self,obj,prop):

        # check the flag indicating if we are currently in the process of
        # restoring document; if not, no further code is run as getExtrusionData() 
        # below return error when some properties are not added by onDocumentRestored()
        if FreeCAD.ActiveDocument.Restoring:
            return

        if hasattr(obj,"IfcType"):
            IfcType = obj.IfcType
        else:
            IfcType = None
        self.hideSubobjects(obj,prop)
        if prop in ["Shape","ResetNodes","NodesOffset"]:
            # ResetNodes is not a property but it allows us to use this function to force reset the nodes
            nodes = None
            extdata = self.getExtrusionData(obj)
            if extdata and not isinstance(extdata[0],list):
                nodes = extdata[0]
                if IfcType in ["Beam", "Column"]:
                    if not isinstance(extdata[1], FreeCAD.Vector):
                        nodes = extdata[1]
                    elif extdata[1].Length > 0:
                        if hasattr(nodes,"CenterOfMass"):
                            import Part
                            nodes = Part.LineSegment(nodes.CenterOfMass,nodes.CenterOfMass.add(extdata[1])).toShape()
                if isinstance(extdata[1], FreeCAD.Vector):
                    nodes.Placement = nodes.Placement.multiply(extdata[2])
            offset = FreeCAD.Vector()
            if hasattr(obj,"NodesOffset"):
                offset = FreeCAD.Vector(0,0,obj.NodesOffset.Value)
            if obj.Nodes and (prop != "ResetNodes"):
                if hasattr(self,"nodes"):
                    if self.nodes:
                        if obj.Nodes != self.nodes:
                            # nodes are set manually: don't touch them
                            return
                else:
                    # nodes haven't been calculated yet, but are set (file load)
                    # we set the nodes now but don't change the property
                    if nodes:
                        self.nodes = [v.Point.add(offset) for v in nodes.Vertexes]
                        return
            # we set the nodes
            if nodes:
                self.nodes = [v.Point.add(offset) for v in nodes.Vertexes]
                obj.Nodes = self.nodes
        ArchComponent.Component.onChanged(self,obj,prop)

        if (prop == "ArchSketchPropertySet"
            and Draft.getType(obj.Base) == "ArchSketch"):
            baseProxy = obj.Base.Proxy
            if hasattr(baseProxy,"getPropertySet"):
                uuid = baseProxy.getPropertySet(obj,
                                 propSetName=obj.ArchSketchPropertySet)
                self.ArchSkPropSetPickedUuid = uuid
        if (hasattr(obj,"ArchSketchData") and obj.ArchSketchData
            and Draft.getType(obj.Base) == "ArchSketch"):
            if hasattr(obj,"ArchSketchEdges"):
                obj.setEditorMode("ArchSketchEdges", ["ReadOnly"])
            if hasattr(obj,"ArchSketchPropertySet"):
                obj.setEditorMode("ArchSketchPropertySet", 0)
        else:
            if hasattr(obj,"ArchSketchEdges"):
                obj.setEditorMode("ArchSketchEdges", 0)
            if hasattr(obj,"ArchSketchPropertySet"):
                obj.setEditorMode("ArchSketchPropertySet", ["ReadOnly"])


    def getNodeEdges(self,obj):

        "returns a list of edges from structural nodes"

        edges = []
        if obj.Nodes:
            import Part
            for i in range(len(obj.Nodes)-1):
                edges.append(Part.LineSegment(obj.Placement.multVec(obj.Nodes[i]),obj.Placement.multVec(obj.Nodes[i+1])).toShape())
            if hasattr(obj.ViewObject,"NodeType"):
                if (obj.ViewObject.NodeType == "Area") and (len(obj.Nodes) > 2):
                    edges.append(Part.LineSegment(obj.Placement.multVec(obj.Nodes[-1]),obj.Placement.multVec(obj.Nodes[0])).toShape())
        return edges


class _ViewProviderStructure(ArchComponent.ViewProviderComponent):

    "A View Provider for the Structure object"

    def __init__(self,vobj):

        ArchComponent.ViewProviderComponent.__init__(self,vobj)

        # setProperties of ArchComponent will be overwritten
        # thus setProperties from ArchComponent will be explicit called to get the properties
        ArchComponent.ViewProviderComponent.setProperties(self, vobj)

        self.setProperties(vobj)
        vobj.ShapeColor = ArchCommands.getDefaultColor("Structure")

    def setProperties(self,vobj):

        pl = vobj.PropertiesList
        if not "ShowNodes" in pl:
            vobj.addProperty("App::PropertyBool","ShowNodes","Nodes",QT_TRANSLATE_NOOP("App::Property","If the nodes are visible or not"), locked=True).ShowNodes = False
        if not "NodeLine" in pl:
            vobj.addProperty("App::PropertyFloat","NodeLine","Nodes",QT_TRANSLATE_NOOP("App::Property","The width of the nodes line"), locked=True)
        if not "NodeSize" in pl:
            vobj.addProperty("App::PropertyFloat","NodeSize","Nodes",QT_TRANSLATE_NOOP("App::Property","The size of the node points"), locked=True)
            vobj.NodeSize = 6
        if not "NodeColor" in pl:
            vobj.addProperty("App::PropertyColor","NodeColor","Nodes",QT_TRANSLATE_NOOP("App::Property","The color of the nodes line"), locked=True)
            vobj.NodeColor = (1.0,1.0,1.0,1.0)
        if not "NodeType" in pl:
            vobj.addProperty("App::PropertyEnumeration","NodeType","Nodes",QT_TRANSLATE_NOOP("App::Property","The type of structural node"), locked=True)
            vobj.NodeType = ["Linear","Area"]

    def onDocumentRestored(self,vobj):

        self.setProperties(vobj)

    def getIcon(self):

        import Arch_rc
        if hasattr(self,"Object"):
            if hasattr(self.Object,"CloneOf"):
                if self.Object.CloneOf:
                    return ":/icons/Arch_Structure_Clone.svg"
        return ":/icons/Arch_Structure_Tree.svg"

    def updateData(self,obj,prop):

        if prop == "Nodes":
            if obj.Nodes:
                if hasattr(self,"nodes"):
                    p = []
                    self.pointset.numPoints.setValue(0)
                    self.lineset.coordIndex.deleteValues(0)
                    self.faceset.coordIndex.deleteValues(0)
                    for n in obj.Nodes:
                        p.append([n.x,n.y,n.z])
                    self.coords.point.setValues(0,len(p),p)
                    self.pointset.numPoints.setValue(len(p))
                    self.lineset.coordIndex.setValues(0,len(p)+1,list(range(len(p)))+[-1])
                    if hasattr(obj.ViewObject,"NodeType"):
                        if (obj.ViewObject.NodeType == "Area") and (len(p) > 2):
                            self.coords.point.set1Value(len(p),p[0][0],p[0][1],p[0][2])
                            self.lineset.coordIndex.setValues(0,len(p)+2,list(range(len(p)+1))+[-1])
                            self.faceset.coordIndex.setValues(0,len(p)+1,list(range(len(p)))+[-1])

        elif prop in ["IfcType"]:
            if hasattr(obj.ViewObject,"NodeType"):
                if hasattr(obj,"IfcType"):
                    IfcType = obj.IfcType
                else:
                    IfcType = None
                if IfcType == "Slab":
                    obj.ViewObject.NodeType = "Area"
                else:
                    obj.ViewObject.NodeType = "Linear"
        else:
            ArchComponent.ViewProviderComponent.updateData(self,obj,prop)

    def onChanged(self,vobj,prop):

        if prop == "ShowNodes":
            if hasattr(self,"nodes"):
                vobj.Annotation.removeChild(self.nodes)
                del self.nodes
            if vobj.ShowNodes:
                from pivy import coin
                self.nodes = coin.SoAnnotation()
                self.coords = coin.SoCoordinate3()
                self.mat = coin.SoMaterial()
                self.pointstyle = coin.SoDrawStyle()
                self.pointstyle.style = coin.SoDrawStyle.POINTS
                self.pointset = coin.SoType.fromName("SoBrepPointSet").createInstance()
                self.linestyle = coin.SoDrawStyle()
                self.linestyle.style = coin.SoDrawStyle.LINES
                self.lineset = coin.SoType.fromName("SoBrepEdgeSet").createInstance()
                self.facestyle = coin.SoDrawStyle()
                self.facestyle.style = coin.SoDrawStyle.FILLED
                self.shapehints = coin.SoShapeHints()
                self.shapehints.faceType = coin.SoShapeHints.UNKNOWN_FACE_TYPE
                self.fmat = coin.SoMaterial()
                self.fmat.transparency.setValue(0.75)
                self.faceset = coin.SoIndexedFaceSet()
                self.nodes.addChild(self.coords)
                self.nodes.addChild(self.mat)
                self.nodes.addChild(self.pointstyle)
                self.nodes.addChild(self.pointset)
                self.nodes.addChild(self.linestyle)
                self.nodes.addChild(self.lineset)
                self.nodes.addChild(self.facestyle)
                self.nodes.addChild(self.shapehints)
                self.nodes.addChild(self.fmat)
                self.nodes.addChild(self.faceset)
                vobj.Annotation.addChild(self.nodes)
                self.updateData(vobj.Object,"Nodes")
                self.onChanged(vobj,"NodeColor")
                self.onChanged(vobj,"NodeLine")
                self.onChanged(vobj,"NodeSize")

        elif prop == "NodeColor":
            if hasattr(self,"mat"):
                l = vobj.NodeColor
                self.mat.diffuseColor.setValue([l[0],l[1],l[2]])
                self.fmat.diffuseColor.setValue([l[0],l[1],l[2]])

        elif prop == "NodeLine":
            if hasattr(self,"linestyle"):
                self.linestyle.lineWidth = vobj.NodeLine

        elif prop == "NodeSize":
            if hasattr(self,"pointstyle"):
                self.pointstyle.pointSize = vobj.NodeSize

        elif prop == "NodeType":
            self.updateData(vobj.Object,"Nodes")

        else:
            ArchComponent.ViewProviderComponent.onChanged(self,vobj,prop)

    def setEdit(self,vobj,mode):
        if mode != 0:
            return None

        taskd = StructureTaskPanel(vobj.Object)
        taskd.obj = self.Object
        taskd.update()
        FreeCADGui.Control.showDialog(taskd)
        return True


class StructureTaskPanel(ArchComponent.ComponentTaskPanel):

    def __init__(self,obj):

        ArchComponent.ComponentTaskPanel.__init__(self)
        self.nodes_widget = QtGui.QWidget()
        self.nodes_widget.setWindowTitle(QtGui.QApplication.translate("Arch", "Node Tools", None))
        lay = QtGui.QVBoxLayout(self.nodes_widget)

        self.resetButton = QtGui.QPushButton(self.nodes_widget)
        self.resetButton.setIcon(QtGui.QIcon(":/icons/edit-undo.svg"))
        self.resetButton.setText(QtGui.QApplication.translate("Arch", "Reset nodes", None))

        lay.addWidget(self.resetButton)
        QtCore.QObject.connect(self.resetButton, QtCore.SIGNAL("clicked()"), self.resetNodes)

        self.editButton = QtGui.QPushButton(self.nodes_widget)
        self.editButton.setIcon(QtGui.QIcon(":/icons/Draft_Edit.svg"))
        self.editButton.setText(QtGui.QApplication.translate("Arch", "Edit nodes", None))
        lay.addWidget(self.editButton)
        QtCore.QObject.connect(self.editButton, QtCore.SIGNAL("clicked()"), self.editNodes)

        self.extendButton = QtGui.QPushButton(self.nodes_widget)
        self.extendButton.setIcon(QtGui.QIcon(":/icons/Snap_Perpendicular.svg"))
        self.extendButton.setText(QtGui.QApplication.translate("Arch", "Extend nodes", None))
        self.extendButton.setToolTip(QtGui.QApplication.translate("Arch", "Extends the nodes of this element to reach the nodes of another element", None))
        lay.addWidget(self.extendButton)
        QtCore.QObject.connect(self.extendButton, QtCore.SIGNAL("clicked()"), self.extendNodes)

        self.connectButton = QtGui.QPushButton(self.nodes_widget)
        self.connectButton.setIcon(QtGui.QIcon(":/icons/Snap_Intersection.svg"))
        self.connectButton.setText(QtGui.QApplication.translate("Arch", "Connect nodes", None))
        self.connectButton.setToolTip(QtGui.QApplication.translate("Arch", "Connects nodes of this element with the nodes of another element", None))
        lay.addWidget(self.connectButton)
        QtCore.QObject.connect(self.connectButton, QtCore.SIGNAL("clicked()"), self.connectNodes)

        self.toggleButton = QtGui.QPushButton(self.nodes_widget)
        self.toggleButton.setIcon(QtGui.QIcon(":/icons/dagViewVisible.svg"))
        self.toggleButton.setText(QtGui.QApplication.translate("Arch", "Toggle all nodes", None))
        self.toggleButton.setToolTip(QtGui.QApplication.translate("Arch", "Toggles all structural nodes of the document on/off", None))
        lay.addWidget(self.toggleButton)
        QtCore.QObject.connect(self.toggleButton, QtCore.SIGNAL("clicked()"), self.toggleNodes)

        self.extrusion_widget = QtGui.QWidget()
        self.extrusion_widget.setWindowTitle(QtGui.QApplication.translate("Arch", "Extrusion Tools", None))
        lay = QtGui.QVBoxLayout(self.extrusion_widget)

        self.selectToolButton = QtGui.QPushButton(self.extrusion_widget)
        self.selectToolButton.setIcon(QtGui.QIcon())
        self.selectToolButton.setText(QtGui.QApplication.translate("Arch", "Select tool...", None))
        self.selectToolButton.setToolTip(QtGui.QApplication.translate("Arch", "Select object or edges to be used as a Tool (extrusion path)", None))
        lay.addWidget(self.selectToolButton)
        QtCore.QObject.connect(self.selectToolButton, QtCore.SIGNAL("clicked()"), self.setSelectionFromTool)

        self.form = [self.form, self.nodes_widget, self.extrusion_widget]
        self.Object = obj
        self.observer = None
        self.nodevis = None

    def editNodes(self):

        FreeCADGui.Control.closeDialog()
        FreeCADGui.runCommand("Draft_Edit")

    def resetNodes(self):

        self.Object.Proxy.onChanged(self.Object,"ResetNodes")

    def extendNodes(self,other=None):

        if not other:
            self.observer = StructSelectionObserver(self.extendNodes)
            FreeCADGui.Selection.addObserver(self.observer)
            FreeCAD.Console.PrintMessage(translate("Arch","Choose another Structure object:"))
        else:
            FreeCADGui.Selection.removeObserver(self.observer)
            self.observer = None
            if Draft.getType(other) != "Structure":
                FreeCAD.Console.PrintError(translate("Arch","The chosen object is not a Structure")+"\n")
            else:
                if not other.Nodes:
                    FreeCAD.Console.PrintError(translate("Arch","The chosen object has no structural nodes")+"\n")
                else:
                    if (len(self.Object.Nodes) != 2) or (len(other.Nodes) != 2):
                        FreeCAD.Console.PrintError(translate("Arch","One of these objects has more than 2 nodes")+"\n")
                    else:
                        import DraftGeomUtils
                        nodes1 = [self.Object.Placement.multVec(v) for v in self.Object.Nodes]
                        nodes2 = [other.Placement.multVec(v) for v in other.Nodes]
                        intersect = DraftGeomUtils.findIntersection(nodes1[0],nodes1[1],nodes2[0],nodes2[1],True,True)
                        if not intersect:
                            FreeCAD.Console.PrintError(translate("Arch","Unable to find a suitable intersection point")+"\n")
                        else:
                            intersect = intersect[0]
                            FreeCAD.Console.PrintMessage(translate("Arch","Intersection found.\n"))
                            if DraftGeomUtils.findClosest(intersect,nodes1) == 0:
                                self.Object.Nodes = [self.Object.Placement.inverse().multVec(intersect),self.Object.Nodes[1]]
                            else:
                                self.Object.Nodes = [self.Object.Nodes[0],self.Object.Placement.inverse().multVec(intersect)]

    def connectNodes(self,other=None):

        if not other:
            self.observer = StructSelectionObserver(self.connectNodes)
            FreeCADGui.Selection.addObserver(self.observer)
            FreeCAD.Console.PrintMessage(translate("Arch","Choose another Structure object:"))
        else:
            FreeCADGui.Selection.removeObserver(self.observer)
            self.observer = None
            if Draft.getType(other) != "Structure":
                FreeCAD.Console.PrintError(translate("Arch","The chosen object is not a Structure")+"\n")
            else:
                if not other.Nodes:
                    FreeCAD.Console.PrintError(translate("Arch","The chosen object has no structural nodes")+"\n")
                else:
                    if (len(self.Object.Nodes) != 2) or (len(other.Nodes) != 2):
                        FreeCAD.Console.PrintError(translate("Arch","One of these objects has more than 2 nodes")+"\n")
                    else:
                        import DraftGeomUtils
                        nodes1 = [self.Object.Placement.multVec(v) for v in self.Object.Nodes]
                        nodes2 = [other.Placement.multVec(v) for v in other.Nodes]
                        intersect = DraftGeomUtils.findIntersection(nodes1[0],nodes1[1],nodes2[0],nodes2[1],True,True)
                        if not intersect:
                            FreeCAD.Console.PrintError(translate("Arch","Unable to find a suitable intersection point")+"\n")
                        else:
                            intersect = intersect[0]
                            FreeCAD.Console.PrintMessage(translate("Arch","Intersection found.")+"\n")
                            if DraftGeomUtils.findClosest(intersect,nodes1) == 0:
                                self.Object.Nodes = [self.Object.Placement.inverse().multVec(intersect),self.Object.Nodes[1]]
                            else:
                                self.Object.Nodes = [self.Object.Nodes[0],self.Object.Placement.inverse().multVec(intersect)]
                            if DraftGeomUtils.findClosest(intersect,nodes2) == 0:
                                other.Nodes = [other.Placement.inverse().multVec(intersect),other.Nodes[1]]
                            else:
                                other.Nodes = [other.Nodes[0],other.Placement.inverse().multVec(intersect)]

    def toggleNodes(self):

        if self.nodevis:
            for obj in self.nodevis:
                obj[0].ViewObject.ShowNodes = obj[1]
            self.nodevis = None
        else:
            self.nodevis = []
            for obj in FreeCAD.ActiveDocument.Objects:
                if hasattr(obj.ViewObject,"ShowNodes"):
                    self.nodevis.append([obj,obj.ViewObject.ShowNodes])
                    obj.ViewObject.ShowNodes = True

    def setSelectionFromTool(self):
        FreeCADGui.Selection.clearSelection()
        if hasattr(self.Object, "Tool"):
            tool = self.Object.Tool
            if hasattr(tool, "Shape") and tool.Shape:
                FreeCADGui.Selection.addSelection(tool)
            else:
                if not isinstance(tool, list):
                    tool = [tool]
                for o, subs in tool:
                    FreeCADGui.Selection.addSelection(o, subs)
        QtCore.QObject.disconnect(self.selectToolButton, QtCore.SIGNAL("clicked()"), self.setSelectionFromTool)
        QtCore.QObject.connect(self.selectToolButton, QtCore.SIGNAL("clicked()"), self.setToolFromSelection)
        self.selectToolButton.setText(QtGui.QApplication.translate("Arch", "Done", None))

    def setToolFromSelection(self):
        objectList = []
        selEx = FreeCADGui.Selection.getSelectionEx()
        for selExi in selEx:
            if len(selExi.SubElementNames) == 0:
                # Add entirely selected objects
                objectList.append(selExi.Object)
            else:
                subElementsNames = [subElementName for subElementName in selExi.SubElementNames if subElementName.startswith("Edge")]
                # Check that at least an edge is selected from the object's shape
                if len(subElementsNames) > 0:
                    objectList.append((selExi.Object, subElementsNames))
        if self.Object.getTypeIdOfProperty("Tool") != "App::PropertyLinkSubList":
            # Upgrade property Tool from App::PropertyLink to App::PropertyLinkSubList (note: Undo/Redo fails)
            self.Object.removeProperty("Tool")
            self.Object.addProperty("App::PropertyLinkSubList", "Tool", "Structure", QT_TRANSLATE_NOOP("App::Property", "An optional extrusion path for this element"), locked=True)
        self.Object.Tool = objectList
        QtCore.QObject.disconnect(self.selectToolButton, QtCore.SIGNAL("clicked()"), self.setToolFromSelection)
        QtCore.QObject.connect(self.selectToolButton, QtCore.SIGNAL("clicked()"), self.setSelectionFromTool)
        self.selectToolButton.setText(QtGui.QApplication.translate("Arch", "Select tool...", None))

    def accept(self):

        if self.observer:
            FreeCADGui.Selection.removeObserver(self.observer)
        if self.nodevis:
            self.toggleNodes()
        FreeCAD.ActiveDocument.recompute()
        FreeCADGui.ActiveDocument.resetEdit()
        return True


class StructSelectionObserver:

    def __init__(self,callback):
        self.callback = callback

    def addSelection(self, docName, objName, sub, pos):
        print("got ",objName)
        obj = FreeCAD.getDocument(docName).getObject(objName)
        self.callback(obj)


class _StructuralSystem(ArchComponent.Component): # OBSOLETE - All Arch objects can now be based on axes

    "The Structural System object"

    def __init__(self,obj):

        ArchComponent.Component.__init__(self,obj)
        obj.addProperty("App::PropertyLinkList","Axes","Arch",QT_TRANSLATE_NOOP("App::Property","Axes systems this structure is built on"), locked=True)
        obj.addProperty("App::PropertyIntegerList","Exclude","Arch",QT_TRANSLATE_NOOP("App::Property","The element numbers to exclude when this structure is based on axes"), locked=True)
        obj.addProperty("App::PropertyBool","Align","Arch",QT_TRANSLATE_NOOP("App::Property","If true the element are aligned with axes"), locked=True).Align = False
        self.Type = "StructuralSystem"

    def execute(self,obj):
        "creates the structure shape"

        import Part
        import DraftGeomUtils

        # creating base shape
        pl = obj.Placement
        if obj.Base:
            if hasattr(obj.Base,'Shape'):
                if obj.Base.Shape.isNull():
                    return
                if not obj.Base.Shape.Solids:
                    return

                base = None

                # applying axes
                pts = self.getAxisPoints(obj)
                if hasattr(obj,"Align"):
                    if obj.Align == False :
                        apl = self.getAxisPlacement(obj)
                    if obj.Align:
                        apl = None
                else :
                    apl = self.getAxisPlacement(obj)

                if pts:
                    fsh = []
                    for i in range(len(pts)):
                        sh = obj.Base.Shape.copy()
                        if hasattr(obj,"Exclude"):
                            if i in obj.Exclude:
                                continue
                        if apl:
                            sh.Placement.Rotation = sh.Placement.Rotation.multiply(apl.Rotation)
                        sh.translate(pts[i])
                        fsh.append(sh)

                    if fsh:
                        base = Part.makeCompound(fsh)
                        base = self.processSubShapes(obj,base,pl)

                if base:
                    if not base.isNull():
                        if base.isValid() and base.Solids:
                            if base.Volume < 0:
                                base.reverse()
                            if base.Volume < 0:
                                FreeCAD.Console.PrintError(translate("Arch","Couldn't compute a shape"))
                                return
                            base = base.removeSplitter()
                            obj.Shape = base
                            if not pl.isNull():
                                obj.Placement = pl

    def getAxisPoints(self,obj):
        "returns the gridpoints of linked axes"
        import DraftGeomUtils
        pts = []
        if len(obj.Axes) == 1:
            if hasattr(obj,"Align"):
                if obj.Align:
                    p0 = obj.Axes[0].Shape.Edges[0].Vertexes[1].Point
                    for e in obj.Axes[0].Shape.Edges:
                        p = e.Vertexes[1].Point
                        p = p.sub(p0)
                        pts.append(p)
                else:
                    for e in obj.Axes[0].Shape.Edges:
                        pts.append(e.Vertexes[0].Point)
            else:
                for e in obj.Axes[0].Shape.Edges:
                        pts.append(e.Vertexes[0].Point)
        elif len(obj.Axes) >= 2:
            set1 = obj.Axes[0].Shape.Edges
            set2 = obj.Axes[1].Shape.Edges
            for e1 in set1:
                for e2 in set2:
                    pts.extend(DraftGeomUtils.findIntersection(e1,e2))
        return pts

    def getAxisPlacement(self,obj):
        "returns an axis placement"
        if obj.Axes:
            return obj.Axes[0].Placement
        return None


class _ViewProviderStructuralSystem(ArchComponent.ViewProviderComponent):

    "A View Provider for the Structural System object"

    def getIcon(self):

        import Arch_rc
        return ":/icons/Arch_StructuralSystem_Tree.svg"


if FreeCAD.GuiUp:
    FreeCADGui.addCommand("Arch_Structure", _CommandStructure())
    FreeCADGui.addCommand("Arch_StructuralSystem", CommandStructuralSystem())
    FreeCADGui.addCommand("Arch_StructuresFromSelection", CommandStructuresFromSelection())

    class _ArchStructureGroupCommand:

        def GetCommands(self):
            return ("Arch_Structure", "Arch_StructuralSystem", "Arch_StructuresFromSelection")
        def GetResources(self):
            return { "MenuText": QT_TRANSLATE_NOOP("Arch_StructureTools", "Structure tools"),
                     "ToolTip": QT_TRANSLATE_NOOP("Arch_StructureTools", "Structure tools")
                   }
        def IsActive(self):
            return not FreeCAD.ActiveDocument is None

    FreeCADGui.addCommand("Arch_StructureTools", _ArchStructureGroupCommand())
