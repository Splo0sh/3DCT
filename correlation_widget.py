#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Title			: correlation_widget
# @Project			: 3DCTv2
# @Description		: Extracting 2D and 3D points for 2D to 3D correlation
# @Author			: Jan Arnold
# @Email			: jan.arnold (at) coraxx.net
# @Credits			:
# @Maintainer		: Jan Arnold
# @Date				: 2016/01
# @Version			: 0.1
# @Status			: developement
# @Usage			: part of 3D Correlation Toolbox
# @Notes			:
# @Python_version	: 2.7.10
# @Last Modified	: 2016/03/03
# ============================================================================

import sys
import os
import re
from PyQt4 import QtCore, QtGui, uic
import numpy as np
import cv2
import tifffile as tf
## Colored stdout
import clrmsg
## Custom Qt functions (mostly to handle events) widgets in QtDesigner are promoted to
import QtCustom
## CSV handler
import csv_handler

execdir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(execdir)
workingdir = execdir

qtCreatorFile_main = os.path.join(execdir, "TDCT_correlation.ui")
Ui_WidgetWindow, QtBaseClass = uic.loadUiType(qtCreatorFile_main)


class MainWidget(QtGui.QWidget, Ui_WidgetWindow):
	def __init__(self, parent=None, left=None, right=None):
		self.debug = True
		if self.debug is True: print clrmsg.DEBUG + 'Debug messages enabled'
		QtGui.QWidget.__init__(self, parent)
		Ui_WidgetWindow.__init__(self)
		self.setupUi(self)
		self.counter = 0		# Just for testing (loop counter for test button)

		## Tableview and models
		self.modelLleft = QtCustom.QStandardItemModelCustom(self)
		self.tableView_left.setModel(self.modelLleft)
		self.modelLleft.tableview = self.tableView_left
		self.modelRight = QtCustom.QStandardItemModelCustom(self)
		self.tableView_right.setModel(self.modelRight)
		self.modelRight.tableview = self.tableView_right

		## store parameters for resizing
		self.parent = parent
		self.size = 500
		self.left = left
		self.right = right

		## Initialize parameters
		self.brightness_left = 0
		self.contrast_left = 10
		self.brightness_right = 0
		self.contrast_right = 10
		## Initialize Images
		self.initImageLeft()
		self.initImageRight()

		## connect item change signal to write changes in model back to QGraphicItems as well as highlighting selected points
		self.modelLleft.itemChanged.connect(self.tableView_left.updateItems)
		self.modelRight.itemChanged.connect(self.tableView_right.updateItems)
		self.tableView_left.selectionModel().selectionChanged.connect(self.tableView_left.showSelectedItem)
		self.tableView_right.selectionModel().selectionChanged.connect(self.tableView_right.showSelectedItem)

		# SpinBoxes
		self.spinBox_rot.valueChanged.connect(self.rotateImage)
		self.spinBox_markerSize.valueChanged.connect(self.changeMarkerSize)

		## Buttons
		self.toolButton_rotcw.clicked.connect(lambda: self.rotateImage45(direction='cw'))
		self.toolButton_rotccw.clicked.connect(lambda: self.rotateImage45(direction='ccw'))
		self.pushButton_test.clicked.connect(self.test)
		self.toolButton_brightness_reset.clicked.connect(lambda: self.horizontalSlider_brightness.setValue(0))
		self.toolButton_contrast_reset.clicked.connect(lambda: self.horizontalSlider_contrast.setValue(10))
		self.toolButton_importPoints.clicked.connect(self.importPoints)
		self.toolButton_exportPoints.clicked.connect(self.exportPoints)

		## Sliders
		self.horizontalSlider_brightness.valueChanged.connect(self.adjustBrightCont)
		self.horizontalSlider_contrast.valueChanged.connect(self.adjustBrightCont)
		## Capture focus change events
		QtCore.QObject.connect(app, QtCore.SIGNAL("focusChanged(QWidget *, QWidget *)"), self.changedFocusSlot)

		## Pass models and scenes to tableviewa
		self.tableView_left._model = self.modelLleft
		self.tableView_right._model = self.modelRight
		self.tableView_left._scene = self.sceneLeft
		self.tableView_right._scene = self.sceneRight

	def keyPressEvent(self,event):
		if event.key() == QtCore.Qt.Key_Delete:
			if self.currentFocusedWidgetName == 'tableView_left':
				if self.debug is True: print clrmsg.DEBUG + "Deleting item(s) on the left side"
				# self.deleteItem(self.tableView_left,self.modelLleft,self.sceneLeft)
				self.tableView_left.deleteItem()
				# self.updateItems(self.modelLleft,self.sceneLeft)
				self.tableView_left.updateItems()
			elif self.currentFocusedWidgetName == 'tableView_right':
				if self.debug is True: print clrmsg.DEBUG + "Deleting item(s) on the right side"
				# self.deleteItem(self.tableView_right,self.modelRight,self.sceneRight)
				self.tableView_right.deleteItem()
				# self.updateItems(self.modelRight,self.sceneRight)
				self.tableView_right.updateItems()

	def test(self):
		if self.counter == 0:
			self.widget_scatterplot.setupCanvas(width=4,height=4,dpi=52,toolbar=False)
		if self.counter < 2:
			self.widget_scatterplot.scatterPlot(x='random',y='random',frame=True,framesize=6,xlabel="nm",ylabel="nm")
		if self.counter == 2:
			self.widget_scatterplot.clearAll()
		if self.counter == 3:
			self.widget_scatterplot.setupCanvas(width=4,height=4,dpi=72,toolbar=True)
			self.widget_scatterplot.scatterPlot(x='random',y='random',frame=True,framesize=6,xlabel="lol",ylabel="rofl")
		self.counter += 1
		self.modelLleft.itemFromIndex(self.modelLleft.index(0, 2)).setForeground(QtCore.Qt.red)

	def changedFocusSlot(self, former, current):
		if self.debug is True: print clrmsg.DEBUG + "focus changed from/to:", former.objectName() if former else former, \
				current.objectName() if current else current
		if current:
			self.currentFocusedWidgetName = current.objectName()
			self.currentFocusedWidget = current
		if former:
			self.formerFocusedWidgetName = former.objectName()
			self.formerFocusedWidget = former

		## Lable showing selected image
		if self.currentFocusedWidgetName in ['spinBox_rot','spinBox_markerSize','horizontalSlider_brightness','horizontalSlider_contrast']:
			pass
		else:
			if self.currentFocusedWidgetName != 'graphicsView_left' and self.currentFocusedWidgetName != 'graphicsView_right':
				self.label_selimg.setStyleSheet("color: rgb(255, 190, 0);")
				self.label_selimg.setText('none')
				self.label_markerSizeNano.setText('')
				self.label_markerSizeNanoUnit.setText('')
				self.label_imgpxsize.setText('')
				self.label_imgpxsizeUnit.setText('')
				self.label_imagetype.setText('')
				self.ctrlEnDisAble(False)
			elif self.currentFocusedWidgetName == 'graphicsView_left':
				self.label_selimg.setStyleSheet("color: rgb(0, 225, 90);")
				self.label_selimg.setText('left')
				self.label_imagetype.setStyleSheet("color: rgb(0, 225, 90);")
				self.label_imagetype.setText('(2D)' if '{0:b}'.format(self.sceneLeft.imagetype)[-1] == '1' else '(3D)')
				self.ctrlEnDisAble(True)
			elif self.currentFocusedWidgetName == 'graphicsView_right':
				self.label_selimg.setStyleSheet("color: rgb(0, 190, 255);")
				self.label_selimg.setText('right')
				self.label_imagetype.setStyleSheet("color: rgb(0, 190, 255);")
				self.label_imagetype.setText('(2D)' if '{0:b}'.format(self.sceneRight.imagetype)[-1] == '1' else '(3D)')
				self.ctrlEnDisAble(True)

		# ## Lable showing selected table
		if self.currentFocusedWidgetName != 'tableView_left' and self.currentFocusedWidgetName != 'tableView_right':
			self.label_selectedTable.setStyleSheet("color: rgb(255, 190, 0);")
			self.label_selectedTable.setText('none')
			self.ctrlEnDisAble(True)
		elif self.currentFocusedWidgetName == 'tableView_left':
			self.label_selectedTable.setStyleSheet("color: rgb(0, 225, 90);")
			self.label_selectedTable.setText('left')
			self.ctrlEnDisAble(False)
		elif self.currentFocusedWidgetName == 'tableView_right':
			self.label_selectedTable.setStyleSheet("color: rgb(0, 190, 255);")
			self.label_selectedTable.setText('right')
			self.ctrlEnDisAble(False)

		## Feed saved rotation angle/brightness-contrast value from selected image to spinbox/slider
		# Block emitting signals for correct setting of BOTH sliders. Otherwise the second one gets overwritten with the old value
		self.horizontalSlider_brightness.blockSignals(True)
		self.horizontalSlider_contrast.blockSignals(True)
		if self.currentFocusedWidgetName == 'graphicsView_left':
			self.spinBox_rot.setValue(self.sceneLeft.rotangle)
			self.spinBox_markerSize.setValue(self.sceneLeft.markerSize)
			self.horizontalSlider_brightness.setValue(self.brightness_left)
			self.horizontalSlider_contrast.setValue(self.contrast_left)
			self.label_imgpxsize.setText(str(self.sceneLeft.pixelSize))  # + ' um') # breaks markersize adjustments check
			self.label_imgpxsizeUnit.setText('um') if self.sceneLeft.pixelSize else self.label_imgpxsizeUnit.setText('')
		elif self.currentFocusedWidgetName == 'graphicsView_right':
			self.spinBox_rot.setValue(self.sceneRight.rotangle)
			self.spinBox_markerSize.setValue(self.sceneRight.markerSize)
			self.horizontalSlider_brightness.setValue(self.brightness_right)
			self.horizontalSlider_contrast.setValue(self.contrast_right)
			self.label_imgpxsize.setText(str(self.sceneRight.pixelSize))  # + ' um') # breaks markersize adjustments check
			self.label_imgpxsizeUnit.setText('um') if self.sceneRight.pixelSize else self.label_imgpxsizeUnit.setText('')
		# Unblock emitting signals.
		self.horizontalSlider_brightness.blockSignals(False)
		self.horizontalSlider_contrast.blockSignals(False)
		# update marker size in nm
		self.changeMarkerSize()

	## Funtion to dis-/enabling the buttons controlling rotation and contrast/brightness
	def ctrlEnDisAble(self,status):
		self.spinBox_rot.setEnabled(status)
		self.spinBox_markerSize.setEnabled(status)
		self.horizontalSlider_brightness.setEnabled(status)
		self.horizontalSlider_contrast.setEnabled(status)
		self.toolButton_brightness_reset.setEnabled(status)
		self.toolButton_contrast_reset.setEnabled(status)
		self.toolButton_rotcw.setEnabled(status)
		self.toolButton_rotccw.setEnabled(status)
		self.toolButton_importPoints.setEnabled(not status)
		self.toolButton_exportPoints.setEnabled(not status)

												###############################################
												###### Image initialization and rotation ######
												#################### START ####################
	def initImageLeft(self):
		if self.left is not None:
			## Changed GraphicsSceneLeft(self) to QtCustom.QGraphicsSceneCustom(self.graphicsView_left) to reuse class for both scenes
			self.sceneLeft = QtCustom.QGraphicsSceneCustom(self.graphicsView_left,side='left',model=self.modelLleft)
			## set pen color yellow
			self.sceneLeft.pen = QtGui.QPen(QtCore.Qt.red)
			## Get pixel size
			self.sceneLeft.pixelSize = self.pxSize(self.left)
			self.sceneLeft.pixelSizeUnit = 'um'
			## Load image, assign it to scene and store image type information
			self.img_left,self.sceneLeft.imagetype,self.imgstack_left = self.imread(self.left)
			## link image to QTableview for determining z
			self.tableView_left.img = self.imgstack_left
			## check if coloring z values in table is needed (correlation needs z=0 in 2D image, so no checking for valid z with 2D images needed)
			if self.imgstack_left is None:
				self.sceneLeft._z = False
			else:
				self.sceneLeft._z = True
			# self.pixmap_left = QtGui.QPixmap(self.left)
			self.pixmap_left = self.cv2Qimage(self.img_left)
			self.pixmap_item_left = QtGui.QGraphicsPixmapItem(self.pixmap_left, None, self.sceneLeft)
			## connect scenes to gui elements
			self.graphicsView_left.setScene(self.sceneLeft)
			## reset scaling (needed for reinizialization)
			self.graphicsView_left.resetMatrix()
			## scaling scene, not image
			scaling_factor = float(self.size)/max(self.pixmap_left.width(), self.pixmap_left.height())
			self.graphicsView_left.scale(scaling_factor,scaling_factor)

	def initImageRight(self):
		if self.right is not None:
			self.sceneRight = QtCustom.QGraphicsSceneCustom(self.graphicsView_right,side='right',model=self.modelRight)
			## set pen color yellow
			self.sceneRight.pen = QtGui.QPen(QtCore.Qt.yellow)
			## Get pixel size
			self.sceneRight.pixelSize = self.pxSize(self.right)
			self.sceneRight.pixelSizeUnit = 'um'
			## Load image, assign it to scene and store image type information
			self.img_right,self.sceneRight.imagetype,self.imgstack_right = self.imread(self.right)
			## link image to QTableview for determining z
			self.tableView_right.img = self.imgstack_right
			## check if coloring z values in table is needed (correlation needs z=0 in 2D image, so no checking for valid z with 2D images needed)
			if self.imgstack_right is None:
				self.sceneRight._z = False
			else:
				self.sceneRight._z = True
			# self.pixmap_right = QtGui.QPixmap(self.right)
			self.pixmap_right = self.cv2Qimage(self.img_right)
			self.pixmap_item_right = QtGui.QGraphicsPixmapItem(self.pixmap_right, None, self.sceneRight)
			## connect scenes to gui elements
			self.graphicsView_right.setScene(self.sceneRight)
			## reset scaling (needed for reinizialization)
			self.graphicsView_right.resetMatrix()
			## scaling scene, not image
			scaling_factor = float(self.size)/max(self.pixmap_right.width(), self.pixmap_right.height())
			self.graphicsView_right.scale(scaling_factor,scaling_factor)

	def rotateImage(self):
		if self.label_selimg.text() == 'left':
			if int(self.spinBox_rot.value()) == 360:
				self.spinBox_rot.setValue(0)
			elif int(self.spinBox_rot.value()) == -1:
				self.spinBox_rot.setValue(359)
			self.graphicsView_left.rotate(int(self.spinBox_rot.value())-self.sceneLeft.rotangle)
			self.sceneLeft.rotangle = int(self.spinBox_rot.value())
			## Update graphics
			self.sceneLeft.enumeratePoints()
		elif self.label_selimg.text() == 'right':
			if int(self.spinBox_rot.value()) == 360:
				self.spinBox_rot.setValue(0)
			elif int(self.spinBox_rot.value()) == -1:
				self.spinBox_rot.setValue(359)
			self.graphicsView_right.rotate(int(self.spinBox_rot.value())-self.sceneRight.rotangle)
			self.sceneRight.rotangle = int(self.spinBox_rot.value())
			## Update graphics
			self.sceneRight.enumeratePoints()

	def rotateImage45(self,direction=None):
		if direction is None:
			print clrmsg.ERROR + "Please specify direction ('cw' or 'ccw')."
		# rotate 45 degree clockwise
		elif direction == 'cw':
			if self.label_selimg.text() == 'left':
				self.sceneLeft.rotangle = self.sceneLeft.rotangle+45
				self.graphicsView_left.rotate(45)
				self.sceneLeft.rotangle = self.anglectrl(angle=self.sceneLeft.rotangle)
				self.spinBox_rot.setValue(self.sceneLeft.rotangle)
				## Update graphics
				self.sceneLeft.enumeratePoints()
			elif self.label_selimg.text() == 'right':
				self.sceneRight.rotangle = self.sceneRight.rotangle+45
				self.graphicsView_right.rotate(45)
				self.sceneRight.rotangle = self.anglectrl(angle=self.sceneRight.rotangle)
				self.spinBox_rot.setValue(self.sceneRight.rotangle)
				## Update graphics
				self.sceneRight.enumeratePoints()
		# rotate 45 degree anticlockwise
		elif direction == 'ccw':
			if self.label_selimg.text() == 'left':
				self.sceneLeft.rotangle = self.sceneLeft.rotangle-45
				self.graphicsView_left.rotate(-45)
				self.sceneLeft.rotangle = self.anglectrl(angle=self.sceneLeft.rotangle)
				self.spinBox_rot.setValue(self.sceneLeft.rotangle)
			elif self.label_selimg.text() == 'right':
				self.sceneRight.rotangle = self.sceneRight.rotangle-45
				self.graphicsView_right.rotate(-45)
				self.sceneRight.rotangle = self.anglectrl(angle=self.sceneRight.rotangle)
				self.spinBox_rot.setValue(self.sceneRight.rotangle)

	def anglectrl(self,angle=None):
		if angle is None:
			print clrmsg.ERROR + "Please specify side, e.g. anglectrl(angle=self.sceneLeft.rotangle)"
		elif angle >= 360:
			angle = angle-360
		elif angle < 0:
			angle = angle+360
		return angle

	def changeMarkerSize(self):
		if self.label_selimg.text() == 'left':
			self.sceneLeft.markerSize = int(self.spinBox_markerSize.value())
			## Update graphics
			self.sceneLeft.enumeratePoints()
			if self.sceneLeft.pixelSize:
				if self.debug is True: print clrmsg.DEBUG + "Doing stuff with image pixelSize (left image).", self.label_imgpxsize.text()
				try:
					self.label_markerSizeNano.setText(str(self.sceneLeft.markerSize*2*self.sceneLeft.pixelSize))
					self.label_markerSizeNanoUnit.setText(self.sceneLeft.pixelSizeUnit)
				except:
					if self.debug is True: print clrmsg.DEBUG + "Image pixel size is not a number:", self.label_imgpxsize.text()
					self.label_markerSizeNano.setText("NaN")
					self.label_markerSizeNanoUnit.setText('')
			else:
				self.label_markerSizeNano.setText('')
				self.label_markerSizeNanoUnit.setText('')
		elif self.label_selimg.text() == 'right':
			self.sceneRight.markerSize = int(self.spinBox_markerSize.value())
			## Update graphics
			self.sceneRight.enumeratePoints()
			if self.sceneRight.pixelSize:
				if self.debug is True: print clrmsg.DEBUG + "Doing stuff with image pixelSize (right image).", self.label_imgpxsize.text()
				try:
					self.label_markerSizeNano.setText(str(self.sceneRight.markerSize*2*self.sceneRight.pixelSize))
					self.label_markerSizeNanoUnit.setText(self.sceneRight.pixelSizeUnit)
				except:
					if self.debug is True: print clrmsg.DEBUG + "Image pixel size is not a number:", self.label_imgpxsize.text()
					self.label_markerSizeNano.setText("NaN")
					self.label_markerSizeNanoUnit.setText('')
			else:
				self.label_markerSizeNano.setText('')
				self.label_markerSizeNanoUnit.setText('')

												##################### END #####################
												###### Image initialization and rotation ######
												###############################################

												###############################################
												######    Image processing functions     ######
												#################### START ####################
	## Read image
	def imread(self,path,normalize=True):
		'''
		return code in 5bit just for fun:
			1 = 2D
			2 = 3D (always normalized, +16)
			4 = greyscale
			8 = multicolor/multichannel
			16= normalized
		'''
		if self.debug is True: print clrmsg.DEBUG + "===== imread"
		img = tf.imread(path)
		if self.debug is True: print clrmsg.DEBUG + "Image shape/dtype:", img.shape, img.dtype
		## Displaying issues with uint16 images -> convert to uint8
		if img.dtype == 'uint16':
			img = img*(255.0/img.max())
			img = img.astype(dtype='uint8')
			if self.debug is True: print clrmsg.DEBUG + "Image dtype converted to:", img.shape, img.dtype
		if img.ndim == 4:
			if self.debug is True: print clrmsg.DEBUG + "Calculating multichannel MIP"
			## return mip, code 2+8+16 and imagestack
			return np.amax(img, axis=1), 26, img
		## this can only handle rgb. For more channels set "3" to whatever max number of channels should be handled
		elif img.ndim == 3 and any([True for dim in img.shape if dim <= 3]) or img.ndim == 2:
			if self.debug is True: print clrmsg.DEBUG + "Loading regular 2D image... multicolor/normalize:", \
				[True for x in [img.ndim] if img.ndim == 3],'/',[normalize]
			if normalize is True:
				## return normalized 2D image with code 1+4+16 for greyscale normalized 2D image and 1+8+16 for multicolor normalized 2D image
				return self.norm_img(img), 25 if img.ndim == 3 else 21, None
			else:
				## return 2D image with code 1+4 for greyscale 2D image and 1+8 for multicolor 2D image
				return img, 9 if img.ndim == 3 else 5, None
		elif img.ndim == 3:
			if self.debug is True: print clrmsg.DEBUG + "Calculating MIP"
			## return mip and code 2+4+16
			return np.amax(img, axis=0), 22, img

	def pxSize(self,img_path):
		with tf.TiffFile(img_path) as tif:
			for page in tif:
				for tag in page.tags.values():
					if isinstance(tag.value, str):
						for keyword in ['PhysicalSizeX','PixelWidth','PixelSize']:
							tagposs = [m.start() for m in re.finditer(keyword, tag.value)]
							for tagpos in tagposs:
								if keyword == 'PhysicalSizeX':
									for piece in tag.value[tagpos:tagpos+30].split('"'):
										try:
											pixelSize = float(piece)
											if self.debug is True: print clrmsg.DEBUG + "Pixel size from exif metakey:", keyword
											## Value is in um from Corrsight/LA tiff files
											return pixelSize
										except Exception as e:
											if self.debug is True: print clrmsg.DEBUG + "Pixel size parser:", e
											pass
								elif keyword == 'PixelWidth':
									for piece in tag.value[tagpos:tagpos+30].split('='):
										try:
											pixelSize = float(piece.strip().split('\r\n')[0])
											if self.debug is True: print clrmsg.DEBUG + "Pixel size from exif metakey:", keyword
											## *1E6 because these values from SEM/FIB image is in m
											return pixelSize*1E6
										except Exception as e:
											if self.debug is True: print clrmsg.DEBUG + "Pixel size parser:", e
											pass
								elif keyword == 'PixelSize':
									for piece in tag.value[tagpos:tagpos+30].split('"'):
										try:
											pixelSize = float(piece)
											if self.debug is True: print clrmsg.DEBUG + "Pixel size from exif metakey:", keyword
											## Value is in um from Corrsight/LA tiff files
											return pixelSize
										except Exception as e:
											if self.debug is True: print clrmsg.DEBUG + "Pixel size parser:", e
											pass

	## Convert opencv image (numpy array in BGR) to RGB QImage and return pixmap. Only takes 2D images
	def cv2Qimage(self,img):
		if self.debug is True: print clrmsg.DEBUG + "===== cv2Qimage"
		## Format 2D greyscale to RGB for QImage
		if img.ndim == 2:
			img = cv2.cvtColor(img,cv2.COLOR_GRAY2RGB)
		if img.shape[0] <= 3:
			if self.debug is True: print clrmsg.DEBUG + "Swaping image axes from c,y,x to y,x,c."
			img = img.swapaxes(0,2).swapaxes(0,1)
		if self.debug is True: print clrmsg.DEBUG + "Image shape:", img.shape
		image = QtGui.QImage(img.tobytes(), img.shape[1], img.shape[0], QtGui.QImage.Format_RGB888)  # .rgbSwapped()
		return QtGui.QPixmap.fromImage(image)
		# return QtGui.QPixmap('/Users/jan/Desktop/160202/LM-SEM.tif')

	## Adjust Brightness and Contrast by sliders
	def adjustBrightCont(self):
		if self.debug is True: print clrmsg.DEBUG + "===== adjustBrightCont"
		if self.label_selimg.text() == 'left':
			self.brightness_left = self.horizontalSlider_brightness.value()
			self.contrast_left = self.horizontalSlider_contrast.value()
			# print self.brightness_left,self.contrast_left
			## Remove image (item)
			self.sceneLeft.removeItem(self.pixmap_item_left)
			## Load replacement
			img_adj = np.copy(self.img_left)
			## Load contrast value (Slider value between 0 and 100)
			contr = self.contrast_left*0.1
			## Adjusting contrast
			img_adj = np.where(img_adj*contr >= 255,255,img_adj*contr)
			## Convert float64 back to uint8
			img_adj = img_adj.astype(dtype='uint8')
			## Adjust brightness
			if self.brightness_left > 0:
				img_adj = np.where(255-img_adj <= self.brightness_left,255,img_adj+self.brightness_left)
			else:
				img_adj = np.where(img_adj <= -self.brightness_left,0,img_adj+self.brightness_left)
				## Convert from int16 back to uint8
				img_adj = img_adj.astype(dtype='uint8')
			## Display image
			self.pixmap_left = self.cv2Qimage(img_adj)
			self.pixmap_item_left = QtGui.QGraphicsPixmapItem(self.pixmap_left, None, self.sceneLeft)
			## Put exchanged image into background
			QtGui.QGraphicsItem.stackBefore(self.pixmap_item_left, self.sceneLeft.items()[-1])
		elif self.label_selimg.text() == 'right':
			self.brightness_right = self.horizontalSlider_brightness.value()
			self.contrast_right = self.horizontalSlider_contrast.value()
			# print self.brightness_right,self.contrast_right
			## Remove image (item)
			self.sceneRight.removeItem(self.pixmap_item_right)
			## Load replacement
			img_adj = np.copy(self.img_right)
			## Load contrast value (Slider value between 0 and 100)
			contr = self.contrast_right*0.1
			## Adjusting contrast
			img_adj = np.where(img_adj*contr >= 255,255,img_adj*contr)
			## Convert float64 back to uint8
			img_adj = img_adj.astype(dtype='uint8')
			## Adjust brightness
			if self.brightness_right > 0:
				img_adj = np.where(255-img_adj <= self.brightness_right,255,img_adj+self.brightness_right)
			else:
				img_adj = np.where(img_adj <= -self.brightness_right,0,img_adj+self.brightness_right)
				## Convert from int16 back to uint8
				img_adj = img_adj.astype(dtype='uint8')
			## Display image
			self.pixmap_right = self.cv2Qimage(img_adj)
			self.pixmap_item_right = QtGui.QGraphicsPixmapItem(self.pixmap_right, None, self.sceneRight)
			## Put exchanged image into background
			QtGui.QGraphicsItem.stackBefore(self.pixmap_item_right, self.sceneRight.items()[-1])

	## Normalize Image
	def norm_img(self,img,copy=False):
		if self.debug is True: print clrmsg.DEBUG + "===== norm_img"
		if copy is True:
			img = np.copy(img)
		dtype = str(img.dtype)
		## Determine data type
		if dtype == "uint16" or dtype == "int16":
			typesize = 65535
		elif dtype == "uint8" or dtype == "int8":
			typesize = 255
		elif dtype == "float32" or dtype == "float64":
			typesize = 1
		else:
			print clrmsg.ERROR + "Sorry, I don't know this file type yet: ", dtype
		## 2D image
		if img.ndim == 2: img *= typesize/img.max()
		## 3D or multichannel image
		elif img.ndim == 3:
			## tiffimage reads z,y,x for stacks but y,x,c if it is multichannel image (or z,c,y,x if it is a multicolor image stack)
			if img.shape[-1] > 3:
				for i in range(int(img.shape[0])):
					img[i,:,:] *= typesize/img[i,:,:].max()
			else:
				for i in range(int(img.shape[2])):
					img[:,:,i] *= typesize/img[:,:,i].max()
		return img

	## function is now done via numpay axis max
	# ## Create Maximum Intensity Projection (MIP)
	# def mip(self,img):
	# 	if self.debug is True: print clrmsg.DEBUG + "===== mip"
	# 	if len(img.shape) == 4:
	# 		img_MIP = np.zeros((img.shape[0], img.shape[2],img.shape[3]), dtype=img.dtype)
	# 		for i in range(0,img.shape[0]):
	# 			for ii in range(0,img.shape[2]):
	# 				for iii in range(0,img.shape[3]):
	# 					img_MIP[i,ii,iii] = img[i,:,ii,iii].max()
	# 		if self.debug is True: print clrmsg.DEBUG + "Image shape original/MIP:", img.shape, img_MIP.shape
	# 		img_MIP = self.norm_img(img_MIP)
	# 		if self.debug is True: print clrmsg.DEBUG + "Image shape normalized MIP:", img_MIP.shape
	# 		return img_MIP
	# 	elif len(img.shape) == 3:
	# 		img_MIP = np.zeros((img.shape[1],img.shape[2]), dtype=img.dtype)
	# 		for i in range(0,img.shape[1]):
	# 			for ii in range(0,img.shape[2]):
	# 				img_MIP[i,ii] = img[:,i,ii].max()
	# 		if self.debug is True: print clrmsg.DEBUG + "Image shape original/MIP:", img.shape, img_MIP.shape
	# 		img_MIP = self.norm_img(img_MIP)
	# 		if self.debug is True: print clrmsg.DEBUG + "Image shape normalized MIP:", img_MIP.shape
	# 		return img_MIP
	# 	else:
	# 		print clrmsg.ERROR + "I'm sorry, I don't know this image shape: {0}".format(img.shape)

												##################### END #####################
												######    Image processing functions    #######
												###############################################

												###############################################
												######     CSV - Point import/export    ######
												#################### START ####################

	def autosave(self):
		csv_file_out = os.path.splitext(self.left)[0] + '_coordinates.txt'
		csv_handler.model2csv(self.modelLleft,csv_file_out,delimiter="\t")
		csv_file_out = os.path.splitext(self.right)[0] + '_coordinates.txt'
		csv_handler.model2csv(self.modelRight,csv_file_out,delimiter="\t")

	def exportPoints(self):
		if self.label_selectedTable.text() == 'left':
			model = self.modelLleft
		elif self.label_selectedTable.text() == 'right':
			model = self.modelRight
		## Export Dioalog. Needs check for extension or add default extension
		csv_file_out, filterdialog = QtGui.QFileDialog.getSaveFileNameAndFilter(
			self, 'Export file as', os.path.dirname(self.left) if self.label_selectedTable.text() == 'left' else os.path.dirname(self.right),
			"Tabstop sepperated (*.csv *.txt);;Comma sepperated (*.csv *.txt)")
		if str(filterdialog).startswith('Comma') is True:
			csv_handler.model2csv(model,csv_file_out,delimiter=",")
		elif str(filterdialog).startswith('Tabstop') is True:
			csv_handler.model2csv(model,csv_file_out,delimiter="\t")

	def importPoints(self):
		csv_file_in, filterdialog = QtGui.QFileDialog.getOpenFileNameAndFilter(
			self, 'Import file as', os.path.dirname(self.left) if self.label_selectedTable.text() == 'left' else os.path.dirname(self.right),
			"Tabstop sepperated (*.csv *.txt);;Comma sepperated (*.csv *.txt)")
		if str(filterdialog).startswith('Comma') is True:
			itemlist = csv_handler.csv2list(csv_file_in,delimiter=",",parent=self,sniff=True)
		elif str(filterdialog).startswith('Tabstop') is True:
			itemlist = csv_handler.csv2list(csv_file_in,delimiter="\t",parent=self,sniff=True)
		print len(itemlist[0])
		if self.label_selectedTable.text() == 'left':
			for item in itemlist: self.sceneLeft.addCircle(
				float(item[0]),
				float(item[1]),
				float(item[2]) if len(item) > 2 else 0)
			self.sceneLeft.itemsToModel()
			# csv_handler.csvAppend2model(csv_file_in,self.modelLleft,delimiter="\t",parent=self,sniff=True)
		elif self.label_selectedTable.text() == 'right':
			for item in itemlist: self.sceneRight.addCircle(
				float(item[0]),
				float(item[1]),
				float(item[2]) if len(item) > 2 else 0)
			self.sceneRight.itemsToModel()
			# csv_handler.csvAppend2model(csv_file_in,self.modelRight,delimiter="\t",parent=self,sniff=True)

												##################### END #####################
												######     CSV - Point import/export    #######
												###############################################


if __name__ == "__main__":
	print clrmsg.DEBUG + 'Debug Test'
	print clrmsg.OK + 'OK Test'
	print clrmsg.ERROR + 'Error Test'
	print clrmsg.INFO + 'Info Test'
	print clrmsg.WARNING + 'Warning Test'
	print '='*20, 'Initializing', '='*20
	app = QtGui.QApplication(sys.argv)
	## mac
	left = '/Volumes/Silver/Dropbox/Dokumente/Code/test_stuff/IB_030.tif'
	# left = '/Volumes/Silver/Dropbox/Dokumente/Code/test_stuff/IB_030_bw.tif'
	# left = '/Users/jan/Desktop/160202/LM-SEM.tif'
	# left = '/Volumes/Silver/output/MAX_input-0.tif'
	# left = '/Users/jan/Desktop/rofllol.tif'
	left = '/Volumes/Silver/output/input-0.tif'
	# left = '/Volumes/Silver/output/Composite.tif'
	# left = '/Users/jan/Desktop/LM-SEM.tif'
	# right = '/Volumes/Silver/Dropbox/Dokumente/Code/test_stuff/px_test.tif'
	right = '/Volumes/Silver/Dropbox/Dokumente/Code/test_stuff/Tile_001-001-000_0-000.tif'
	# right = '/Users/jan/Desktop/test/pxsize_test/pxsize_test_0_small.tif'
	## win
	# left = r'E:\Dropbox\Dokumente\Code\test_stuff\IB_030.tif'
	# right = r'E:\Dropbox\Dokumente\Code\test_stuff\px_test.tif'
	widget = MainWidget(left=left, right=right)
	widget.show()
	sys.exit(app.exec_())