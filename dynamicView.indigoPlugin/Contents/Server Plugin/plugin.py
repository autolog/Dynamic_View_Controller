#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Dynamic View Controller © Autolog 2016-2017
# Requires Indigo 7
#

try:
    import indigo
except:
    pass

import inspect
import logging
import os

import plistlib

import Queue

import sys

import threading
from time import time

from constants import *
from refreshDynamicView import ThreadRefreshDynamicView


class Plugin(indigo.PluginBase):

    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

        # Initialise dictionary to store plugin Globals
        self.globals = {}

        # Initialise dictionary for debug in plugin Globals
        self.globals['debug'] = {}
        self.globals['debug']['monitorDebugEnabled']  = False  # if False it indicates no debugging is active else it indicates that at least one type of debug is active

        self.globals['debug']['debugGeneral']     = logging.INFO  # For general debugging of the main thread
        self.globals['debug']['monitorRefresh']   = logging.INFO  # For monitoring refresh Dynamic View processing 
        self.globals['debug']['debugRefresh']     = logging.INFO  # For debugging refresh Dynamic View processing
        self.globals['debug']['debugMethodTrace'] = logging.INFO  # For displaying method invocations i.e. trace method

        self.globals['debug']['previousDebugGeneral']     = logging.INFO  # For general debugging of the main thread
        self.globals['debug']['previousMonitorRefresh']   = logging.INFO  # For monitoring refresh Dynamic View processing
        self.globals['debug']['previousDebugRefresh']     = logging.INFO  # For refresh Dynamic View processing
        self.globals['debug']['previousDebugMethodTrace'] = logging.INFO  # For displaying method invocations i.e. trace method

        # Setup Logging

        logformat = logging.Formatter('%(asctime)s.%(msecs)03d\t%(levelname)-12s\t%(name)s.%(funcName)-25s %(msg)s', datefmt='%Y-%m-%d %H:%M:%S')
        self.plugin_file_handler.setFormatter(logformat)

        self.plugin_file_handler.setLevel(logging.INFO)  # Master Logging Level for Plugin Log file

        self.indigo_log_handler.setLevel(logging.INFO)   # Logging level for Indigo Event Log

        self.generalLogger = logging.getLogger("Plugin.general")
        self.generalLogger.setLevel(self.globals['debug']['debugGeneral'])

        self.methodTracer = logging.getLogger("Plugin.method")  
        self.methodTracer.setLevel(self.globals['debug']['debugMethodTrace'])

        # Initialising Message
        self.generalLogger.info(u"Autolog 'Dynamic View Controller' initializing . . .")

        # Initialise dictionary to store internal details about Dynamic View devices
        self.globals['dynamics'] = {}

        self.globals['testSymLink'] = False

        self.validatePrefsConfigUi(pluginPrefs)  # Validate the Plugin Config before plugin initialisation

        self.setDebuggingLevels(pluginPrefs)  # Check monitoring and debug options  

        # self.generalLogger.debug(u'SELF = %s' % (type(self)))
        # self.generalLogger.debug(u'pluginId = %s' % (str(pluginId)))
        # self.generalLogger.debug(u'pluginDisplayName = %s' % (str(pluginDisplayName)))
        # self.generalLogger.debug(u'pluginVersion = %s' % (str(pluginVersion)))
        # self.generalLogger.debug(u'pluginPrefs = %s' % (str(pluginPrefs)))

    def __del__(self):
        indigo.PluginBase.__del__(self)

    def startup(self):

        self.methodTracer.threaddebug(u"CLASS: Plugin")

        self.globals['queues'] = {}
        self.globals['queues']['refreshDynamicView'] = {}  # There will be one 'refreshDynamicView' queue for each Dynamic View device - set-up in device start

        indigo.devices.subscribeToChanges()

        self.globals['threads'] = {}
        self.globals['threads']['refreshDynamicView'] = {}  # One thread per Dynamic View device

        self.generalLogger.info(u"Autolog 'Dynamic View Controller' initialization complete")

    def shutdown(self):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        self.generalLogger.info(u"Autolog 'Dynamic View Controller' Plugin shutdown requested")

        # Logic needed here to shutdown dynamic device threads .... ### FIX THIS [21-AUG-2016 & 5-SEP-2016 !!!] ###

        self.generalLogger.info(u"Autolog 'Dynamic View Controller' Plugin shutdown complete")

    def validatePrefsConfigUi(self, valuesDict):

        self.methodTracer.threaddebug(u"CLASS: Plugin")

        return True

    def closedPrefsConfigUi(self, valuesDict, userCancelled):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        self.generalLogger.debug(u"'closePrefsConfigUi' called with userCancelled = %s" % (str(userCancelled)))  

        if userCancelled:
            return

        # Check monitoring and debug options  
        self.setDebuggingLevels(valuesDict)

    def setDebuggingLevels(self, valuesDict):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        self.globals['debug']['monitorDebugEnabled'] = bool(valuesDict.get("monitorDebugEnabled", False))

        self.globals['debug']['debugGeneral']     = logging.INFO  # For general debugging of the main thread
        self.globals['debug']['monitorRefresh']   = logging.INFO  # For monitoring refresh Dynamic View processing 
        self.globals['debug']['debugRefresh']     = logging.INFO  # For debugging refresh Dynamic View processing

        if not self.globals['debug']['monitorDebugEnabled']:
            self.plugin_file_handler.setLevel(logging.INFO)
        else:
            self.plugin_file_handler.setLevel(logging.THREADDEBUG)

        debugGeneral     = bool(valuesDict.get("debugGeneral", False))
        monitorRefresh   = bool(valuesDict.get("monitorRefresh", False))
        debugRefresh     = bool(valuesDict.get("debugRefresh", False))
        debugMethodTrace = bool(valuesDict.get("debugMethodTrace", False))

        if debugGeneral:
            self.globals['debug']['debugGeneral'] = logging.DEBUG  # For general debugging of the main thread
        if monitorRefresh:
            self.globals['debug']['monitorRefresh'] = logging.DEBUG  # For logging messages sent to LIFX lamps 
        if debugRefresh:
            self.globals['debug']['debugRefresh'] = logging.DEBUG  # For debugging messages sent to LIFX lamps
        if debugMethodTrace:
            self.globals['debug']['debugMethodTrace'] = logging.THREADDEBUG  # For displaying method invocations i.e. trace method

        self.globals['debug']['monitoringActive'] = monitorRefresh

        self.globals['debug']['debugActive'] = debugGeneral or debugRefresh or debugMethodTrace

        if not self.globals['debug']['monitorDebugEnabled'] or (not self.globals['debug']['monitoringActive'] and not self.globals['debug']['debugActive']):
            self.generalLogger.info(u"No monitoring or debugging requested")
        else:
            if not self.globals['debug']['monitoringActive']:
                self.generalLogger.info(u"No monitoring requested")
            else:
                monitorTypes = []
                if monitorRefresh:
                    monitorTypes.append('Refresh')
                message = self.listActive(monitorTypes)   
                self.generalLogger.warning(u"Monitoring enabled for 'Dynamic View Controller': %s" % message)

            if not self.globals['debug']['debugActive']:
                self.generalLogger.info(u"No debugging requested")
            else:
                debugTypes = []
                if debugGeneral:
                    debugTypes.append('General')
                if debugRefresh:
                    debugTypes.append('Refresh')
                if debugMethodTrace:
                    debugTypes.append('Method Trace')
                message = self.listActive(debugTypes)   
                self.generalLogger.warning(u"Debugging enabled for 'Dynamic View Controller': %s" % message)

    def listActive(self, monitorDebugTypes):            
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        loop = 0
        listedTypes = ''
        for monitorDebugType in monitorDebugTypes:
            if loop == 0:
                listedTypes = listedTypes + monitorDebugType
            else:
                listedTypes = listedTypes + ', ' + monitorDebugType
            loop += 1
        return listedTypes

    def runConcurrentThread(self):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        # This thread is used to detect plugin close down only

        try:
            while True:
                self.sleep(60) # in seconds
        except self.StopThread:

            for self.dynamicDevId in self.globals['threads']['refreshDynamicView']:
                if self.globals['threads']['refreshDynamicView'][self.dynamicDevId]['threadActive']:
                    self.generalLogger.debug(u"'Refresh' BEING STOPPED")
                    self.globals['threads']['refreshDynamicView'][self.dynamicDevId]['event'].set()  # Stop the Thread
                    self.globals['queues']['refreshDynamicView'][self.dynamicDevId].put(['STOPTHREAD'])
                    self.globals['threads']['refreshDynamicView'][self.dynamicDevId]['thread'].join(7.0)  # wait for thread to end
                    self.generalLogger.debug(u"'Refresh' NOW STOPPED")
            pass

        self.generalLogger.debug(u"runConcurrentThread being stopped")   

    def deviceStartComm(self, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        self.currentTime = indigo.server.getTime()

        dev.stateListOrDisplayStateIdChanged()  # Ensure latest devices.xml is being used

        try:

            if dev.id in self.globals['dynamics']:
                self.generalLogger.debug(u"GLOBALS FOR DYNAMIC VIEW ALREADY SETUP")

            self.globals['dynamics'][dev.id] = {}
            self.globals['dynamics'][dev.id]['datetimeStarted'] = self.currentTime
            self.globals['dynamics'][dev.id]['processMode'] = dev.pluginProps.get('processMode', kProcessModeFoscamHD)
            self.globals['dynamics'][dev.id]['broadcasterPluginId'] = dev.pluginProps.get("broadcasterPluginId", kBroadcasterPluginId)
            self.globals['dynamics'][dev.id]['mesageType'] = dev.pluginProps.get("messageType", kMessageType)
            self.globals['dynamics'][dev.id]['rootFolder'] = dev.pluginProps.get('rootFolder', 'unknown')
            self.globals['dynamics'][dev.id]['symlinkFile'] = dev.pluginProps.get('symlinkFile', 'unknown')
            self.globals['dynamics'][dev.id]['symlinkLatestFile'] = dev.pluginProps.get('symlinkLatestFile', 'unknown')
            self.globals['dynamics'][dev.id]['numberOfCycleFiles'] = int(dev.pluginProps.get('numberOfCycleFiles', 0))
            self.globals['dynamics'][dev.id]['symlinkCycleFile'] = dev.pluginProps.get('symlinkCycleFile', 'unknown')
            self.globals['dynamics'][dev.id]['defaultFile'] = dev.pluginProps.get('defaultFile', 'unknown')
            self.globals['dynamics'][dev.id]['status'] = 'waiting ...'
            self.globals['dynamics'][dev.id]['refreshCount'] = 0
            try:
                indigo.server.subscribeToBroadcast(self.globals['dynamics'][dev.id]['broadcasterPluginId'], self.globals['dynamics'][dev.id]['mesageType'], u'broadcastReceived')  # Receive broadcasts from Foscam Plugin
            except StandardError, e:
                self.generalLogger.error(u"Dynamic View '%s' unable to subscribe to broadcast. Reason: %s" % (dev.name, e))   

            self.globals['dynamics'][dev.id]['filename'] = ''  # e.g. full file name e.g MDAlarm_20160905-170912.jpg
            self.globals['dynamics'][dev.id]['fileNameList'] = []  # e.g. ['20160907145723', '20160907150719', '20160907164503']
            self.globals['dynamics'][dev.id]['fileNameListIndex'] = -1  # Current selected index into fileNameList, fileModifiedDateList
            self.globals['dynamics'][dev.id]['fileNameListIndexMax'] = -1

            self.globals['dynamics'][dev.id]['latestFilename'] = ''
            self.globals['dynamics'][dev.id]['latestFullFilename'] = ''
            self.globals['dynamics'][dev.id]['latestFileDateTimeUI'] = ''

            self.globals['dynamics'][dev.id]['dateList'] = []  # e.g. ['20160904', '20160905', '20160906', '20160907']
            self.globals['dynamics'][dev.id]['dateListIndexIntofileNameList']= []  # Index into 'fileNameList' e.g. [0, 4, 56, 89]
            self.globals['dynamics'][dev.id]['dateListIndex'] = -1  # Current selected index into dateList
            self.globals['dynamics'][dev.id]['dateListIndexMax'] = -1

            self.globals['dynamics'][dev.id]['halfHourList'] = []  # e.g. ['201609040930', '201609041000', '201609051530', '201609061330', '201609061400', '201609061430', '201609070730', '201609071930', '201609072000']        
            self.globals['dynamics'][dev.id]['halfHourListIndexIntofileNameList'] = []  # Index into 'fileNameList' e.g. [0, 2, 4, 56, 64, 73, 89, 95, 121]        
            self.globals['dynamics'][dev.id]['halfHourListIndex'] = -1  # Current selected index into halfHourList
            self.globals['dynamics'][dev.id]['halfHourListIndexMax'] = -1
            self.globals['dynamics'][dev.id]['fullFileName'] = ''  # e.g. full file name e.g path/MDAlarm_20160905-170912.jpg

            if 'refreshDynamicView' in self.globals['queues']:
                if dev.id in self.globals['queues']['refreshDynamicView']:
                    with self.globals['queues']['refreshDynamicView'][dev.id].mutex:
                        self.globals['queues']['refreshDynamicView'][dev.id].queue.clear  # clear existing 'refreshDynamicView'  queue for device
                else: 
                    self.globals['queues']['refreshDynamicView'][dev.id]= Queue.Queue()  # set-up 'refreshDynamicView' queue for device

            if dev.id in self.globals['threads']['refreshDynamicView'] and self.globals['threads']['refreshDynamicView'][dev.id]['threadActive']:
                self.generalLogger.debug(u"'refreshDynamicView' BEING STOPPED")
                self.globals['threads']['refreshDynamicView'][dev.id]['event'].set()  # Stop the Thread
                self.globals['threads']['refreshDynamicView'][dev.id]['thread'].join(7.0)  # wait for thread to end
                self.generalLogger.debug(u"'refreshDynamicView' NOW STOPPED")
 
            self.globals['threads']['refreshDynamicView'][dev.id] = {}
            self.globals['threads']['refreshDynamicView'][dev.id]['threadActive'] = False
            self.globals['threads']['refreshDynamicView'][dev.id]['event'] = threading.Event()
            self.globals['threads']['refreshDynamicView'][dev.id]['thread'] = ThreadRefreshDynamicView(self.globals, dev.id, self.globals['threads']['refreshDynamicView'][dev.id]['event'])
            self.globals['threads']['refreshDynamicView'][dev.id]['thread'].start()

            keyValueList = []
            keyValue = {}
            keyValue['key'] = 'status'
            keyValue['value'] = self.globals['dynamics'][dev.id]['status']
            keyValueList.append(keyValue)
            keyValue = {}
            keyValue['key'] = 'refreshCount'
            keyValue['value'] = str(self.globals['dynamics'][dev.id]['refreshCount'])
            keyValueList.append(keyValue)
            keyValue = {}
            keyValue['key'] = 'selectedFilename'  # Will be full file name e.g MDAlarm_20160905-170912.jpg
            keyValue['value'] = ''
            keyValueList.append(keyValue)
            keyValue = {}
            keyValue['key'] = 'selectedDate'  # Will be e.g. 20160907
            keyValue['value'] = ''
            keyValueList.append(keyValue)
            keyValue = {}
            keyValue['key'] = 'selectedHalfHour'  # Will be e.g. 201609071430
            keyValue['value'] = ''
            keyValueList.append(keyValue)
            dev.updateStatesOnServer(keyValueList)
            dev.updateStateImageOnServer(indigo.kStateImageSel.TimerOff)

            # Initialise Dynamic State
            params = {}
            self.globals['queues']['refreshDynamicView'][dev.id].put(['initialiseDynamicState', params])

        except StandardError, e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.generalLogger.error(u"deviceStartComm: StandardError detected for '%s' at line '%s' = %s" % (dev.name, exc_tb.tb_lineno,  e))   

    ########################################################################
    # This method is called to generate a list of plugin identifiers / names
    ########################################################################
    def broadcasterPluginMenu(self, filter, valuesDict, typeId, devId):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        pluginNameList = []
        indigoInstallPath = indigo.server.getInstallFolderPath()
        pluginFolders =['Plugins', 'Plugins (Disabled)']
        for pluginFolder in pluginFolders:
            pluginsList = os.listdir(indigoInstallPath + '/' + pluginFolder)
            for plugin in pluginsList:
                # Check for Indigo Plugins and exclude 'system' plugins
                if (plugin.lower().endswith('.indigoplugin')) and (not plugin[0:1] == '.'):
                    # retrieve plugin Info.plist file
                    try:
                        pl = plistlib.readPlist(indigoInstallPath + "/" + pluginFolder + "/" + plugin + "/Contents/Info.plist")
                        CFBundleIdentifier = pl["CFBundleIdentifier"]
                        if self.pluginId != CFBundleIdentifier:
                            # Don't include self (i.e. this plugin) in the plugin list
                            CFBundleDisplayName = pl["CFBundleDisplayName"]
                            # if disabled plugins folder, append 'Disabled' to name
                            if pluginFolder == 'Plugins (Disabled)':
                                CFBundleDisplayName += ' [Disabled]'
                            pluginNameList.append((CFBundleIdentifier, CFBundleDisplayName))
                    except:
                        pass
        return pluginNameList

    def getDeviceConfigUiValues(self, pluginProps, typeId, devId):

        # Set default values for Edit Device Settings... (ConfigUI)

        if typeId == "dynamicView":
            pluginProps["broadcasterPluginId"] = pluginProps.get("broadcasterPluginId", kBroadcasterPluginId)
            pluginProps["messageType"] = pluginProps.get("messageType", kMessageType)
            pluginProps["rootFolder"] = pluginProps.get("rootFolder", "unknown")
            pluginProps["symlinkFile"] = pluginProps.get("symlinkFile", "unknown")
            pluginProps["symlinkLatestFile"] = pluginProps.get("symlinkLatestFile", "unknown")
            pluginProps["defaultFile"] = pluginProps.get("defaultFile", "unknown")

        return super(Plugin, self).getDeviceConfigUiValues(pluginProps, typeId, devId)

    def validateDeviceConfigUi(self, valuesDict, typeId, devId):
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        if typeId == "dynamicView":
            if valuesDict["broadcasterPluginId"] == '':
                valuesDict["broadcasterPluginId"] = kBroadcasterPluginId
            if valuesDict["messageType"] == '':
                valuesDict["messageType"] = kMessageType

        return True, valuesDict

    def deviceStopComm(self, dev):

        if dev.id in self.globals['threads']['refreshDynamicView'] and self.globals['threads']['refreshDynamicView'][dev.id]['threadActive']:
            self.generalLogger.debug(u"'refreshDynamicView' BEING STOPPED")
            self.globals['threads']['refreshDynamicView'][dev.id]['event'].set()  # Stop the Thread
            self.globals['queues']['refreshDynamicView'][dev.id].put(['STOPTHREAD'])
            self.globals['threads']['refreshDynamicView'][dev.id]['thread'].join(7.0)  # wait for thread to end
            self.generalLogger.debug(u"'refreshDynamicView' NOW STOPPED")
            self.globals['threads']['refreshDynamicView'].pop(dev.id, None)  # Remove Thread

        if 'refreshDynamicView' in self.globals['queues']:
            self.globals['queues']['refreshDynamicView'].pop(dev.id, None)  # Remove Queue

        self.globals['dynamics'].pop(dev.id, None)  # Remove Dynamic View plugin internal storage

    def broadcastReceived(self, arg):
        self.methodTracer.threaddebug(u"CLASS: Plugin")
    
        try:
            deviceIdBroadcastedTo = int(arg)
            if deviceIdBroadcastedTo in self.globals['dynamics']:
                params = {}
                self.globals['queues']['refreshDynamicView'][deviceIdBroadcastedTo].put(['updateDynamicState', params])
                params = {'type':'file', 'mode': 'none', 'number': 0}
                self.globals['queues']['refreshDynamicView'][deviceIdBroadcastedTo.id].put(['skip', params])

        except:
            pass

    def checkDynamicViewEnabled(self, dev, pluginAction):    
        self.methodTracer.threaddebug(u"CLASS: Plugin")

        if dev is None:
            callingAction = inspect.stack()[1][3]
            self.generalLogger.error(u"Plugin Action '%s' [%s] ignored as no Dynamic View device defined." % (pluginAction.name, callingAction))
            return False
        elif not dev.enabled:
            callingAction = inspect.stack()[1][3]
            self.generalLogger.error(u"Plugin Action '%s' [%s] ignored as Dynamic View '%s' is not enabled." % (pluginAction.name, callingAction, dev.name))
            return False

        return True

    def initialiseDynamicState(self, pluginAction, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")
    
        if not self.checkDynamicViewEnabled(dev, pluginAction):
            return

        params = {}
        self.globals['queues']['refreshDynamicView'][dev.id].put(['initialiseDynamicState', params])

    def updateDynamicState(self, pluginAction, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")
    
        if not self.checkDynamicViewEnabled(dev, pluginAction):
            return

        params = {}
        self.globals['queues']['refreshDynamicView'][dev.id].put(['updateDynamicState', params])

    def skipToLatest(self, pluginAction, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")
    
        if not self.checkDynamicViewEnabled(dev, pluginAction):
            return

        params = {'type':'file', 'mode': 'latest', 'number': 0}
        self.globals['queues']['refreshDynamicView'][dev.id].put(['skip', params])

    def daySkipBackward(self, pluginAction, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")
    
        if not self.checkDynamicViewEnabled(dev, pluginAction):
            return

        try:
            number = int(pluginAction.props.get('number', 1))
        except:
            number = 1
        params = {'type':'day', 'mode': 'back', 'number': number}
        self.globals['queues']['refreshDynamicView'][dev.id].put(['skip', params])

    def daySkipForward(self, pluginAction, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")
    
        if not self.checkDynamicViewEnabled(dev, pluginAction):
            return

        try:
            number = int(pluginAction.props.get('number', 1))
        except:
            number = 1
        params = {'type':'day', 'mode': 'forward', 'number': number}
        self.globals['queues']['refreshDynamicView'][dev.id].put(['skip', params])

    def timeSkipBackward(self, pluginAction, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")
    
        if not self.checkDynamicViewEnabled(dev, pluginAction):
            return

        try:
            number = int(pluginAction.props.get('number', 1))
        except:
            number = 1
        params = {'type':'time', 'mode': 'back', 'number': number}
        self.globals['queues']['refreshDynamicView'][dev.id].put(['skip', params])

    def timeSkipForward(self, pluginAction, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")
    
        if not self.checkDynamicViewEnabled(dev, pluginAction):
            return

        try:
            number = int(pluginAction.props.get('number', 1))
        except:
            number = 1
        params = {'type':'time', 'mode': 'forward', 'number': number}
        self.globals['queues']['refreshDynamicView'][dev.id].put(['skip', params])

    def skipBackward(self, pluginAction, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")
    
        if not self.checkDynamicViewEnabled(dev, pluginAction):
            return

        try:
            number = int(pluginAction.props.get('number', 1))
        except:
            number = 1
        params = {'type':'file', 'mode': 'back', 'number': number}
        self.globals['queues']['refreshDynamicView'][dev.id].put(['skip', params])

    def skipForward(self, pluginAction, dev):
        self.methodTracer.threaddebug(u"CLASS: Plugin")
    
        if not self.checkDynamicViewEnabled(dev, pluginAction):
            return

        try:
            number = int(pluginAction.props.get('number', 1))
        except:
            number = 1
        params = {'type':'file', 'mode': 'forward', 'number': number}
        self.globals['queues']['refreshDynamicView'][dev.id].put(['skip', params])

