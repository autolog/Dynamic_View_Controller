#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# FOSCAM HD Controller © Autolog 2016-2107
# Requires Indigo 7
#

# plugin Constants

#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Foscam HD Controller © Autolog 2019-2022
# Requires Indigo 2022.1+
#

import logging

# ============================== Custom Imports ===============================
try:
    import indigo  # noqa
except ImportError:
    pass

number = -1

debug_show_constants = False
debug_use_labels = False

# def constant_id(constant_label) -> int:  # Auto increment constant id
def constant_id(constant_label):  # Auto increment constant id

    global number
    if debug_show_constants and number == -1:
        indigo.server.log("Dynamic View Controller Plugin internal Constant Name mapping ...", level=logging.DEBUG)
    number += 1
    if debug_show_constants:
        indigo.server.log(f"{number}: {constant_label}", level=logging.DEBUG)
    if debug_use_labels:
        return constant_label
    else:
        return number

# plugin Constants

# noinspection Duplicates
ADDRESS = constant_id("ADDRESS")
API_VERSION = constant_id("API_VERSION")
BROADCASTER_PLUGIN_ID = constant_id("BROADCASTER_PLUGIN_ID")

DATE_LIST = constant_id("DATE_LIST")
DATE_LIST_INDEX_SELECTED = constant_id("DATE_LIST_INDEX_SELECTED")
DATE_LIST_INDEX_MAX = constant_id("DATE_LIST_INDEX_MAX")

DATE_TIME_STARTED = constant_id("DATE_TIME_STARTED")
DAY = constant_id("DAY")

DEBUG = constant_id("DEBUG")

DEFAULT_FILE = constant_id("DEFAULT_FILE")
DYNAMICS = constant_id("DYNAMICS")
EVENT = constant_id("EVENT")
FILENAME = constant_id("FILENAME")

FILENAME_LIST = constant_id("FILENAME_LIST")
FILENAME_LIST_INDEX_SELECTED = constant_id("FILENAME_LIST_INDEX_SELECTED")
FILENAME_LIST_INDEX_MAX = constant_id("FILENAME_LIST_INDEX_MAX")

FULL_FILENAME = constant_id("FULL_FILENAME")

HALF_HOUR_LIST = constant_id("HALF_HOUR_LIST")
HALF_HOUR_LIST_INDEX_SELECTED = constant_id("HALF_HOUR_LIST_INDEX_SELECTED")
HALF_HOUR_LIST_INDEX_MAX = constant_id("HALF_HOUR_LIST_INDEX_MAX")

EVENT_LIST = constant_id("EVENT_LIST")
EVENT_LIST_INDEX_SELECTED = constant_id("EVENT_LIST_INDEX_SELECTED")
EVENT_LIST_INDEX_MAX = constant_id("EVENT_LIST_INDEX_MAX")

EVENT_SECONDS = constant_id("EVENT_SECONDS")

KEEP_THREAD_ALIVE = constant_id("KEEP_THREAD_ALIVE")
LATEST_FILENAME = constant_id("LATEST_FILENAME")
LATEST_FILE_DATE_TIME_UI = constant_id("LATEST_FILE_DATE_TIME_UI")
LATEST_FULL_FILENAME = constant_id("LATEST_FULL_FILENAME")
MESSAGE_TYPE = constant_id("MESSAGE_TYPE")
NUMBER_OF_CYCLE_FILES = constant_id("NUMBER_OF_CYCLE_FILES")
PATH = constant_id("PATH")
PLUGIN_DISPLAY_NAME = constant_id("PLUGIN_DISPLAY_NAME")
PLUGIN_ID = constant_id("PLUGIN_ID")
PLUGIN_INFO = constant_id("PLUGIN_INFO")
PLUGIN_VERSION = constant_id("PLUGIN_VERSION")
PROCESS_MODE = constant_id("PROCESS_MODE")
QUEUES = constant_id("QUEUES")
REFRESH_COUNT = constant_id("REFRESH_COUNT")
REFRESH_DYNAMIC_VIEW = constant_id("REFRESH_DYNAMIC_VIEW")
ROOT_FOLDER = constant_id("ROOT_FOLDER")
SKIP_MODE = constant_id("SKIP_MODE")
# SKIP_MODE_BACK = constant_id("SKIP_MODE_BACK")
# SKIP_MODE_FORWARD = constant_id("SKIP_MODE_FORWARD")
# SKIP_MODE_LATEST = constant_id("SKIP_MODE_LATEST")
# SKIP_MODE_NONE = constant_id("SKIP_MODE_NONE")
SKIP_NUMBER = constant_id("SKIP_NUMBER")
SKIP_TYPE = constant_id("SKIP_TYPE")
# SKIP_TYPE_DAY = constant_id("SKIP_TYPE_DAY")
# SKIP_TYPE_FILE = constant_id("SKIP_TYPE_FILE")
# SKIP_TYPE_TIME = constant_id("SKIP_TYPE_TIME")
STATUS = constant_id("STATUS")
STATUS_TIMER = constant_id("STATUS_TIMER")
STOP_THREAD = constant_id("STOP_THREAD")
SYM_LINK_CYCLE_FILE = constant_id("SYM_LINK_CYCLE_FILE")
SYM_LINK_FILE = constant_id("SYM_LINK_FILE")
SYM_LINK_LATEST_FILE = constant_id("SYM_LINK_LATEST_FILE")
TEST_SYM_LINK = constant_id("TEST_SYM_LINK")
THREAD = constant_id("THREAD")
THREADS = constant_id("THREADS")
THREAD_ACTIVE = constant_id("THREAD_ACTIVE")
ZZ_NUMBER = constant_id("NUMBER")

DEFAULT_BROADCASTER_PLUGIN_ID = "com.autologplugin.indigoplugin.foscamhdcontroller"  # Plugin ID of the 'Foscam HD Controller' plugin (taken from its Info.plist file):
DEFAULT_BROADCASTER_MESSAGE_TYPE = "updateDynamicView"  # Message Type of messages broadcast to this Plugin

MONTHS_TRANSLATION = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

PROCESS_MODE_FOSCAM_HD = "0"
PROCESS_MODE_MODIFIED_FILE_DATE_ORDER = "1"

LOG_LEVEL_NOT_SET = 0
LOG_LEVEL_DEBUGGING = 10
LOG_LEVEL_CAMERA = 15
LOG_LEVEL_INFO = 20
LOG_LEVEL_WARNING = 30
LOG_LEVEL_ERROR = 40
LOG_LEVEL_CRITICAL = 50

LOG_LEVEL_TRANSLATION = dict()
LOG_LEVEL_TRANSLATION[LOG_LEVEL_NOT_SET] = "Not Set"
LOG_LEVEL_TRANSLATION[LOG_LEVEL_DEBUGGING] = "Debugging"
LOG_LEVEL_TRANSLATION[LOG_LEVEL_CAMERA] = "Camera Communication Logging"
LOG_LEVEL_TRANSLATION[LOG_LEVEL_INFO] = "Info"
LOG_LEVEL_TRANSLATION[LOG_LEVEL_WARNING] = "Warning"
LOG_LEVEL_TRANSLATION[LOG_LEVEL_ERROR] = "Error"
LOG_LEVEL_TRANSLATION[LOG_LEVEL_CRITICAL] = "Critical"

LOG_LEVEL_TRANSLATION = dict()
LOG_LEVEL_TRANSLATION[LOG_LEVEL_NOT_SET] = "Not Set"
LOG_LEVEL_TRANSLATION[LOG_LEVEL_DEBUGGING] = "Topic Filter Logging"
LOG_LEVEL_TRANSLATION[LOG_LEVEL_INFO] = "Info"
LOG_LEVEL_TRANSLATION[LOG_LEVEL_WARNING] = "Warning"
LOG_LEVEL_TRANSLATION[LOG_LEVEL_ERROR] = "Error"
LOG_LEVEL_TRANSLATION[LOG_LEVEL_CRITICAL] = "Critical"


class DynamicProcess:
    # See https://stackoverflow.com/questions/67525257/capture-makes-remaining-patterns-unreachable
    INITIALISE_DYNAMIC_STATE = 0
    UPDATE_DYNAMIC_STATE = 1
    SKIP = 2


class DynamicProcessMode:
    PROCESS_MODE_FOSCAM_HD = 0
    PROCESS_MODE_MODIFIED_FILE_DATE_ORDER = 1


class SkipType:
    SKIP_TYPE_DAY = "D"
    SKIP_TYPE_EVENT = "E"
    SKIP_TYPE_FILE = "F"
    SKIP_TYPE_TIME = "T"


class SkipMode:
    SKIP_MODE_NONE = 0
    SKIP_MODE_BACK = 1
    SKIP_MODE_FIRST = 2
    SKIP_MODE_FORWARD = 3
    SKIP_MODE_LATEST = 4

