#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Dynamic View Controller © Autolog 2016-2023
# Requires Indigo 2023.1+
#

try:
    # noinspection PyUnresolvedReferences
    import indigo
except ImportError:
    pass

import inspect
import os
import platform
import plistlib

import queue

import sys

import threading
import traceback

from constants import *
from refreshDynamicView import ThreadRefreshDynamicView

NO_FILE_SPECIFIED = "No File Specified"


class Plugin(indigo.PluginBase):
    def __init__(self, plugin_id, plugin_display_name, plugin_version, plugin_prefs, **kwargs):
        super(Plugin, self).__init__(plugin_id, plugin_display_name, plugin_version, plugin_prefs, **kwargs)

        self.debug = True

        # Initialise dictionary to store plugin Globals
        self.globals = dict()

        # Initialise Indigo plugin info
        self.globals[PLUGIN_INFO] = dict()
        self.globals[PLUGIN_INFO][PLUGIN_ID] = plugin_id
        self.globals[PLUGIN_INFO][PLUGIN_DISPLAY_NAME] = plugin_display_name
        self.globals[PLUGIN_INFO][PLUGIN_VERSION] = plugin_version
        self.globals[PLUGIN_INFO][PATH] = indigo.server.getInstallFolderPath()
        self.globals[PLUGIN_INFO][API_VERSION] = indigo.server.apiVersion
        self.globals[PLUGIN_INFO][ADDRESS] = indigo.server.address

        log_format = logging.Formatter("%(asctime)s.%(msecs)03d\t%(levelname)-12s\t%(name)s.%(funcName)-25s %(msg)s", datefmt="%Y-%m-%d %H:%M:%S")
        self.plugin_file_handler.setFormatter(log_format)
        self.plugin_file_handler.setLevel(LOG_LEVEL_INFO)  # Logging Level for plugin log file
        self.indigo_log_handler.setLevel(LOG_LEVEL_INFO)  # Logging level for Indigo Event Log

        self.logger = logging.getLogger("Plugin.Dynamic")

        # Initialising Message
        self.logger.info("'Dynamic View Controller' initializing . . .")

        # Initialise dictionary to store internal details about Dynamic View devices
        self.globals[DYNAMICS] = {}

        # Set Plugin Config Values
        self.closedPrefsConfigUi(plugin_prefs, False)

    def __del__(self):
        indigo.PluginBase.__del__(self)

    def display_plugin_information(self):
        try:
            def plugin_information_message():
                startup_message_ui = "Plugin Information:\n"
                startup_message_ui += f"{'':={'^'}80}\n"
                startup_message_ui += f"{'Plugin Name:':<30} {self.globals[PLUGIN_INFO][PLUGIN_DISPLAY_NAME]}\n"
                startup_message_ui += f"{'Plugin Version:':<30} {self.globals[PLUGIN_INFO][PLUGIN_VERSION]}\n"
                startup_message_ui += f"{'Plugin ID:':<30} {self.globals[PLUGIN_INFO][PLUGIN_ID]}\n"
                startup_message_ui += f"{'Indigo Version:':<30} {indigo.server.version}\n"
                startup_message_ui += f"{'Indigo License:':<30} {indigo.server.licenseStatus}\n"
                startup_message_ui += f"{'Indigo API Version:':<30} {indigo.server.apiVersion}\n"
                startup_message_ui += f"{'Indigo Reflector URL:':<30} {indigo.server.getReflectorURL()}\n"
                startup_message_ui += f"{'Indigo WebServer URL:':<30} {indigo.server.getWebServerURL()}\n"
                startup_message_ui += f"{'Architecture:':<30} {platform.machine()}\n"
                startup_message_ui += f"{'Python Version:':<30} {sys.version.split(' ')[0]}\n"
                startup_message_ui += f"{'Mac OS Version:':<30} {platform.mac_ver()[0]}\n"
                startup_message_ui += f"{'Plugin Process ID:':<30} {os.getpid()}\n"
                startup_message_ui += f"{'':={'^'}80}\n"
                return startup_message_ui

            self.logger.info(plugin_information_message())

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def exception_handler(self, exception_error_message, log_failing_statement):
        filename, line_number, method, statement = traceback.extract_tb(sys.exc_info()[2])[-1]
        module = filename.split("/")
        log_message = f"'{exception_error_message}' in module '{module[-1]}', method '{method} [{self.globals[PLUGIN_INFO][PLUGIN_VERSION]}]'"
        if log_failing_statement:
            log_message = log_message + f"\n   Failing statement [line {line_number}]: '{statement}'"
        else:
            log_message = log_message + f" at line {line_number}"
        self.logger.error(log_message)

    def startup(self):
        try:
            self.globals[QUEUES] = {}
            self.globals[QUEUES][REFRESH_DYNAMIC_VIEW] = {}  # There will be one 'refreshDynamicView' queue for each Dynamic View device - set-up in device start

            indigo.devices.subscribeToChanges()

            self.globals[THREADS] = {}
            self.globals[THREADS][REFRESH_DYNAMIC_VIEW] = {}  # One thread per Dynamic View device

            self.logger.info("'Dynamic View Controller' initialization complete")

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def shutdown(self):
        try:
            self.logger.info("'Dynamic View Controller' Plugin shutdown requested")

            # Logic needed here to shut down dynamic device threads .... ### FIX THIS [21-AUG-2016 & 5-SEP-2016 !!!] ###

            self.logger.info("'Dynamic View Controller' Plugin shutdown complete")

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    # noinspection PyMethodMayBeStatic
    def validatePrefsConfigUi(self, valuesDict):
        try:
            return True

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def closedPrefsConfigUi(self, values_dict, userCancelled):
        try:
            self.logger.debug(f"'closePrefsConfigUi' called with userCancelled = {str(userCancelled)}")

            if userCancelled:
                return

            self.globals[DEBUG] = bool(values_dict.get("developmentDebug", False))  # noqa

            # Get required Event Log and Plugin Log logging levels
            plugin_log_level = int(values_dict.get("pluginLogLevel", LOG_LEVEL_INFO))
            event_log_level = int(values_dict.get("eventLogLevel", LOG_LEVEL_INFO))

            # Ensure following logging level messages are output
            self.indigo_log_handler.setLevel(LOG_LEVEL_INFO)
            self.plugin_file_handler.setLevel(LOG_LEVEL_INFO)

            # Output required logging levels and TP Message Monitoring requirement to logs
            self.logger.info(f"Logging to Indigo Event Log at the '{LOG_LEVEL_TRANSLATION[event_log_level]}' level")
            self.logger.info(f"Logging to Plugin Event Log at the '{LOG_LEVEL_TRANSLATION[plugin_log_level]}' level")

            # Now set required logging levels
            self.indigo_log_handler.setLevel(event_log_level)
            self.plugin_file_handler.setLevel(plugin_log_level)


        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def dynamic(self, action, dev=None, callerWaitingForResult=None):
        try:
            # self.logger.warning(f"Handling Dynamic Image request")
            reply = indigo.Dict()
            try:
                props_dict = dict(action.props)
                dynamic_device_id = int(list(props_dict["file_path"])[0])  # Passed in URL
                selected_file_path = indigo.devices[dynamic_device_id].states["selectedFullFilename"]
                folder_root = self.globals[DYNAMICS][dynamic_device_id][ROOT_FOLDER]
                full_file_path = f"{folder_root}/{selected_file_path}"
                debug = 1  # Debug point
            except Exception as exception_error:
                # file name wasn't specified, set a flag
                full_file_path = NO_FILE_SPECIFIED
            try:
                reply = indigo.utils.return_static_file(full_file_path, status=200, path_is_relative=False, content_type="image/png")
            except Exception as exception_error:
                # file wasn't found
                if full_file_path == NO_FILE_SPECIFIED:
                    self.logger.error("no file was specified in the request query arguments")
                    reply["content"] = "no file was specified in the request query arguments"
                    reply["status"] = 400
                else:
                    if self.globals[DYNAMICS][dynamic_device_id][DEFAULT_FILE] != "" and self.globals[DYNAMICS][dynamic_device_id][DEFAULT_FILE] != "unknown":
                        # set user selection via device configuration
                        file_path = self.globals[DYNAMICS][dynamic_device_id][DEFAULT_FILE]
                    else:
                        # Set plugin default
                        file_path = f"{self.globals[PLUGIN_INFO][PATH]}/Plugins/dynamicView.indigoPlugin/Contents/Resources/default.png"
                    try:
                        reply = indigo.utils.return_static_file(file_path, status=200, path_is_relative=False, content_type="image/png")
                    except Exception as exception_error:
                        self.exception_handler(exception_error, True)  # Log error and display failing statement
            return reply

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def runConcurrentThread(self):
        try:
            # This thread is used to detect plugin close down only
            try:
                while True:
                    self.sleep(60)  # in seconds
            except self.StopThread:

                for self.dynamicDevId in self.globals[THREADS][REFRESH_DYNAMIC_VIEW]:
                    if self.globals[THREADS][REFRESH_DYNAMIC_VIEW][self.dynamicDevId][THREAD_ACTIVE]:
                        self.logger.debug("'Refresh' BEING STOPPED")
                        self.globals[THREADS][REFRESH_DYNAMIC_VIEW][self.dynamicDevId][EVENT].set()  # Stop the Thread
                        self.globals[QUEUES][REFRESH_DYNAMIC_VIEW][self.dynamicDevId].put([STOP_THREAD])
                        self.globals[THREADS][REFRESH_DYNAMIC_VIEW][self.dynamicDevId][THREAD].join(7.0)  # wait for thread to end
                        self.logger.debug("'Refresh' NOW STOPPED")
                pass

            self.logger.debug("runConcurrentThread being stopped")

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def deviceStartComm(self, dev):
        try:
            dev.stateListOrDisplayStateIdChanged()  # Ensure latest devices.xml is being used
            if dev.id in self.globals[DYNAMICS]:
                self.logger.debug("GLOBALS FOR DYNAMIC VIEW ALREADY SETUP")

            if dev.id not in self.globals[DYNAMICS]:
                self.globals[DYNAMICS][dev.id] = dict()
            self.globals[DYNAMICS][dev.id][DATE_TIME_STARTED] = indigo.server.getTime()

            self.globals[DYNAMICS][dev.id][DEBUG] = bool(dev.pluginProps.get("enableDebug", False))

            self.globals[DYNAMICS][dev.id][PROCESS_MODE] = int(dev.pluginProps.get("processMode", DynamicProcessMode.PROCESS_MODE_FOSCAM_HD))
            try:
                event_seconds = int(dev.pluginProps.get("eventSeconds", 5))
            except ValueError:
                event_seconds = 5
            self.globals[DYNAMICS][dev.id][EVENT_SECONDS] = event_seconds
            self.globals[DYNAMICS][dev.id][PROCESS_MODE] = int(dev.pluginProps.get("processMode", DynamicProcessMode.PROCESS_MODE_FOSCAM_HD))
            self.globals[DYNAMICS][dev.id][BROADCASTER_PLUGIN_ID] = dev.pluginProps.get("broadcasterPluginId", DEFAULT_BROADCASTER_PLUGIN_ID)
            self.globals[DYNAMICS][dev.id][MESSAGE_TYPE] = dev.pluginProps.get("messageType", DEFAULT_BROADCASTER_MESSAGE_TYPE)
            self.globals[DYNAMICS][dev.id][ROOT_FOLDER] = dev.pluginProps.get("rootFolder", "unknown")
            # self.globals[DYNAMICS][dev.id][SYM_LINK_FILE] = dev.pluginProps.get("symlinkFile", "unknown")
            # self.globals[DYNAMICS][dev.id][SYM_LINK_LATEST_FILE] = dev.pluginProps.get("symlinkLatestFile", "unknown")
            # self.globals[DYNAMICS][dev.id][NUMBER_OF_CYCLE_FILES] = int(dev.pluginProps.get("numberOfCycleFiles", 0))
            # self.globals[DYNAMICS][dev.id][SYM_LINK_CYCLE_FILE] = dev.pluginProps.get("symlinkCycleFile", "unknown")
            self.globals[DYNAMICS][dev.id][DEFAULT_FILE] = dev.pluginProps.get("defaultFile", "unknown")
            self.globals[DYNAMICS][dev.id][STATUS] = "idle"
            self.globals[DYNAMICS][dev.id][REFRESH_COUNT] = 0
            try:
                indigo.server.subscribeToBroadcast(self.globals[DYNAMICS][dev.id][BROADCASTER_PLUGIN_ID], self.globals[DYNAMICS][dev.id][MESSAGE_TYPE], "broadcastReceived")  # Receive broadcasts from Foscam Plugin
            except Exception as exception_error:
                self.logger.error(f"Dynamic View '{dev.name}' unable to subscribe to broadcast. Reason: {exception_error}")

            self.globals[DYNAMICS][dev.id][FILENAME] = ""  # e.g. full file name e.g MDAlarm_20160905-170912.jpg
            self.globals[DYNAMICS][dev.id][FILENAME_LIST] = []  # e.g. ['20160907145723', '20160907150719', '20160907164503']
            self.globals[DYNAMICS][dev.id][FILENAME_LIST_INDEX_SELECTED] = -1  # Current selected index into fileNameList, fileModifiedDateList
            self.globals[DYNAMICS][dev.id][FILENAME_LIST_INDEX_MAX] = -1

            self.globals[DYNAMICS][dev.id][LATEST_FILENAME] = ""
            self.globals[DYNAMICS][dev.id][LATEST_FULL_FILENAME] = ""
            self.globals[DYNAMICS][dev.id][LATEST_FILE_DATE_TIME_UI] = ""

            self.globals[DYNAMICS][dev.id][DATE_LIST] = []  # e.g. ['20160904', '20160905', '20160906', '20160907']
            self.globals[DYNAMICS][dev.id][DATE_LIST_INDEX_SELECTED] = -1  # Current selected index into dateList
            self.globals[DYNAMICS][dev.id][DATE_LIST_INDEX_MAX] = -1

            self.globals[DYNAMICS][dev.id][HALF_HOUR_LIST] = []  # e.g. ['201609040930', '201609041000', '201609051530', '201609061330', '201609061400', '201609061430', '201609070730', '201609071930', '201609072000']        
            self.globals[DYNAMICS][dev.id][HALF_HOUR_LIST_INDEX_SELECTED] = -1  # Current selected index into halfHourList
            self.globals[DYNAMICS][dev.id][HALF_HOUR_LIST_INDEX_MAX] = -1

            self.globals[DYNAMICS][dev.id][FULL_FILENAME] = ""  # e.g. full file name e.g path/MDAlarm_20160905-170912.jpg

            if REFRESH_DYNAMIC_VIEW in self.globals[QUEUES]:
                if dev.id in self.globals[QUEUES][REFRESH_DYNAMIC_VIEW]:
                    with self.globals[QUEUES][REFRESH_DYNAMIC_VIEW][dev.id].mutex:
                        self.globals[QUEUES][REFRESH_DYNAMIC_VIEW][dev.id].queue.clear  # noqa - clear existing 'refreshDynamicView'  queue for device
                else: 
                    self.globals[QUEUES][REFRESH_DYNAMIC_VIEW][dev.id] = queue.Queue()  # set-up 'refreshDynamicView' queue for device

            if dev.id in self.globals[THREADS][REFRESH_DYNAMIC_VIEW] and self.globals[THREADS][REFRESH_DYNAMIC_VIEW][dev.id][THREAD_ACTIVE]:
                self.logger.debug("'refreshDynamicView' BEING STOPPED")
                self.globals[THREADS][REFRESH_DYNAMIC_VIEW][dev.id][EVENT].set()  # Stop the Thread
                self.globals[THREADS][REFRESH_DYNAMIC_VIEW][dev.id][THREAD].join(7.0)  # wait for thread to end
                self.logger.debug("'refreshDynamicView' NOW STOPPED")
 
            self.globals[THREADS][REFRESH_DYNAMIC_VIEW][dev.id] = {}
            self.globals[THREADS][REFRESH_DYNAMIC_VIEW][dev.id][THREAD_ACTIVE] = False
            self.globals[THREADS][REFRESH_DYNAMIC_VIEW][dev.id][EVENT] = threading.Event()
            self.globals[THREADS][REFRESH_DYNAMIC_VIEW][dev.id][THREAD] = ThreadRefreshDynamicView(self.globals, dev.id, self.globals[THREADS][REFRESH_DYNAMIC_VIEW][dev.id][EVENT])
            self.globals[THREADS][REFRESH_DYNAMIC_VIEW][dev.id][THREAD].start()

            keyValueList = [
                {'key': 'status', 'value': self.globals[DYNAMICS][dev.id][STATUS]},
                {'key': 'refreshCount', 'value': f"{self.globals[DYNAMICS][dev.id][REFRESH_COUNT]}"},
                {'key': 'selectedFilename', 'value': ""},
                {'key': 'selectedDate', 'value': ""},
                {'key': 'selectedHalfHour', 'value': ""},
            ]
            dev.updateStatesOnServer(keyValueList)
            dev.updateStateImageOnServer(indigo.kStateImageSel.TimerOff)

            # Initialise Dynamic State
            params = {}
            self.globals[QUEUES][REFRESH_DYNAMIC_VIEW][dev.id].put([DynamicProcess.INITIALISE_DYNAMIC_STATE, params])

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    ########################################################################
    # This method is called to generate a list of plugin identifiers / names
    ########################################################################
    def broadcasterPluginMenu(self, device_filter, valuesDict, typeId, devId):
        try:
            pluginNameList = []
            indigoInstallPath = indigo.server.getInstallFolderPath()
            pluginFolders = ["Plugins", "Plugins (Disabled)"]
            for pluginFolder in pluginFolders:
                pluginsList = os.listdir(indigoInstallPath + "/" + pluginFolder)
                for plugin in pluginsList:
                    # Check for Indigo Plugins and exclude 'system' plugins
                    if (plugin.lower().endswith(".indigoplugin")) and (not plugin[0:1] == '.'):
                        # retrieve plugin Info.plist file
                        try:
                            filename = f"{indigoInstallPath}/{pluginFolder}/{plugin}/Contents/Info.plist"
                            with open(filename, "rb") as plist_file:
                                contents = plist_file.read()
                                pl = plistlib.loads(contents)
                                CFBundleIdentifier = pl["CFBundleIdentifier"]
                                if self.pluginId != CFBundleIdentifier:
                                    # Don't include self (i.e. this plugin) in the plugin list
                                    CFBundleDisplayName = pl["CFBundleDisplayName"]
                                    # if disabled plugins folder, append 'Disabled' to name
                                    if pluginFolder == "Plugins (Disabled)":
                                        CFBundleDisplayName += " [Disabled]"
                                    pluginNameList.append((CFBundleIdentifier, CFBundleDisplayName))
                        except Exception as exception_error:
                            pass
            return pluginNameList

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def getDeviceConfigUiValues(self, pluginProps, typeId, devId):
        try:
            # Set default values for Edit Device Settings... (ConfigUI)
            if typeId == "dynamicView":
                pluginProps["broadcasterPluginId"] = pluginProps.get("broadcasterPluginId", DEFAULT_BROADCASTER_PLUGIN_ID)
                pluginProps["messageType"] = pluginProps.get("messageType", DEFAULT_BROADCASTER_MESSAGE_TYPE)
                pluginProps["rootFolder"] = pluginProps.get("rootFolder", "unknown")
                pluginProps["symlinkFile"] = pluginProps.get("symlinkFile", "unknown")
                pluginProps["symlinkLatestFile"] = pluginProps.get("symlinkLatestFile", "unknown")
                pluginProps["defaultFile"] = pluginProps.get("defaultFile", "unknown")

            return super(Plugin, self).getDeviceConfigUiValues(pluginProps, typeId, devId)

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def validateDeviceConfigUi(self, valuesDict, typeId, devId):
        try:
            if typeId == "dynamicView":
                if valuesDict["broadcasterPluginId"] == "":
                    valuesDict["broadcasterPluginId"] = DEFAULT_BROADCASTER_PLUGIN_ID
                if valuesDict["messageType"] == "":
                    valuesDict["messageType"] = DEFAULT_BROADCASTER_MESSAGE_TYPE

            return True, valuesDict

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def deviceStopComm(self, dev):
        try:
            if dev.id in self.globals[THREADS][REFRESH_DYNAMIC_VIEW] and self.globals[THREADS][REFRESH_DYNAMIC_VIEW][dev.id][THREAD_ACTIVE]:
                self.logger.debug("'refreshDynamicView' BEING STOPPED")
                self.globals[THREADS][REFRESH_DYNAMIC_VIEW][dev.id][EVENT].set()  # Stop the Thread
                self.globals[QUEUES][REFRESH_DYNAMIC_VIEW][dev.id].put([STOP_THREAD])
                self.globals[THREADS][REFRESH_DYNAMIC_VIEW][dev.id][THREAD].join(7.0)  # wait for thread to end
                self.logger.debug("'refreshDynamicView' NOW STOPPED")
                self.globals[THREADS][REFRESH_DYNAMIC_VIEW].pop(dev.id, None)  # Remove Thread

            if REFRESH_DYNAMIC_VIEW in self.globals[QUEUES]:
                self.globals[QUEUES][REFRESH_DYNAMIC_VIEW].pop(dev.id, None)  # Remove Queue

            self.globals[DYNAMICS].pop(dev.id, None)  # Remove Dynamic View plugin internal storage

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def broadcastReceived(self, arg):
        try:
            deviceIdBroadcastedTo = int(arg)
            if deviceIdBroadcastedTo in self.globals[DYNAMICS]:
                params = dict()
                self.globals[QUEUES][REFRESH_DYNAMIC_VIEW][deviceIdBroadcastedTo].put([DynamicProcess.INITIALISE_DYNAMIC_STATE, params])
                params = dict()
                # params[SKIP_TYPE] = SkipType.SKIP_TYPE_FILE
                # params[SKIP_MODE] = SkipMode.SKIP_MODE_NONE
                # params[SKIP_NUMBER] = 0
                self.globals[QUEUES][REFRESH_DYNAMIC_VIEW][deviceIdBroadcastedTo].put([DynamicProcess.UPDATE_DYNAMIC_STATE, params])

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def checkDynamicViewEnabled(self, dev, pluginAction):
        try:
            if dev is None:
                callingAction = inspect.stack()[1][3]
                self.logger.error(f"Plugin Action '{pluginAction.name}' [{callingAction}] ignored as no Dynamic View device defined.")
                return False
            elif not dev.enabled:
                callingAction = inspect.stack()[1][3]
                self.logger.error(f"Plugin Action '{pluginAction.name}' [{callingAction}] ignored as Dynamic View '{dev.name}' is not enabled.")
                return False

            return True

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def initialiseDynamicState(self, pluginAction, dev):
        try:
            if not self.checkDynamicViewEnabled(dev, pluginAction):
                return

            params = {}
            self.globals[QUEUES][REFRESH_DYNAMIC_VIEW][dev.id].put([DynamicProcess.INITIALISE_DYNAMIC_STATE, params])

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def updateDynamicState(self, pluginAction, dev):
        try:
            if not self.checkDynamicViewEnabled(dev, pluginAction):
                return

            params = {}
            self.globals[QUEUES][REFRESH_DYNAMIC_VIEW][dev.id].put([DynamicProcess.UPDATE_DYNAMIC_STATE, params])

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def skipToFirst(self, pluginAction, dev):
        try:
            if not self.checkDynamicViewEnabled(dev, pluginAction):
                return

            # params = {TYPE: TYPE_FILE, MODE: MODE_LATEST, NUMBER: 0}
            params = dict()
            params[SKIP_TYPE] = SkipType.SKIP_TYPE_FILE
            params[SKIP_MODE] = SkipMode.SKIP_MODE_FIRST
            params[SKIP_NUMBER] = 0
            self.globals[QUEUES][REFRESH_DYNAMIC_VIEW][dev.id].put([DynamicProcess.SKIP, params])

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def skipToLatest(self, pluginAction, dev):
        try:
            if not self.checkDynamicViewEnabled(dev, pluginAction):
                return
            try:
                skip_type = pluginAction.props.get("skipType", "F")
            except Exception:
                skip_type = "F"

            # params = {TYPE: TYPE_FILE, MODE: MODE_LATEST, NUMBER: 0}
            params = dict()
            params[SKIP_TYPE] = skip_type
            params[SKIP_MODE] = SkipMode.SKIP_MODE_LATEST
            params[SKIP_NUMBER] = 0
            self.globals[QUEUES][REFRESH_DYNAMIC_VIEW][dev.id].put([DynamicProcess.SKIP, params])

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def daySkipBackward(self, pluginAction, dev):
        try:
            if not self.checkDynamicViewEnabled(dev, pluginAction):
                return

            try:
                number_to_skip = int(pluginAction.props.get("number", 1))
            except ValueError:
                number_to_skip = 1
            # params = {TYPE: TYPE_DAY, MODE: MODE_BACK, NUMBER: number_to_skip}
            params = dict()
            params[SKIP_TYPE] = SkipType.SKIP_TYPE_DAY
            params[SKIP_MODE] = SkipMode.SKIP_MODE_BACK
            params[SKIP_NUMBER] = number_to_skip
            self.globals[QUEUES][REFRESH_DYNAMIC_VIEW][dev.id].put([DynamicProcess.SKIP, params])

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def daySkipForward(self, pluginAction, dev):
        try:
            if not self.checkDynamicViewEnabled(dev, pluginAction):
                return

            try:
                number_to_skip = int(pluginAction.props.get("number", 1))
            except ValueError:
                number_to_skip = 1
            # params = {TYPE: TYPE_DAY, MODE: MODE_FORWARD, NUMBER: number_to_skip}
            params = dict()
            params[SKIP_TYPE] = SkipType.SKIP_TYPE_DAY
            params[SKIP_MODE] = SkipMode.SKIP_MODE_FORWARD
            params[SKIP_NUMBER] = number_to_skip
            self.globals[QUEUES][REFRESH_DYNAMIC_VIEW][dev.id].put([DynamicProcess.SKIP, params])

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def eventSkipBackward(self, pluginAction, dev):
        try:
            if not self.checkDynamicViewEnabled(dev, pluginAction):
                return

            try:
                number_to_skip = int(pluginAction.props.get("number", 1))
            except ValueError:
                number_to_skip = 1
            # params = {TYPE: TYPE_DAY, MODE: MODE_BACK, NUMBER: number_to_skip}
            params = dict()
            params[SKIP_TYPE] = SkipType.SKIP_TYPE_EVENT
            params[SKIP_MODE] = SkipMode.SKIP_MODE_BACK
            params[SKIP_NUMBER] = number_to_skip
            self.globals[QUEUES][REFRESH_DYNAMIC_VIEW][dev.id].put([DynamicProcess.SKIP, params])

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def eventSkipForward(self, pluginAction, dev):
        try:
            if not self.checkDynamicViewEnabled(dev, pluginAction):
                return

            try:
                number_to_skip = int(pluginAction.props.get("number", 1))
            except ValueError:
                number_to_skip = 1
            # params = {TYPE: TYPE_DAY, MODE: MODE_FORWARD, NUMBER: number_to_skip}
            params = dict()
            params[SKIP_TYPE] = SkipType.SKIP_TYPE_EVENT
            params[SKIP_MODE] = SkipMode.SKIP_MODE_FORWARD
            params[SKIP_NUMBER] = number_to_skip
            self.globals[QUEUES][REFRESH_DYNAMIC_VIEW][dev.id].put([DynamicProcess.SKIP, params])

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def timeSkipBackward(self, pluginAction, dev):
        try:
            if not self.checkDynamicViewEnabled(dev, pluginAction):
                return

            try:
                number_to_skip = int(pluginAction.props.get("number", 1))
            except ValueError:
                number_to_skip = 1
            # params = {TYPE: TYPE_TIME, MODE: MODE_BACK, NUMBER: number_to_skip}
            params = dict()
            params[SKIP_TYPE] = SkipType.SKIP_TYPE_TIME
            params[SKIP_MODE] = SkipMode.SKIP_MODE_BACK
            params[SKIP_NUMBER] = number_to_skip
            self.globals[QUEUES][REFRESH_DYNAMIC_VIEW][dev.id].put([DynamicProcess.SKIP, params])

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def timeSkipForward(self, pluginAction, dev):
        try:
            if not self.checkDynamicViewEnabled(dev, pluginAction):
                return

            try:
                number_to_skip = int(pluginAction.props.get("number", 1))
            except ValueError:
                number_to_skip = 1
            # params = {TYPE: TYPE_TIME, MODE: MODE_FORWARD, NUMBER: number_to_skip}
            params = dict()
            params[SKIP_TYPE] = SkipType.SKIP_TYPE_TIME
            params[SKIP_MODE] = SkipMode.SKIP_MODE_FORWARD
            params[SKIP_NUMBER] = number_to_skip
            self.globals[QUEUES][REFRESH_DYNAMIC_VIEW][dev.id].put([DynamicProcess.SKIP, params])

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def skipBackward(self, pluginAction, dev):
        try:
            if not self.checkDynamicViewEnabled(dev, pluginAction):
                return

            try:
                number_to_skip = int(pluginAction.props.get("number", 1))
            except ValueError:
                number_to_skip = 1
            # params = {TYPE: TYPE_FILE, MODE: MODE_BACK, NUMBER: number_to_skip}
            params = dict()
            params[SKIP_TYPE] = SkipType.SKIP_TYPE_FILE
            params[SKIP_MODE] = SkipMode.SKIP_MODE_BACK
            params[SKIP_NUMBER] = number_to_skip
            self.globals[QUEUES][REFRESH_DYNAMIC_VIEW][dev.id].put([DynamicProcess.SKIP, params])

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement

    def skipForward(self, pluginAction, dev):
        try:
            if not self.checkDynamicViewEnabled(dev, pluginAction):
                return
            try:
                number_to_skip = int(pluginAction.props.get("number", 1))
            except ValueError:
                number_to_skip = 1
            # params = {TYPE: TYPE_FILE, MODE: MODE_FORWARD, NUMBER: number_to_skip}
            params = dict()
            params[SKIP_TYPE] = SkipType.SKIP_TYPE_FILE
            params[SKIP_MODE] = SkipMode.SKIP_MODE_FORWARD
            params[SKIP_NUMBER] = number_to_skip
            self.globals[QUEUES][REFRESH_DYNAMIC_VIEW][dev.id].put([DynamicProcess.SKIP, params])

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing statement
