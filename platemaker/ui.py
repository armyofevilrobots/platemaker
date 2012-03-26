#!python

# Created by Michael Kessler, 2012
"""Utility for organizing and panelizing objects for 3d printing."""

import sys
try:
    #Done in reverse in case we need PySide
    #TODO: We should _really_ not be using import * from either
    #pyqt/pyside or opengl, as they have TONS of crap we may accidentally
    #redefine or stomp on. We should only import what we need.
    from PyQt4.QtOpenGL import QGLWidget
    from PyQt4 import QtGui, QtCore
except ImportError, exc:
    sys.stderr.write("Failed to import PyQT4/OpenGL. "
            "Falling back to PySide.\n")
    from PySide import QtGui, QtCore
    from PySide.QtOpenGL import QGLWidget
import struct
import re
import math

try:
    from OpenGL.GL import * #pylint: disable-msg=W0614
    from OpenGL.GLU import * #pylint: disable-msg=W0614
except Exception, exc:
    print "Could not initialize OpenGL.", exc
    sys.exit(1)

from platemaker.utils import (
        TEXTCHARS, IS_BINARY_STRING, COLOR_LIST, parse_args)

def cleanupInputValueDecorator(fn):
    """Cleans up input value if it is out of bounds
    or invalid for float"""
    def fndecorator(self,value):
        try:
            value = float(value)
        except ValueError:
            value = 0
        return fn(self, value)
    return fndecorator

class MyViewport(QGLWidget):
    """Viewport widget"""
    def __init__(self, parent = None):
        QGLWidget.__init__(self, parent)
        self.setMinimumSize( 200, 200 )
        self.models = []
        self.dockwidgets = []
        self.cameraRotate = [0, 0, 0]
        self.cameraTranslate = [0 ,0, -20]
        self.oldx = 0.0
        self.oldy = 0.0
        self.x = 1
        self.y = 1
        self.lastColor = 0

    def resetFiles(self):
        """Clears all files back to a blank slate."""
        while len(self.dockwidgets):
            widget = self.dockwidgets.pop()
            widget.close()
            #widget.setParent(None)
            #self.parent().removeDockWidget(widget)
            del widget

        self.dockwidgets = list()
        self.models = list()
        self.updateGL()


    def exportFile(self, filepath):
        """Exports the file merged"""
        outputFile = open(filepath, 'w')
        objectName = "Exported From Platemaker"
        outputFile.write("solid %s\n" % objectName)
        for model in self.models:
            model.writeToFile(outputFile, False)
        outputFile.write("endsolid %s\n" % objectName)
        outputFile.close()

    def openFiles(self, filepaths):
        """Open files for merging"""
        for filepath in filepaths:
            self.openFile(filepath)

    def openFile(self, filepath):
        """Open a file for merging"""
        offset = 0
        self.lastColor += 1
        if (self.lastColor > len( COLOR_LIST ) - 1):
            self.lastColor = 0
        infile = open(filepath, 'r')
        inputModel = model(infile, self.lastColor)
        inputModel.transform[0] = offset
        offset += 0
        self.addModel(inputModel)
        mc = QtGui.QDockWidget(self)
        mc.setWindowTitle(infile.name)
        mc.setAllowedAreas(
                QtCore.Qt.TopDockWidgetArea |
                QtCore.Qt.BottomDockWidgetArea |
                QtCore.Qt.LeftDockWidgetArea |
                QtCore.Qt.RightDockWidgetArea )
        mcc = QtGui.QWidget(mc)
        mcl = QtGui.QHBoxLayout(mcc)
        print dir(mcl)
        mcv = QtGui.QDoubleValidator(mcc)

        mcx = TransformEdit(mcc)
        mcx.setValue(0.0)
        mcx.setMinimumWidth(60)
        mcx.valueChanged.connect(inputModel.setX)
        mcx.valueChanged.connect(self.updateGL)
        mcl.addWidget(mcx)

        mcy = TransformEdit(mcc)
        mcy.setValue(0.0)
        mcy.setMinimumWidth(60)
        mcy.valueChanged.connect(inputModel.setY)
        mcy.valueChanged.connect(self.updateGL)
        mcl.addWidget(mcy)

        mcz = TransformEdit(mcc)
        mcz.setValue(0.0)
        mcz.setMinimumWidth(60)
        mcz.valueChanged.connect(inputModel.setZ)
        mcz.valueChanged.connect(self.updateGL)
        mcl.addWidget(mcz)

        mccb = QtGui.QPushButton(mcc)
        mccb.setFixedWidth(30)
        mccb.clicked.connect(inputModel.pickColor)
        mcl.addWidget(mccb)

        mcc.setLayout( mcl )
        mc.setWidget(mcc)
        self.parent().addDockWidget( QtCore.Qt.RightDockWidgetArea, mc )
        self.dockwidgets.append(mc)

    def showOpenDialog(self):
        """Show the open file dialog"""
        fileDialog = QtGui.QFileDialog(self)
        fileDialog.setFileMode(QtGui.QFileDialog.ExistingFiles)
        fileDialog.filesSelected.connect(self.openFiles)
        filters = ["Stereo Lithography files (*.stl)"]
        fileDialog.setNameFilters(filters)
        fileDialog.exec_()

    def showExportDialog(self):
        """Show the export file dialog"""
        fileDialog = QtGui.QFileDialog(self)
        fileDialog.setAcceptMode( QtGui.QFileDialog.AcceptSave )
        fileDialog.fileSelected.connect(self.exportFile)
        filters = ["Stereo Lithography files (*.stl)"]
        fileDialog.setNameFilters( filters )
        fileDialog.exec_()



    def setRX(self,value):
        self.cameraTranslate[0] = value / 100.0
        self.updateGL()

    def setRY(self,value):
        self.cameraTranslate[1] = value / 100.0
        self.updateGL()

    def setRZ(self,value):
        self.cameraTranslate[2] = value / 100.0
        self.updateGL()

    def mousePressEvent(self, mouseEvent):
        self.oldx = mouseEvent.x()
        self.oldy = mouseEvent.y()

    def mouseMoveEvent(self, mouseEvent):
        if int(mouseEvent.buttons()) != QtCore.Qt.NoButton :
            # user is dragging
            delta_x = mouseEvent.x() - self.oldx
            delta_y = self.oldy - mouseEvent.y()
            if int(mouseEvent.buttons()) & QtCore.Qt.LeftButton :
                if int(mouseEvent.buttons()) & QtCore.Qt.MidButton :
                    print "dolly {} {}".format(delta_x, delta_y)
                else:
                    self.cameraRotate[2] += (delta_x * 1)
                    self.cameraRotate[0] -= (delta_y * 1)
            elif int(mouseEvent.buttons()) & QtCore.Qt.RightButton :
                self.cameraTranslate[2] += delta_y * 0.1
            self.oldx = mouseEvent.x()
            self.oldy = mouseEvent.y()
            self.update()

    def initializeGL(self):
        """
        GL Setup Routine
        """
        glEnable( GL_LIGHTING )
        glColorMaterial ( GL_FRONT_AND_BACK, GL_DIFFUSE )
        glEnable ( GL_COLOR_MATERIAL )
        glEnable(GL_LIGHT0)
        glShadeModel (GL_SMOOTH)
        glEnable(GL_DEPTH_TEST)
        glLightfv(GL_LIGHT0, GL_AMBIENT, [0.1, 0.1, 0.1, 0] )
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [.2, .2, .2, 0])
        glLightfv(GL_LIGHT0, GL_SPECULAR, [0, 0, 0, 0])

    def paintGL(self):
        """
        Drawing Routine
        """
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glMatrixMode( GL_PROJECTION )
        glLoadIdentity()
        #glOrtho(-5, 5, -5, 5, .1, 100)

        ratio = float(self.x) / float(self.y)
        gluPerspective(30.0, ratio, 0.1, 1000)

        glMatrixMode( GL_MODELVIEW )
        glLoadIdentity()
        glLightfv(GL_LIGHT0, GL_POSITION, (100, 100, 100))

        glTranslate(
                self.cameraTranslate[0],
                self.cameraTranslate[1],
                self.cameraTranslate[2] )
        glRotate( -45, 1, 0, 0 )
        glRotate( self.cameraRotate[0], 1, 0, 0)
        glRotate( self.cameraRotate[1], 0, 1, 0)
        glRotate( self.cameraRotate[2], 0, 0, 1)
        glScale( 0.1, 0.1, 0.1 )


        for model in self.models:

            glPushMatrix()
            tf = model.transform
            glTranslate( tf[0], tf[1], tf[2] )
            glCallList(model.drawList)
            glPopMatrix()


    def addModel(self, model):
        self.models.append(model)

    def resizeGL(self, w, h):
        """
        Resize the GL Viewport
        """
        glViewport(0, 0, w, h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        self.x = w
        self.y = h

#class TransformEdit(QtGui.QLineEdit):
    #def __init__(self,parent = None):
        #QtGui.QLineEdit.__init__(self, parent)

    #def wheelEvent(self,event):
        #currentValue = float(self.text())
        #self.setText("{}".format(currentValue + (event.delta() / 10.0)))

class TransformEdit(QtGui.QDoubleSpinBox):
    def __init__(self, parent = None):
        QtGui.QDoubleSpinBox.__init__(self, parent)
        self.setMinimum(-500)
        self.setMaximum(500)
        self.setSingleStep(5)


class bounding:
    def __init__(self):
        self.px = None
        self.nx = None
        self.py = None
        self.ny = None

    def checkVertex(self, vertex):
        self.inputPx(vertex[0])
        self.inputNx(vertex[0])
        self.inputPy(vertex[1])
        self.inputNy(vertex[1])

    def inputPx(self, value):
        if self.px:
            if ( value > self.px ):
                self.px = value
        else:
            self.px = value

    def inputPy(self, value):
        if self.py:
            if ( value > self.py ):
                self.py = value
        else:
            self.py = value

    def inputNx(self, value):
        if self.nx:
            if ( value < self.nx ):
                self.nx = value
        else:
            self.nx = value

    def inputNy(self, value):
        if self.ny:
            if ( value < self.ny ):
                self.ny = value
        else:
            self.ny = value

class poly:
    def __init__(self):
        self.vertex = []
        self.nx = 0.0
        self.ny = 0.0
        self.nz = 0.0
    def setNormal(self, x, y, z):
        self.nx = x
        self.ny = y
        self.nz = z
    def addVertex(self, a, b, c):
        components = [a, b, c]
        self.vertex.append(components)

class model(QtCore.QObject):

    def __init__(self, filestream, colorNumber=0, parent=None):
        QtCore.QObject.__init__(self, parent)
        self.file = filestream
        self.polygons = []
        self.transform = [0.0, 0.0, 0.0]
        self.color = COLOR_LIST[colorNumber]
        self.drawList = None

        if (not IS_BINARY_STRING( self.file.read(1024))):
            self.parseAscii()
        else:
            self.parseBinary()

        self.bakeGeometry()

    def bakeGeometry(self):
        self.drawList = glGenLists(1)
        glNewList(self.drawList, GL_COMPILE)

        glBegin(GL_TRIANGLES)

        glColor(self.color)
        for polygon in self.polygons:
            for vertex in polygon.vertex:
                glVertex3f( vertex[0], vertex[1], vertex[2] )
                glNormal3f( polygon.nx, polygon.ny, polygon.nz )
        glEnd()
        glEndList()

    @cleanupInputValueDecorator
    def setX(self, value):
        self.transform[0] = float(value)

    @cleanupInputValueDecorator
    def setY(self, value):
        self.transform[1] = float(value)

    @cleanupInputValueDecorator
    def setZ(self, value):
        self.transform[2] = float(value)

    def pickColor(self):
        picker = QtGui.QColorDialog()
        picker.colorSelected.connect(self.selectColor)
        picker.exec_()

    def selectColor(self,color):
        self.color = [
                color.red() / 255.0,
                color.green() / 255.0,
                color.blue() / 255.0]

    def writeToFile(self, f, writeHeader = True):
        if (writeHeader):
            f.write("solid %s\n" % self.file.name)
        for polygon in self.polygons:
            f.write("  facet normal %f %f %f\n" %
                    ( polygon.nx, polygon.ny, polygon.nz))
            f.write("    outer loop\n" )
            for vertex in polygon.vertex:
                f.write("      vertex %f %f %f\n" %
                        (
                            vertex[0] + self.transform[0],
                            vertex[1] + self.transform[1],
                            vertex[2] + self.transform[2]
                            )
                        )
            f.write("    endloop\n")
            f.write("  endfacet\n")
        if ( writeHeader):
            f.write("endsolid %s\n" % self.file.name)


    def description(self):
        self.computeBoundingBox()
        bb = self.boundingbox
        return "File: %s\nPolygons: %d" % (self.file, len(self.polygons))

    def computeBoundingBox(self):
        bb = bounding()
        for polygon in self.polygons:
            for vertex in polygon.vertex:
                bb.checkVertex(vertex)
        self.boundingbox = bb

    def parseAscii(self):
        """Parses an Ascii stl file (this is SIMPLE!)"""
        # Reset the starting location to the beginning.
        current = None
        self.file.seek(0)

        normalFinder = re.compile(
                "[\s]*facet[\s]*normal[\s]+([^\s]+)[\s]+([^\s]+)[\s]+([^\s]+)")
        vertexFinder = re.compile(
                "[\s]*vertex[\s]+([^\s]+)[\s]+([^\s]+)[\s]+([^\s]+)")
        for line in self.file:
            # If the line contains 'solid' then continue.
            if ( line.find("solid") != -1 ):
                continue
            elif ( line.find("vertex") != -1 ):
                result = vertexFinder.match( line )
                current.addVertex(
                        float(result.group(1)),
                        float(result.group(2)),
                        float(result.group(3)) )
            elif ( line.find("endfacet") != -1 ):
                self.polygons.append(current)
            elif ( line.find("facet normal") != -1 ):
                current = poly()
                result = normalFinder.match( line )
                current.setNormal(
                        float(result.group(1)),
                        float(result.group(2)),
                        float(result.group(3)) )

    def parseBinary(self):
        """Parses an Ascii stl file (shorter, but less SIMPLE!)"""
        # Make sure we start after the header.
        self.file.seek(80)

        # Figure out how large this file is.
        self.length = struct.unpack("<I", self.file.read(4))[0]

        for i in xrange( 0, self.length):
            current = poly()
            (na, nb, nc) = struct.unpack("<3f", self.file.read(12))
            current.setNormal( na, nb, nc )
            for p in xrange( 0, 3 ):
                (va, vb, vc) = struct.unpack("<3f", self.file.read(12))
                current.addVertex( va, vb, vc )
            b = struct.unpack( "<h", self.file.read(2))
            self.polygons.append(current)



def main():
    """If __name__ magic ;)"""
    results = parse_args()
    app = QtGui.QApplication(sys.argv)
    mainWindow = QtGui.QMainWindow()
    myViewport = MyViewport()
    mainWindow.setCentralWidget( myViewport )
    mainWindow.setWindowTitle('Platemaker')

    menu = mainWindow.menuBar()
    fileMenu = menu.addMenu('File')
    openAction = QtGui.QAction('Open...', mainWindow)
    openAction.setShortcut( 'Ctrl+o' )
    openAction.triggered.connect(myViewport.showOpenDialog)
    fileMenu.addAction(openAction)

    exportAction = QtGui.QAction('Export...', mainWindow)
    exportAction.setShortcut( 'Ctrl+e' )
    exportAction.triggered.connect(myViewport.showExportDialog)
    fileMenu.addAction(exportAction)

    fileMenu.addSeparator()
    closeAction = QtGui.QAction('Reset', mainWindow)
    closeAction.setShortcut('Ctrl+r')
    closeAction.triggered.connect(myViewport.resetFiles)
    fileMenu.addAction(closeAction)

    mainWindow.show()

    if ( results.input ):
        for infile in results.input:
            myViewport.openFile(infile)
    sys.exit(app.exec_())
