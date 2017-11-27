#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Dynamic View Controller © Autolog 2016-2017
# Requires Indigo 7
#

import datetime

import errno
try:
    import indigo
except:
    pass

import logging
from operator import itemgetter
import os

import Queue

import subprocess
import sys

import threading
import time

from constants import *


class ThreadRefreshDynamicView(threading.Thread):

    def __init__(self, globals, devId, event):

        threading.Thread.__init__(self)

        self.globals = globals

        self.messageHandlingMonitorLogger = logging.getLogger("Plugin.MonitorRefresh")
        self.messageHandlingMonitorLogger.setLevel(self.globals['debug']['monitorRefresh'])

        self.messageHandlingDebugLogger = logging.getLogger("Plugin.DebugRefresh")
        self.messageHandlingDebugLogger.setLevel(self.globals['debug']['debugRefresh'])

        self.methodTracer = logging.getLogger("Plugin.method")  
        self.methodTracer.setLevel(self.globals['debug']['debugMethodTrace'])

        self.threadStop = event

        self.dynamicDevId = int(devId)  # Set Indigo Device id (for Dynamic View) to value passed in Thread invocation
        self.dynamicAddress = indigo.devices[self.dynamicDevId].address
        self.dynamicName = indigo.devices[self.dynamicDevId].name

        self.globals['threads']['refreshDynamicView'][self.dynamicDevId]['threadActive'] = True

        self.messageHandlingDebugLogger.debug(u"Initialising 'refreshDynamicView' Thread for %s [%s]" % (self.dynamicName, self.dynamicAddress))  
  
    def run(self):

        self.methodTracer.threaddebug(u"ThreadRefreshDynamicView")  

        time.sleep(2)  # Allow devices to start?

        try:

            self.messageHandlingDebugLogger.debug(u"Refresh Dynamic View Thread initialised for %s [%s]" % (self.dynamicName, self.dynamicAddress))  

            while not self.threadStop.is_set():
                try:

                    if self.globals['debug']['previousMonitorRefresh'] != self.globals['debug']['monitorRefresh']:
                        self.globals['debug']['previousMonitorRefresh'] = self.globals['debug']['monitorRefresh']
                        self.messageHandlingMonitorLogger.setLevel(self.globals['debug']['monitorRefresh'])

                    if self.globals['debug']['previousDebugRefresh'] != self.globals['debug']['debugRefresh']:
                        self.globals['debug']['previousDebugRefresh'] = self.globals['debug']['debugRefresh']
                        self.messageHandlingDebugLogger.setLevel(self.globals['debug']['debugRefresh'])

                    if self.globals['debug']['previousDebugMethodTrace'] !=self.globals['debug']['debugMethodTrace']:
                        self.globals['debug']['previousDebugMethodTrace'] = self.globals['debug']['debugMethodTrace']
                        self.methodTracer.setLevel(self.globals['debug']['debugMethodTrace'])

                    commandToHandle = self.globals['queues']['refreshDynamicView'][self.dynamicDevId].get(True,5)
                    if commandToHandle[0] == 'STOPTHREAD':
                        continue  # self.threadStop should be set

                    self.dynamicDev = indigo.devices[self.dynamicDevId]  # Get latest Version of Dynamic Device

                    command = commandToHandle[0]
                    commandParams = commandToHandle[1]

                    processCommandMethod = 'process' + command[0:1].upper() + command[1:]
                    self.messageHandlingDebugLogger.debug(u"processCommand = %s" % (processCommandMethod))
                    try:                    
                        processCommandMethodMethod = getattr(self, processCommandMethod)

                        processCommandMethodMethod(commandParams)
                    except StandardError, e:
                        self.messageHandlingDebugLogger.error(u"Process Command Method detected error. Line '%s' has error='%s'" % (sys.exc_traceback.tb_lineno, e)) 
                except Queue.Empty:
                    pass

        except StandardError, e:
            self.messageHandlingDebugLogger.error(u"Handle Command Thread  detected error. Line '%s' has error='%s'" % (sys.exc_traceback.tb_lineno, e))   

            self.globals['dynamics'][self.dynamicDevId]['keepThreadAlive'] = False

            self.messageHandlingDebugLogger.debug(u"Handle Command Thread ended for %s [%s]" % (self.dynamicName, self.dynamicAddress))

        self.messageHandlingDebugLogger.debug(u"Refresh Dynamic View thread ended for Dynamic View: %s [%s]" % (self.dynamicName, self.dynamicAddress))  

        self.globals['threads']['handleResponse'][self.dynamicDevId]['threadActive'] = False

    def processInitialiseDynamicState(self, paramsNotUsedInThisMethod):

        try:
            if not self.processUpdateDynamicState(paramsNotUsedInThisMethod):
                self.messageHandlingDebugLogger.error(u"Unable to initialise Dynamic State for '%s'" % self.dynamicDev.name)
                return

            parameters = {'type':'file', 'mode': 'none', 'number': 0}
            self.processSkip(parameters)
                
        except StandardError, e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.messageHandlingDebugLogger.error(u"initialiseDynamicState: StandardError detected for '%s' at line '%s' = %s" % (self.dynamicDev.name, exc_tb.tb_lineno,  e))
 
    def processUpdateDynamicState(self, paramsNotUsedInThisMethod):

        if self.globals['dynamics'][self.dynamicDevId]['processMode'] == kProcessModeFoscamHD:
            return(self.processUpdateDynamicStateFoscamHD(paramsNotUsedInThisMethod))
        elif self.globals['dynamics'][self.dynamicDevId]['processMode'] == kProcessModeModifiedFileDateOrder:
            return(self.processUpdateDynamicStateModifiedFileDateOrder(paramsNotUsedInThisMethod))
        else:
            return(self.processUpdateDynamicStateFolderNameOrder(paramsNotUsedInThisMethod))

    def processUpdateDynamicStateFoscamHD(self, paramsNotUsedInThisMethod):
        try:
            folderRoot = self.globals['dynamics'][self.dynamicDevId]['rootFolder']
            if folderRoot == 'unknown':
                self.messageHandlingDebugLogger.error(u"Folder root not specified in Device Configuration for '%s'" % self.dynamicDev.name)
                return False

            # Save the currently selected: Day, Half-hour and filename
            previousSelectedFilepath = self.dynamicDev.states["selectedFilepath"]  # full file path e.g '/Users/<USER>/Documents/CAMERA/<MODEL>_<MAC-ADDRESS>/20160904/20160904-150000
            previousSelectedFilename = self.dynamicDev.states["selectedFilename"]  # full file name e.g MDAlarm_20160905-170912.jpg
            previousSelectedfileName = previousSelectedFilename[8:23]  # short key file name e.g 20160905-170912
            previousSelectedDate = self.dynamicDev.states["selectedDate"]  # e.g. 20160907
            previousSelectedHalfHour = self.dynamicDev.states["selectedHalfHour"]  # e.g. 201609071430

            # Used to derive the updated indexes into the lists of an existing selected file (typically in a Control Page)
            selectedfileNameNewIndex = -1
            selectedDateNewIndex = -1
            selectedHalfHourNewIndex = -1

            dirPathList = []
            dirPathListIndex = -1

            # lists of paths, lists of files, lists of file path index, change of path, change of date file index, change of half hour file index
            fileNameList = []  # e.g. ['20160907145723', '20160907150719', '20160907164503']
            fileNameListIndex = -1
            fileDirPathList = []
            fileModifiedDateList = []

            dateList = []  # e.g. ['20160904', '20160905', '20160906', '20160907']
            dateListIndexIntofileNameList = []  # Index into 'fileNameList' e.g. [0, 4, 56, 89]
            dateListIndex = -1

            halfHourList = []  # e.g. ['201609040930', '201609041000', '201609051530', '201609061330', '201609061400', '201609061430', '201609070730', '201609071930', '201609072000']        
            halfHourListIndexIntofileNameList = []  # Index into 'fileNameList' e.g. [0, 2, 4, 56, 64, 73, 89, 95, 121]        
            halfHourListIndex = -1

            # Initialise for loop checks
            forLoopPreviousDirPath = ''
            forLoopPreviousDate = '20000101'  # i.e. format 'YYYYMMDD'
            forLoopPreviousHalfHour = '200001010000'  # i.e. format 'YYYYMMDDHHMM'

            for dirPath, subdirList, fileList in sorted(os.walk(folderRoot)):
                for filename in fileList:
                    if forLoopPreviousDirPath != dirPath:
                        forLoopPreviousDirPath = dirPath
                        dirPathList.append(dirPath)
                        dirPathListIndex = len(dirPathList) - 1

                    fullFileName = os.path.join(dirPath, filename)

                    if filename[0:8] != "MDAlarm_":  # Only process snapshot images if in foscamHD mode
                        continue  # loop back toprocess next file

                    # work out key components of filename
                    fname = filename[8:23]  # e.g. 20160907-143718
                    fnameDate = filename[8:16]  # e.g. 20160907
                    fnameTime = filename[17:23]  # e.g. 143718
                    fnameHour = filename[17:19]  # e.g. 14
                    fnameMinute = filename[19:21]  # e.g. 37
                    # derive half-hour
                    fnameDerivedBaseHalfHour = '00' if fnameMinute < '30' else '30'
                    fnameHalfHour = fnameDate + fnameHour + fnameDerivedBaseHalfHour  # e.g. 201609071430
                    # At this point we have worked out all the key components for 'kProcessModeFoscamHD'

                    # save the filename key into the list - key is made up of date & time (YYYYMMDDHHMMSS)
                    fileNameList.append(fname)  # e.g. 20160907-143718
                    fileNameListIndex = len(fileNameList) - 1

                    if fnameHalfHour != forLoopPreviousHalfHour:  # Handle change of half-hour
                        forLoopPreviousHalfHour = fnameHalfHour
                        halfHourList.append(fnameHalfHour)  # Save the new Half hour e.g. '201609081930'
                        halfHourListIndexIntofileNameList.append(fileNameListIndex)  # Save
                        halfHourListIndex = len(halfHourList) - 1

                    if fnameDate != forLoopPreviousDate:  # handle change of date
                        forLoopPreviousDate = fnameDate
                        dateList.append(fnameDate)
                        dateListIndexIntofileNameList.append(fileNameListIndex)
                        dateListIndex  = len(dateList) - 1

                    # Now update previous displayed file & file indexes 
                    if fname == previousSelectedfileName:
                        selectedfileNameNewIndex = fileNameListIndex
                    if fnameHalfHour == previousSelectedHalfHour:
                        selectedHalfHourNewIndex = halfHourListIndex
                    if fnameDate == previousSelectedDate:
                        selectedDateNewIndex = dateListIndex

            if fileNameListIndex != -1:
                if selectedfileNameNewIndex == -1:  # Not set
                    selectedfileNameNewIndex = fileNameListIndex  # Set to latest
                if selectedHalfHourNewIndex == -1:  # Not set
                    selectedHalfHourNewIndex = halfHourListIndex  # Set to latest
                if selectedDateNewIndex == -1:  # Not set
                    selectedDateNewIndex = dateListIndex  # Set to latest

                self.globals['dynamics'][self.dynamicDevId]['fullFileName'] = fullFileName

                self.globals['dynamics'][self.dynamicDevId]['filename'] = 'MDAlarm_' + fileNameList[selectedfileNameNewIndex] + '.jpg'

                self.globals['dynamics'][self.dynamicDevId]['fileNameList'] = fileNameList
                self.globals['dynamics'][self.dynamicDevId]['fileNameListIndex'] = selectedfileNameNewIndex
                self.globals['dynamics'][self.dynamicDevId]['fileNameListIndexMax'] = len(self.globals['dynamics'][self.dynamicDevId]['fileNameList']) - 1

                self.globals['dynamics'][self.dynamicDevId]['dateList'] = dateList
                self.globals['dynamics'][self.dynamicDevId]['dateListIndexIntofileNameList'] = dateListIndexIntofileNameList
                self.globals['dynamics'][self.dynamicDevId]['dateListIndex'] = selectedDateNewIndex
                self.globals['dynamics'][self.dynamicDevId]['dateListIndexMax'] = len(self.globals['dynamics'][self.dynamicDevId]['dateListIndexIntofileNameList']) - 1

                self.globals['dynamics'][self.dynamicDevId]['halfHourList'] = halfHourList
                self.globals['dynamics'][self.dynamicDevId]['halfHourListIndexIntofileNameList'] = halfHourListIndexIntofileNameList
                self.globals['dynamics'][self.dynamicDevId]['halfHourListIndex'] = selectedHalfHourNewIndex
                self.globals['dynamics'][self.dynamicDevId]['halfHourListIndexMax'] = len(self.globals['dynamics'][self.dynamicDevId]['halfHourList']) - 1

                self.globals['dynamics'][self.dynamicDevId]['latestFilename'] = filename
                self.globals['dynamics'][self.dynamicDevId]['latestFullFilename'] = fullFileName
                self.globals['dynamics'][self.dynamicDevId]['latestFileDateTimeUI'] = '18-Oct-2016, 12:29:25'

                parameters = {'type':'file', 'mode': 'none', 'number': 0}
                self.processSkip(parameters)

                # DEBUG DEBUG DEBUG DEBUG DEBUG DEBUG DEBUG DEBUG DEBUG DEBUG DEBUG DEBUG DEBUG DEBUG DEBUG DEBUG DEBUG DEBUG DEBUG DEBUG DEBUG DEBUG DEBUG DEBUG DEBUG DEBUG 
                for halfHour in halfHourListIndexIntofileNameList:
                    self.messageHandlingDebugLogger.debug(u"Half-hour: %s" % (fileNameList[halfHour]))
                return True  

        except StandardError, e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.messageHandlingDebugLogger.error(u"updateDynamicStateFoscamHD: StandardError detected for '%s' at line '%s' = %s" % (self.dynamicDev.name, exc_tb.tb_lineno,  e))

        return False  # An error occurred or no folder to display


    def processUpdateDynamicStateModifiedFileDateOrder(self, paramsNotUsedInThisMethod):
        try:
            folderRoot = self.globals['dynamics'][self.dynamicDevId]['rootFolder']
            if folderRoot == 'unknown':
                return False

            # Save the currently selected: Day, Half-hour and filename
            previousSelectedFilepath = self.dynamicDev.states["selectedFilepath"]  # full file path e.g '/Users/<USER>/Documents/CAMERA/<MODEL>_<MAC-ADDRESS>/20160904/20160904-150000
            previousSelectedFilename = self.dynamicDev.states["selectedFilename"]  # full file name e.g MDAlarm_20160905-170912.jpg
            previousSelectedfileName = previousSelectedFilename[8:23]  # short key file name e.g 20160905-170912
            previousSelectedDate = self.dynamicDev.states["selectedDate"]  # e.g. 20160907
            previousSelectedHalfHour = self.dynamicDev.states["selectedHalfHour"]  # e.g. 201609071430

            # Used to derive the updated indexes into the lists of an existing selected file (typically in a Control Page)
            selectedfileNameNewIndex = -1
            selectedDateNewIndex = -1
            selectedHalfHourNewIndex = -1

            dirPathList = []
            dirPathListIndex = -1

            # lists of paths, lists of files, lists of file path index, change of path, change of date file index, change of half hour file index
            fileNameList = []  # e.g. ['20160907145723', '20160907150719', '20160907164503']
            fileNameListIndex = -1
            fileDirPathList = []
            fileModifiedDateList = []

            dateList = []  # e.g. ['20160904', '20160905', '20160906', '20160907']
            dateListIndexIntofileNameList = []  # Index into 'fileNameList' e.g. [0, 4, 56, 89]
            dateListIndex = -1

            halfHourList = []  # e.g. ['201609040930', '201609041000', '201609051530', '201609061330', '201609061400', '201609061430', '201609070730', '201609071930', '201609072000']        
            halfHourListIndexIntofileNameList = []  # Index into 'fileNameList' e.g. [0, 2, 4, 56, 64, 73, 89, 95, 121]        
            halfHourListIndex = -1

            for dirPath, subdirList, fileList in os.walk(folderRoot):
                for filename in fileList:
                    fullFileName = os.path.join(dirPath, filename)
                    t = os.path.getmtime(fullFileName)
                    tt = time.localtime(t)
                    lastModifiedDateTime = time.strftime('%Y%m%d-%H%M%S', tt)
                    fileNameList.append([lastModifiedDateTime, fullFileName])

            fileNameList.sort(key=itemgetter(0))  # Sort filename list into modified date order

            # Initialise for loop checks
            forLoopPreviousDirPath = ''
            forLoopPreviousDate = '20000101'  # i.e. format 'YYYYMMDD'
            forLoopPreviousHalfHour = '200001010000'  # i.e. format 'YYYYMMDDHHMM'

            for fileNameListIndex, fileInfo in enumerate(fileNameList):
                    lastModifiedDateTime, fullFileName = fileInfo

                    fnameDate = lastModifiedDateTime[0:8]  # e.g. 20160907
                    fnameTime = lastModifiedDateTime[9:15]  # e.g. 143718
                    fnameHour = lastModifiedDateTime[9:11]  # e.g. 14
                    fnameMinute = lastModifiedDateTime[11:13]  # e.g. 37
                    # derive half-hour
                    fnameDerivedBaseHalfHour = '00' if fnameMinute < '30' else '30'
                    fnameHalfHour = fnameDate + fnameHour + fnameDerivedBaseHalfHour  # e.g. '201609071430'
                    # At this point we have worked out all the key components for 'kProcessModeModifiedFileDateOrder'

                    if fnameHalfHour != forLoopPreviousHalfHour:  # Handle change of half-hour
                        forLoopPreviousHalfHour = fnameHalfHour
                        halfHourList.append(fnameHalfHour)  # Save the new Half hour e.g. '201609081930'
                        halfHourListIndexIntofileNameList.append(fileNameListIndex)  # Save
                        halfHourListIndex = len(halfHourList) - 1

                    if fnameDate != forLoopPreviousDate:  # handle change of date
                        forLoopPreviousDate = fnameDate
                        dateList.append(fnameDate)
                        dateListIndexIntofileNameList.append(fileNameListIndex)
                        dateListIndex  = len(dateList) - 1

                    # Now update previous displayed file & file indexes 
                    if fullFileName == previousSelectedfileName:
                        selectedfileNameNewIndex = fileNameListIndex
                    if fnameHalfHour == previousSelectedHalfHour:
                        selectedHalfHourNewIndex = halfHourListIndex
                    if fnameDate == previousSelectedDate:
                        selectedDateNewIndex = dateListIndex

            if fileNameListIndex != -1:

                if selectedfileNameNewIndex == -1:  # Not set
                    selectedfileNameNewIndex = fileNameListIndex  # Set to latest
                if selectedHalfHourNewIndex == -1:  # Not set
                    selectedHalfHourNewIndex = halfHourListIndex  # Set to latest
                if selectedDateNewIndex == -1:  # Not set
                    selectedDateNewIndex = dateListIndex  # Set to latest

                self.globals['dynamics'][self.dynamicDevId]['fullFileName'] = fileNameList[selectedfileNameNewIndex][1]

                head, tail = os.path.split(self.globals['dynamics'][self.dynamicDevId]['fullFileName'])
                self.globals['dynamics'][self.dynamicDevId]['filename'] = tail

                self.globals['dynamics'][self.dynamicDevId]['fileNameList'] = fileNameList
                self.globals['dynamics'][self.dynamicDevId]['fileNameListIndex'] = selectedfileNameNewIndex
                self.globals['dynamics'][self.dynamicDevId]['fileNameListIndexMax'] = len(self.globals['dynamics'][self.dynamicDevId]['fileNameList']) - 1

                self.globals['dynamics'][self.dynamicDevId]['dateList'] = dateList
                self.globals['dynamics'][self.dynamicDevId]['dateListIndexIntofileNameList'] = dateListIndexIntofileNameList
                self.globals['dynamics'][self.dynamicDevId]['dateListIndex'] = selectedDateNewIndex
                self.globals['dynamics'][self.dynamicDevId]['dateListIndexMax'] = len(self.globals['dynamics'][self.dynamicDevId]['dateListIndexIntofileNameList']) - 1

                self.globals['dynamics'][self.dynamicDevId]['halfHourList'] = halfHourList
                self.globals['dynamics'][self.dynamicDevId]['halfHourListIndexIntofileNameList'] = halfHourListIndexIntofileNameList
                self.globals['dynamics'][self.dynamicDevId]['halfHourListIndex'] = selectedHalfHourNewIndex
                self.globals['dynamics'][self.dynamicDevId]['halfHourListIndexMax'] = len(self.globals['dynamics'][self.dynamicDevId]['halfHourList']) - 1

                parameters = {'type':'file', 'mode': 'none', 'number': 0}
                self.processSkip(parameters)

                for halfHour in halfHourListIndexIntofileNameList:
                    self.messageHandlingDebugLogger.debug(u"Half-hour: %s" % (fileNameList[halfHour]))
                return True  

        except StandardError, e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.messageHandlingDebugLogger.error(u"updateDynamicStateOther: StandardError detected for '%s' at line '%s' = %s" % (self.dynamicDev.name, exc_tb.tb_lineno,  e))

        return False  # An error occurred or no folder to display

    def processUpdateDynamicStateFolderNameOrder(self, paramsNotUsedInThisMethod):

        # FUTURE DEVELOPMENT

        return False

    def processSkip(self, parameters):

        try:
            if 'StatusTimer' in self.globals['dynamics'][self.dynamicDevId]:
                self.globals['dynamics'][self.dynamicDevId]['StatusTimer'].cancel()
                del self.globals['dynamics'][self.dynamicDevId]['StatusTimer']

            skipType = parameters['type']  # 'day', 'time', 'file'
            skipMode = parameters['mode']  # 'back', 'forward'
            skipNumber =  int(parameters['number'])  # Number to skip

            if len(self.globals['dynamics'][self.dynamicDevId]['fileNameList']) == 0:
                # No files in list so select defualt image
                symLinkFile = self.globals['dynamics'][self.dynamicDevId]['symlinkFile']
                defaultFile = self.globals['dynamics'][self.dynamicDevId]['defaultFile']
                process = subprocess.Popen(['unlink', symLinkFile], stdout=subprocess.PIPE)
                process = subprocess.Popen(['ln', '-s', defaultFile, symLinkFile], stdout=subprocess.PIPE)

            if skipType == 'file':  # File(s) at a time
                atLimit = False
                if skipMode == 'forward':
                    testValue = self.globals['dynamics'][self.dynamicDevId]['fileNameListIndex'] + skipNumber
                    if testValue < self.globals['dynamics'][self.dynamicDevId]['fileNameListIndexMax']:
                        self.globals['dynamics'][self.dynamicDevId]['fileNameListIndex'] += skipNumber
                    else:
                        atLimit = True
                        self.globals['dynamics'][self.dynamicDevId]['fileNameListIndex'] = self.globals['dynamics'][self.dynamicDevId]['fileNameListIndexMax']
                elif skipMode == 'back': 
                    testValue = self.globals['dynamics'][self.dynamicDevId]['fileNameListIndex'] - skipNumber
                    if testValue > 0:
                        self.globals['dynamics'][self.dynamicDevId]['fileNameListIndex'] -= skipNumber
                    else:
                        atLimit = True
                        self.globals['dynamics'][self.dynamicDevId]['fileNameListIndex'] = 0
                elif skipMode == 'none':
                    pass  # Leave as is
                else:  # skipMode == 'latest':
                    self.globals['dynamics'][self.dynamicDevId]['fileNameListIndex'] = self.globals['dynamics'][self.dynamicDevId]['fileNameListIndexMax'] 

            elif skipType == 'time':  # Half-hour(s) at a time
                atLimit = False
                if skipMode == 'forward':
                    testValue = self.globals['dynamics'][self.dynamicDevId]['halfHourListIndex'] + skipNumber
                    if testValue < (len(self.globals['dynamics'][self.dynamicDevId]['halfHourListIndexIntofileNameList']) -1):
                        self.globals['dynamics'][self.dynamicDevId]['halfHourListIndex'] += skipNumber
                    else:
                        atLimit = True
                        self.globals['dynamics'][self.dynamicDevId]['fileNameListIndex'] = self.globals['dynamics'][self.dynamicDevId]['fileNameListIndexMax']
                elif skipMode == 'back':
                    testValue = self.globals['dynamics'][self.dynamicDevId]['halfHourListIndex'] - skipNumber
                    if testValue > 0:
                        self.globals['dynamics'][self.dynamicDevId]['halfHourListIndex'] -= skipNumber
                    else:
                        atLimit = True
                        self.globals['dynamics'][self.dynamicDevId]['fileNameListIndex'] = 0
                if not atLimit:
                    self.globals['dynamics'][self.dynamicDevId]['fileNameListIndex'] = self.globals['dynamics'][self.dynamicDevId]['halfHourListIndexIntofileNameList'][self.globals['dynamics'][self.dynamicDevId]['halfHourListIndex']]

            elif skipType == 'day':  # Day(s) at a time
                atLimit = False

                if skipMode == 'forward':
                    testValue = self.globals['dynamics'][self.dynamicDevId]['dateListIndex'] + skipNumber
                    if testValue < (len(self.globals['dynamics'][self.dynamicDevId]['dateListIndexIntofileNameList']) -1):
                        self.globals['dynamics'][self.dynamicDevId]['dateListIndex'] += skipNumber
                    else:
                        atLimit = True
                        self.globals['dynamics'][self.dynamicDevId]['fileNameListIndex'] = self.globals['dynamics'][self.dynamicDevId]['fileNameListIndexMax']
                elif skipMode == 'back':
                    testValue = self.globals['dynamics'][self.dynamicDevId]['dateListIndex'] - skipNumber
                    if testValue > 0:
                        self.globals['dynamics'][self.dynamicDevId]['dateListIndex'] -= skipNumber
                    else:
                        atLimit = True
                        self.globals['dynamics'][self.dynamicDevId]['fileNameListIndex'] = 0
                if not atLimit:
                    self.globals['dynamics'][self.dynamicDevId]['fileNameListIndex'] = self.globals['dynamics'][self.dynamicDevId]['dateListIndexIntofileNameList'][self.globals['dynamics'][self.dynamicDevId]['dateListIndex']]

            derivedData = self.deriveData(self.globals['dynamics'][self.dynamicDevId]['fileNameListIndex'])
            derivedFullFileName = derivedData[0]  # e.g. '/Users/<USER>/Documents/CAMERA/<MODEL>_<MAC-ADDRESS>/20160911/20160911-090000/MDAlarm_20160911-092647.jpg'
            derivedFileName = derivedData[1]  # e.g. 'MDAlarm_20160911-092647.jpg'
            derivedDate = derivedData[2]  # e.g. '20160912'
            derivedHalfHour = derivedData[3]  # e.g. '201609110930'
            derivedNumber = derivedData[4]  # e.g '173'
            derivedDateUI = derivedData[5]
            derivedHalfHourUI = derivedData[6]
            derivedFileDateTimeUI = derivedData[7]

            self.globals['dynamics'][self.dynamicDevId]['halfHourListIndex'] = self.globals['dynamics'][self.dynamicDevId]['halfHourList'].index(derivedHalfHour)
            self.globals['dynamics'][self.dynamicDevId]['dateListIndex'] = self.globals['dynamics'][self.dynamicDevId]['dateList'].index(derivedDate)

            latestData = self.deriveData(self.globals['dynamics'][self.dynamicDevId]['fileNameListIndexMax'])
            latestFullFilename = latestData[0]  # e.g. '/Users/<USER>/Documents/CAMERA/<MODEL>_<MAC-ADDRESS>/20160911/20160911-090000/MDAlarm_20160911-092647.jpg'
            latestFileName = latestData[1]  # e.g. 'MDAlarm_20160911-092647.jpg'
            #latestDate = latestData[2]  # e.g. '20160912'
            #latestHalfHour = latestData[3]  # e.g. '201609110930'
            #latestNumber = latestData[4]  # e.g '173'
            #latestDateUI = latestData[5]
            #latestHalfHourUI = latestData[6]
            latestFileDateTimeUI = latestData[7]



            latestMaximum = str(self.globals['dynamics'][self.dynamicDevId]['fileNameListIndexMax'] + 1)

            derivedNumberUI = str(derivedNumber) + ' of ' + str(latestMaximum)

            keyValueList = []

            keyValue = {}
            keyValue['key'] = 'latestFilename'
            #keyValue['value'] = self.globals['dynamics'][self.dynamicDevId]['latestFilename']
            keyValue['value'] = latestFileName
            keyValueList.append(keyValue)

            keyValue = {}
            keyValue['key'] = 'latestFullFilename'
            #keyValue['value'] = self.globals['dynamics'][self.dynamicDevId]['latestFilename']
            keyValue['value'] = latestFullFilename
            keyValueList.append(keyValue)

            keyValue = {}
            keyValue['key'] = 'latestFileDateTimeUI'
            #keyValue['value'] = self.globals['dynamics'][self.dynamicDevId]['latestFileDateTimeUI']
            keyValue['value'] = latestFileDateTimeUI
            keyValueList.append(keyValue)

            keyValue = {}
            keyValue['key'] = 'selectedFilename'
            keyValue['value'] = derivedFileName
            keyValueList.append(keyValue)

            keyValue = {}
            keyValue['key'] = 'selectedDate'
            keyValue['value'] = derivedDate
            keyValueList.append(keyValue)

            keyValue = {}
            keyValue['key'] = 'selectedHalfHour'
            keyValue['value'] = derivedHalfHour
            keyValueList.append(keyValue)

            keyValue = {}
            keyValue['key'] = 'selectedNumber'
            keyValue['value'] = derivedNumber
            keyValueList.append(keyValue)

            keyValue = {}
            keyValue['key'] = 'latestMaximum'
            keyValue['value'] = latestMaximum
            keyValueList.append(keyValue)

            keyValue = {}
            keyValue['key'] = 'selectedFileDateTimeUI'
            keyValue['value'] = derivedFileDateTimeUI
            keyValueList.append(keyValue)

            keyValue = {}
            keyValue['key'] = 'selectedDateUI'
            keyValue['value'] = derivedDateUI
            keyValueList.append(keyValue)

            keyValue = {}
            keyValue['key'] = 'selectedHalfHourUI'
            keyValue['value'] = derivedHalfHourUI
            keyValueList.append(keyValue)

            keyValue = {}
            keyValue['key'] = 'selectedNumberUI'
            keyValue['value'] = derivedNumberUI
            keyValueList.append(keyValue)

            keyValue = {}
            keyValue['key'] = 'status'
            keyValue['value'] = '... refreshing'
            keyValueList.append(keyValue)

            self.globals['dynamics'][self.dynamicDevId]['refreshCount'] += 1
            keyValue = {}
            keyValue['key'] = 'refreshCount'
            keyValue['value'] = str(self.globals['dynamics'][self.dynamicDevId]['refreshCount'])
            keyValueList.append(keyValue)

            self.dynamicDev.updateStatesOnServer(keyValueList)
            self.dynamicDev.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)

            timerSeconds = 3.0
            self.globals['dynamics'][self.dynamicDevId]['StatusTimer'] = threading.Timer(timerSeconds, self.updateStatusTimer, ['StatusTimer', self.dynamicDevId])
            self.globals['dynamics'][self.dynamicDevId]['StatusTimer'].start()


            selectedFile = self.globals['dynamics'][self.dynamicDevId]['rootFolder'] + '/' + derivedDate + '/' + derivedHalfHour[0:8] + '-' + derivedHalfHour[8:12] + '00/' + derivedFileName

            symLinkFile = self.globals['dynamics'][self.dynamicDevId]['symlinkFile']
            if symLinkFile != 'unknown':
                process = subprocess.Popen(['unlink', symLinkFile], stdout=subprocess.PIPE)
                process = subprocess.Popen(['ln', '-s', derivedFullFileName, symLinkFile], stdout=subprocess.PIPE)

            symlinkLatestFile = self.globals['dynamics'][self.dynamicDevId]['symlinkLatestFile']
            if symLinkFile != 'unknown':
                process = subprocess.Popen(['unlink', symlinkLatestFile], stdout=subprocess.PIPE)
                process = subprocess.Popen(['ln', '-s', latestFullFilename, symlinkLatestFile], stdout=subprocess.PIPE)

    
        except StandardError, e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.messageHandlingDebugLogger.error(u"initialiseDynamicState: StandardError detected for '%s' at line '%s' = %s" % (self.dynamicDev.name, exc_tb.tb_lineno,  e))

    def updateStatusTimer(self, timerId, devId):
        try:
            keyValueList = []

            keyValue = {}
            keyValue['key'] = 'status'
            keyValue['value'] = 'waiting ...'
            keyValueList.append(keyValue)

            indigo.devices[devId].updateStatesOnServer(keyValueList)  # Just in case I want to update more fields ;-)

            indigo.devices[devId].updateStateImageOnServer(indigo.kStateImageSel.TimerOff)

        except StandardError, e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.messageHandlingDebugLogger.error(u"updateStatusTimer: StandardError detected for '%s' at line '%s' = %s" % (indigo.devices[devId].name, exc_tb.tb_lineno,  e))


    def deriveData(self, paramfileIndexEntry):

        try:
            # Derive correct HalfHour and Date from file name

            if self.globals['dynamics'][self.dynamicDevId]['processMode'] == kProcessModeFoscamHD:
                dynamicfileName = self.globals['dynamics'][self.dynamicDevId]['fileNameList'][paramfileIndexEntry]
                derivedFileName = 'MDAlarm_' + dynamicfileName + '.jpg'

                derivedDateIndexEntry = self.globals['dynamics'][self.dynamicDevId]['dateList'].index(dynamicfileName[0:8])
                derivedDate = self.globals['dynamics'][self.dynamicDevId]['dateList'][derivedDateIndexEntry]
                derivedHour = dynamicfileName[9:11]  # e.g. 14
                derivedMinute = dynamicfileName[11:13]  # e.g. 37
                # derive half-hour
                derivedDerivedBaseHalfHour = '00' if derivedMinute < '30' else '30'
                derivedHalfHour = derivedDate + derivedHour + derivedDerivedBaseHalfHour  # e.g. 201609071430
                derivedHalfHourIndexEntry = self.globals['dynamics'][self.dynamicDevId]['halfHourList'].index(derivedHalfHour)
                derivedHalfHour = self.globals['dynamics'][self.dynamicDevId]['halfHourList'][derivedHalfHourIndexEntry]
                
                derivedNumber = str(paramfileIndexEntry + 1)
                
                derivedFullFileName = self.globals['dynamics'][self.dynamicDevId]['rootFolder'] + '/' + derivedDate + '/' + derivedHalfHour[0:8] + '-' + derivedHalfHour[8:12] + '00/' + derivedFileName

                derivedDateUI = str(derivedDate[6:8]) + '-' + str(kMonths[int(derivedDate[4:6]) -1]) + '-' + str(derivedDate[0:4])
                derivedHalfHourUI = str(derivedHalfHour[8:10]) + ':' + str(derivedHalfHour[10:12])
                derivedFileDateTimeUI = str(derivedDateUI) + ', ' + str(derivedFileName[-10:-8]) + ':' + str(derivedFileName[-8:-6]) + ':' + str(derivedFileName[-6:-4])

                return [derivedFullFileName, derivedFileName, derivedDate, derivedHalfHour, derivedNumber, derivedDateUI,  derivedHalfHourUI, derivedFileDateTimeUI]

            elif self.globals['dynamics'][self.dynamicDevId]['processMode'] == kProcessModeModifiedFileDateOrder:

                derivedFullFileName = self.globals['dynamics'][self.dynamicDevId]['fileNameList'][paramfileIndexEntry][1]
                path, derivedFileName = os.path.split(derivedFullFileName)
                lastModifiedDateTime = self.globals['dynamics'][self.dynamicDevId]['fileNameList'][paramfileIndexEntry][0]

 
                derivedDate = lastModifiedDateTime[0:8]
                derivedHour = lastModifiedDateTime[9:11]
                derivedMinute = lastModifiedDateTime[11:13]
                derivedSecond = lastModifiedDateTime[13:15] 
                # derive half-hour
                derivedBaseHalfHour = '00' if derivedMinute < '30' else '30'
                derivedHalfHour = derivedDate + derivedHour + derivedBaseHalfHour  # e.g. 201609071430
                derivedHalfHourIndexEntry = self.globals['dynamics'][self.dynamicDevId]['halfHourList'].index(derivedHalfHour)
                derivedHalfHour = self.globals['dynamics'][self.dynamicDevId]['halfHourList'][derivedHalfHourIndexEntry]
                
                derivedNumber = str(paramfileIndexEntry + 1)

                derivedDateUI = str(lastModifiedDateTime[6:8]) + '-' + str(kMonths[int(lastModifiedDateTime[4:6]) -1]) + '-' + str(lastModifiedDateTime[0:4])
                derivedHalfHourUI = str(derivedHalfHour[8:10]) + ':' + str(derivedHalfHour[10:12])
                derivedFileDateTimeUI = str(derivedDateUI) + ', ' + str(derivedHour) + ':' + str(derivedMinute) + ':' + str(derivedSecond)

                return [derivedFullFileName, derivedFileName, derivedDate, derivedHalfHour, derivedNumber,  derivedDateUI,  derivedHalfHourUI, derivedFileDateTimeUI]
            else:
                # Assume 'kProcessModeFolderNameOrder'  FUTURE EXTENSION ?
                pass
                self.messageHandlingDebugLogger.error(u"deriveData: Invalid Proces Mode '%s' for '%s'" % (self.globals['dynamics'][self.dynamicDevId]['processMode'], self.dynamicDev.name))

        except StandardError, e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.messageHandlingDebugLogger.error(u"deriveData: StandardError detected for '%s' at line '%s' = %s" % (self.dynamicDev.name, exc_tb.tb_lineno,  e))