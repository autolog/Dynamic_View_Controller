#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Dynamic View Controller © Autolog 2016-2023
# Requires Indigo 2022.1+
#

try:
    # noinspection PyUnresolvedReferences
    import indigo
except ImportError:
    pass

import datetime as dt
from operator import itemgetter
import os
import queue
import subprocess
import sys
import threading
import time
import traceback

from constants import *


class ThreadRefreshDynamicView(threading.Thread):

    def __init__(self, plugin_globals, devId, event):

        threading.Thread.__init__(self)

        self.globals = plugin_globals

        self.debug = self.globals[DYNAMICS][devId][DEBUG]

        self.refresh_dynamic_view_logger = logging.getLogger("Plugin.Dynamic")

        self.thread_stop = event

        self.dynamic_device_id = int(devId)  # Set Indigo Device id (for Dynamic View) to the value passed in Thread invocation
        self.dynamic_device = indigo.devices[self.dynamic_device_id]  # Get latest Version of Dynamic Device
        self.dynamic_device_address = self.dynamic_device.address
        self.dynamic_device_name = self.dynamic_device.name

        if self.debug:
            self.refresh_dynamic_view_logger.debug(f"Initialising 'refreshDynamicView' Thread for {self.dynamic_device_name} [{self.dynamic_device_address}]")

        self.globals[THREADS][REFRESH_DYNAMIC_VIEW][self.dynamic_device_id][THREAD_ACTIVE] = True


    def exception_handler(self, exception_error_message, log_failing_statement):
        filename, line_number, method, statement = traceback.extract_tb(sys.exc_info()[2])[-1]  # noqa [Ignore duplicate code warning]
        module = filename.split("/")
        log_message = f"'{exception_error_message}' in module '{module[-1]}', method '{method} [{self.globals[PLUGIN_INFO][PLUGIN_VERSION]}]'"
        if log_failing_statement:
            log_message = log_message + f"\n   Failing statement [line {line_number}]: '{statement}'"
        else:
            log_message = log_message + f" at line {line_number}"
        self.refresh_dynamic_view_logger.error(log_message)

    def run(self):
        time.sleep(2)  # Allow devices to start?

        try:

            if self.debug:
                self.refresh_dynamic_view_logger.debug(f"Refresh Dynamic View Thread initialised for {self.dynamic_device_name} [{self.dynamic_device_address}]")

            while not self.thread_stop.is_set():
                try:
                    command_to_handle = self.globals[QUEUES][REFRESH_DYNAMIC_VIEW][self.dynamic_device_id].get(True, 5)
                    if command_to_handle[0] == STOP_THREAD:
                        continue  # self.thread_stop should be set

                    self.dynamic_device = indigo.devices[self.dynamic_device_id]  # Get latest Version of Dynamic Device

                    command = int(command_to_handle[0])
                    command_parameters = command_to_handle[1]

                    process_mode = self.globals[DYNAMICS][self.dynamic_device_id][PROCESS_MODE]
                    match command:
                        case DynamicProcess.INITIALISE_DYNAMIC_STATE:
                            self.processInitialiseDynamicState(process_mode)
                        case DynamicProcess.UPDATE_DYNAMIC_STATE:
                            self.processUpdateDynamicState(process_mode)
                        case DynamicProcess.SKIP:
                            self.processSkip(command_parameters)
                        case _:
                            if self.debug:
                                self.refresh_dynamic_view_logger.debug(f"Dynamic View, Received command '{command}' with parameters '{command_parameters}' ignored!")
                except queue.Empty:
                    pass

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing

            self.globals[DYNAMICS][self.dynamic_device_id][KEEP_THREAD_ALIVE] = False

            if self.debug:
                self.refresh_dynamic_view_logger.debug(f"Handle Command Thread ended for {self.dynamic_device_name} [{self.dynamic_device_address}]")

        if self.debug:
            self.refresh_dynamic_view_logger.debug(f"Refresh Dynamic View thread ended for Dynamic View: {self.dynamic_device_name} [{self.dynamic_device_address}]")

        self.globals[THREADS][REFRESH_DYNAMIC_VIEW][self.dynamic_device_id][THREAD_ACTIVE] = False

    def processInitialiseDynamicState(self, process_mode):

        try:
            if not self.processUpdateDynamicState(process_mode):
                self.refresh_dynamic_view_logger.error(f"Unable to initialise Dynamic State for '{self.dynamic_device.name}'")
                return

            parameters = dict()
            parameters[SKIP_TYPE] = SkipType.SKIP_TYPE_FILE
            parameters[SKIP_MODE] = SkipMode.SKIP_MODE_NONE
            parameters[SKIP_NUMBER] = 0
            self.processSkip(parameters)

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing

    def processUpdateDynamicState(self, process_mode):
        try:
            folder_root = self.globals[DYNAMICS][self.dynamic_device_id][ROOT_FOLDER]
            if folder_root == "unknown" or folder_root == "":
                self.refresh_dynamic_view_logger.error(f"Folder root not specified in Device Configuration for '{self.dynamic_device.name}'")
                return False

            try:
                # Save the currently selected: Day, Half-hour, Event and filename
                previously_selected_full_filename = self.dynamic_device.states["selectedFullFilename"]  # full file path with no folder_root e.g. '<SUB_DIR_1>_<SUB_DIR_2 etc>/filename.jpg'
                previously_selected_filename = self.dynamic_device.states["selectedFilename"]  # filename.jpg
                previously_selected_date = self.dynamic_device.states["selectedDate"]  # e.g. 20160907
                previously_selected_half_hour = self.dynamic_device.states["selectedHalfHour"]  # e.g. 201609071430
                previously_selected_event = self.dynamic_device.states["selectedEvent"]  # e.g. 20160907143924
            except Exception as exception_error:
                if self.debug:
                    self.refresh_dynamic_view_logger.debug("Previously Selected initialisation error caught!")
                previously_selected_full_filename = ""
                previously_selected_full_filename = ""
                previously_selected_date = ""
                previously_selected_half_hour = ""
                previously_selected_event = ""

            folder_root_length = len(folder_root) + 1  # allow for trailing backslash
            initial_file_name_list = list()  # e.g. multiple occurrences of [20230903173912, 'whatever.jpg']

            walk_successful = False
            retries_to_attempt = range(4)  # Five attempts
            for retry in retries_to_attempt:
                if self.debug:
                    self.refresh_dynamic_view_logger.debug(f"Walk attempt {retry}")
                try:
                    for dir_path, subdir_list, file_list in os.walk(folder_root, followlinks=True):
                        for file_name in file_list:
                            full_file_name_including_folder_root = os.path.join(dir_path, file_name)
                            event_file_name = full_file_name_including_folder_root[folder_root_length:]  # Remove common folder_root component of file_name to save space!

                            match process_mode:
                                case DynamicProcessMode.PROCESS_MODE_FOSCAM_HD:
                                    if file_name[0:8] != "MDAlarm_":  # Only process snapshot images if in foscamHD mode
                                        continue  # loop back to process next file
                                    foscam_date = file_name[8:16]  # e.g. 20230903
                                    foscam_time = file_name[17:23]  # e.g. 124959
                                    file_event_date_time = f"{foscam_date}{foscam_time}"
                                case DynamicProcessMode.PROCESS_MODE_MODIFIED_FILE_DATE_ORDER:
                                    if file_name[-3:] != "jpg":  # check file type
                                        continue
                                    last_modified_date_time = os.path.getmtime(full_file_name_including_folder_root)
                                    last_modified_date_time_local = time.localtime(last_modified_date_time)
                                    file_event_date_time = time.strftime("%Y%m%d%H%M%S", last_modified_date_time_local)  # e.g. 20230903173912
                                case _:
                                    return  # Invalid process mode

                            initial_file_name_list.append([file_event_date_time, event_file_name])  # e.g. 20230903173912, full file path with no folder_root e.g. '<SUB_DIR_1>_<SUB_DIR_2 etc>/filename.jpg'
                    walk_successful = True
                    break

                except Exception as exception_error:
                    pass  # Loop back to try again

            if not walk_successful:
                return False
            if self.debug:
                self.refresh_dynamic_view_logger.debug(f"Walk Successful")

            # Sort filename list on event date time and then filename
            initial_file_name_list = sorted(initial_file_name_list, key=lambda x: (x[0], x[1]))

            # Now create the index lists for: fate, half-hour and event
            date_list = list()
            half_hour_list = list()
            event_list = list()

            # Create the detailed filename index list where each entry will contain: event date_time, file name, date list index, half-hour list index and event index index
            file_name_list_detailed = list()

            # setup intial previous date time for: date / half_hour / event check
            event_previous_year = 2000
            event_previous_month = 1
            event_previous_day = 1
            event_previous_hour = 0
            event_previous_minute = 0
            event_previous_second = 0

            event_previous_date = "20000101"  # Used in 'Day' change check (YYYMMDD)
            event_previous_half_hour = "200001010000"  # Used in 'Half-Hour' change check (YYYYMMDDHHMM)

            selected_date_updated_index = -1
            selected_half_hour_updated_index = -1
            selected_event_updated_index = -1
            selected_file_name_updated_index = -1

            for file_name_index in range(len(initial_file_name_list)-1):
                indexed_event_file_name = initial_file_name_list[file_name_index][1]  # e.g. full file path with no folder_root e.g. '<SUB_DIR_1>_<SUB_DIR_2 etc>/filename.jpg'
                indexed_event_date_time = initial_file_name_list[file_name_index][0]  # e.g. 20230918151721

                indexed_event_date = indexed_event_date_time[0:8]  # Used in 'Day' change check (YYYMMDD)
                indexed_event_time = indexed_event_date_time[8:14]
                indexed_event_hour = indexed_event_time[0:2]
                indexed_event_minute = indexed_event_time[2:4]
                indexed_event_second = indexed_event_time[4:6]
                indexed_event_calculated_half_hour = "00" if indexed_event_minute < "30" else "30"
                indexed_event_half_hour = f"{indexed_event_date}{indexed_event_hour}{indexed_event_calculated_half_hour}"  # Used in 'Half-Hour' change check (YYYYMMDDHHMM)

                # Check for date change
                if indexed_event_date != event_previous_date:
                    date_list.append((indexed_event_date, file_name_index))
                    if self.debug:
                        self.refresh_dynamic_view_logger.debug(
                            f"New Date [{len(date_list) - 1}] @ {indexed_event_date} [{indexed_event_date_time}], FN Index: {file_name_index}")

                # Check for half-hour change
                if indexed_event_half_hour != event_previous_half_hour:
                    half_hour_list.append((indexed_event_half_hour, file_name_index))
                    if self.debug:
                        self.refresh_dynamic_view_logger.debug(
                            f"New Half Hour  [{len(half_hour_list) - 1}] @ {indexed_event_hour}:{indexed_event_calculated_half_hour} [{indexed_event_half_hour}], FN Index: {file_name_index}")

                # Check for event change
                event_year = int(indexed_event_date[0:4])
                event_month = int(indexed_event_date[4:6])
                event_day = int(indexed_event_date[6:8])
                event_hour = int(indexed_event_time[0:2])
                event_minute = int(indexed_event_time[2:4])
                event_second = int(indexed_event_time[4:6])
                previous_event_time = dt.datetime(event_previous_year, event_previous_month, event_previous_day, event_previous_hour, event_previous_minute, event_previous_second)
                event_time = dt.datetime(event_year, event_month, event_day, event_hour, event_minute, event_second)
                event_difference_seconds = (event_time - previous_event_time).total_seconds()
                if event_difference_seconds > self.globals[DYNAMICS][self.dynamic_device_id][EVENT_SECONDS]:
                    event_list.append((indexed_event_date_time, file_name_index))
                    if self.debug:
                        self.refresh_dynamic_view_logger.debug(
                            f"New event [{len(event_list) - 1}] @ {event_hour}:{event_minute}:{event_second} [{indexed_event_date_time}], FN Index: {file_name_index}")

                # Now set up the file_name_list_detailed
                current_date_list_index = len(date_list) - 1
                current_half_hour_list_index = len(half_hour_list) - 1
                current_event_list_index = len(event_list) - 1

                file_name_list_detailed.append((indexed_event_date_time, indexed_event_file_name, current_date_list_index, current_half_hour_list_index, current_event_list_index))

                current_filename_list_detailed_index = len(file_name_list_detailed) - 1
                if self.debug:
                    if current_filename_list_detailed_index > (len(file_name_list_detailed) - 100):  # TODO: Debug
                        self.refresh_dynamic_view_logger.debug(f"New Filename @ {file_name_list_detailed[current_filename_list_detailed_index]}")

                if indexed_event_file_name != previously_selected_full_filename:
                    # Re-calculate updated index of previous selected item
                    selected_date_updated_index = len(date_list) - 1  # Index starts from zero
                    selected_half_hour_updated_index = len(half_hour_list) - 1  # Index starts from zero
                    selected_event_updated_index = len(event_list) - 1  # Index starts from zero
                    selected_file_name_updated_index = len(file_name_list_detailed) - 1  # Index starts from zero

                # save current settings for next iteration check
                event_previous_year = int(event_year)
                event_previous_month = int(event_month)
                event_previous_day = int(event_day)
                event_previous_hour = int(event_hour)
                event_previous_minute = int(event_minute)
                event_previous_second = int(event_second)
                event_previous_date = indexed_event_date
                event_previous_half_hour = indexed_event_half_hour

            # At this point there a four lists: file_name_list_detailed, date_list, half_hour_list and event_list

            date_list_entry_count = len(date_list)
            half_hour_list_entry_count = len(half_hour_list)
            event_list_entry_count = len(event_list)
            file_name_list_detailed_entry_count = len(file_name_list_detailed)

            if file_name_list_detailed_entry_count > 0:
                # check if selected entries set and if not set to latest
                if selected_date_updated_index == -1:  # Not set
                    selected_date_updated_index = date_list_entry_count - 1  # Set to latest
                if selected_half_hour_updated_index == -1:  # Not set
                    selected_half_hour_updated_index = half_hour_list_entry_count - 1  # Set to latest
                if selected_event_updated_index == -1:  # Not set
                    selected_event_updated_index = event_list_entry_count - 1  # Set to latest
                if selected_file_name_updated_index == -1:  # Not set
                    selected_file_name_updated_index = file_name_list_detailed_entry_count - 1  # Set to latest file name

                full_file_name = file_name_list_detailed[selected_date_updated_index][1]

                self.globals[DYNAMICS][self.dynamic_device_id][FULL_FILENAME] = full_file_name
                # self.refresh_dynamic_view_logger.info(f"FULL_FILENAME [1]: {self.globals[DYNAMICS][self.dynamic_device_id][FULL_FILENAME]}")

                self.globals[DYNAMICS][self.dynamic_device_id][FILENAME] = full_file_name

                self.globals[DYNAMICS][self.dynamic_device_id][DATE_LIST] = date_list
                self.globals[DYNAMICS][self.dynamic_device_id][DATE_LIST_INDEX_SELECTED] = selected_date_updated_index
                self.globals[DYNAMICS][self.dynamic_device_id][DATE_LIST_INDEX_MAX] = len(date_list) - 1

                self.globals[DYNAMICS][self.dynamic_device_id][HALF_HOUR_LIST] = half_hour_list
                self.globals[DYNAMICS][self.dynamic_device_id][HALF_HOUR_LIST_INDEX_SELECTED] = selected_half_hour_updated_index
                self.globals[DYNAMICS][self.dynamic_device_id][HALF_HOUR_LIST_INDEX_MAX] = len(half_hour_list) - 1

                self.globals[DYNAMICS][self.dynamic_device_id][EVENT_LIST] = event_list
                self.globals[DYNAMICS][self.dynamic_device_id][EVENT_LIST_INDEX_SELECTED] = selected_event_updated_index
                self.globals[DYNAMICS][self.dynamic_device_id][EVENT_LIST_INDEX_MAX] = len(event_list) - 1

                self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST] = file_name_list_detailed
                self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST_INDEX_SELECTED] = selected_file_name_updated_index
                self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST_INDEX_MAX] = len(file_name_list_detailed) - 1

                self.globals[DYNAMICS][self.dynamic_device_id][LATEST_FILENAME] = file_name_list_detailed[len(file_name_list_detailed) - 1][1]

                self.globals[DYNAMICS][self.dynamic_device_id][LATEST_FULL_FILENAME] = self.globals[DYNAMICS][self.dynamic_device_id][LATEST_FILENAME]
                self.globals[DYNAMICS][self.dynamic_device_id][LATEST_FILE_DATE_TIME_UI] = "24-Sep-2023, 11:09:25"  # TODO: Sort this!

                parameters = dict()
                parameters[SKIP_TYPE] = SkipType.SKIP_TYPE_FILE
                parameters[SKIP_MODE] = SkipMode.SKIP_MODE_NONE
                parameters[SKIP_NUMBER] = 0
                self.processSkip(parameters)

                self.globals[DYNAMICS][self.dynamic_device_id][REFRESH_COUNT] += 1
                
                return True
            
        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing

        return False  # An error occurred or no folder to display

    # noinspection PyMethodMayBeStatic
    def _processUpdateDynamicStateFolderNameOrder(self, paramsNotUsedInThisMethod):

        # FUTURE DEVELOPMENT

        return False

    def processSkip(self, parameters):
        try:
            result = self._processSkip(1, parameters)
            if result:
                return
            process_mode = self.globals[DYNAMICS][self.dynamic_device_id][PROCESS_MODE]
            self.processUpdateDynamicState(process_mode)
            result = self._processSkip(2, parameters)

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing

    def _processSkip(self, attempt, parameters):
        try:
            # Delete timer that is setup to revert UI status (text and icon)
            if STATUS_TIMER in self.globals[DYNAMICS][self.dynamic_device_id]:
                self.globals[DYNAMICS][self.dynamic_device_id][STATUS_TIMER].cancel()
                del self.globals[DYNAMICS][self.dynamic_device_id][STATUS_TIMER]

            skipType = parameters[SKIP_TYPE]  # Can be: TYPE_DAY, TYPE_TIME, TYPE_FILE
            skipMode = parameters[SKIP_MODE]  # can be: MODE_BACK, MODE_FORWARD
            skipNumber = int(parameters[SKIP_NUMBER])  # Number to skip

            if len(self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST]) == 0:
                return

            date_list_length = len(self.globals[DYNAMICS][self.dynamic_device_id][DATE_LIST])
            half_hour_list_length = len(self.globals[DYNAMICS][self.dynamic_device_id][HALF_HOUR_LIST])
            event_list_length = len(self.globals[DYNAMICS][self.dynamic_device_id][EVENT_LIST])
            filename_list_length = len(self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST])
            if self.debug:
                self.refresh_dynamic_view_logger.debug(
                    f"BEFORE LENGTHS: Date={date_list_length}, Half-Hour={half_hour_list_length}, Event={event_list_length}, Filename={filename_list_length}")

            date_list_index_selected = self.globals[DYNAMICS][self.dynamic_device_id][DATE_LIST_INDEX_SELECTED]
            half_hour_list_index_selected = self.globals[DYNAMICS][self.dynamic_device_id][HALF_HOUR_LIST_INDEX_SELECTED]
            event_list_index_selected = self.globals[DYNAMICS][self.dynamic_device_id][EVENT_LIST_INDEX_SELECTED]
            filename_list_index_selected = self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST_INDEX_SELECTED]

            if self.debug:
                self.refresh_dynamic_view_logger.debug(
                    f"BEFORE SELECTION: Date={date_list_index_selected}, Half-Hour={half_hour_list_index_selected}, Event={event_list_index_selected}, Filename={filename_list_index_selected}")

            filename_selected_entry = self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST][filename_list_index_selected]
            if self.debug:
                self.refresh_dynamic_view_logger.debug(f"BEFORE FILE DETAILS: {filename_selected_entry}")
            match skipType:
                case SkipType.SKIP_TYPE_FILE:  # File(s) at a time
                    match skipMode:
                        case SkipMode.SKIP_MODE_FORWARD:
                            new_index = self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST_INDEX_SELECTED] + skipNumber
                            if new_index < (self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST_INDEX_MAX]):
                                self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST_INDEX_SELECTED] = new_index
                            else:
                                self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST_INDEX_SELECTED] = self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST_INDEX_MAX]
                        case SkipMode.SKIP_MODE_BACK:
                            new_index = self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST_INDEX_SELECTED] - skipNumber
                            if new_index > 0:
                                self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST_INDEX_SELECTED] = new_index
                            else:
                                self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST_INDEX_SELECTED] = 0
                        case SkipMode.SKIP_MODE_NONE:
                            pass  # Leave as is
                        case SkipMode.SKIP_MODE_FIRST:
                            self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST_INDEX_SELECTED] = 0
                        case _:  # skipMode == 'latest'
                            self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST_INDEX_SELECTED] = self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST_INDEX_MAX]

                    # Update associated 'selected' indexes
                    selected_index = self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST_INDEX_SELECTED]
                    self.globals[DYNAMICS][self.dynamic_device_id][DATE_LIST_INDEX_SELECTED] = self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST][selected_index][2]
                    self.globals[DYNAMICS][self.dynamic_device_id][HALF_HOUR_LIST_INDEX_SELECTED] = self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST][selected_index][3]
                    self.globals[DYNAMICS][self.dynamic_device_id][EVENT_LIST_INDEX_SELECTED] = self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST][selected_index][4]

                case SkipType.SKIP_TYPE_TIME:  # Half-hour(s) at a time
                    match skipMode:
                        case SkipMode.SKIP_MODE_FORWARD:
                            new_index = self.globals[DYNAMICS][self.dynamic_device_id][HALF_HOUR_LIST_INDEX_SELECTED] + skipNumber
                            if new_index < (self.globals[DYNAMICS][self.dynamic_device_id][HALF_HOUR_LIST_INDEX_MAX]):
                                self.globals[DYNAMICS][self.dynamic_device_id][HALF_HOUR_LIST_INDEX_SELECTED] = new_index
                            else:
                                self.globals[DYNAMICS][self.dynamic_device_id][HALF_HOUR_LIST_INDEX_SELECTED] = self.globals[DYNAMICS][self.dynamic_device_id][HALF_HOUR_LIST_INDEX_MAX]
                        case SkipMode.SKIP_MODE_BACK:
                            half_hour_list_index_selected = self.globals[DYNAMICS][self.dynamic_device_id][HALF_HOUR_LIST_INDEX_SELECTED]
                            half_hour_list_Filename_index_selected = self.globals[DYNAMICS][self.dynamic_device_id][HALF_HOUR_LIST][half_hour_list_index_selected][1]
                            if (skipNumber > 1 or
                                    half_hour_list_Filename_index_selected == self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST_INDEX_SELECTED]):
                                new_index = self.globals[DYNAMICS][self.dynamic_device_id][HALF_HOUR_LIST_INDEX_SELECTED] - skipNumber
                            else:
                                new_index = self.globals[DYNAMICS][self.dynamic_device_id][HALF_HOUR_LIST_INDEX_SELECTED]

                            if new_index > 0:
                                self.globals[DYNAMICS][self.dynamic_device_id][HALF_HOUR_LIST_INDEX_SELECTED] = new_index
                            else:
                                self.globals[DYNAMICS][self.dynamic_device_id][HALF_HOUR_LIST_INDEX_SELECTED] = 0
                        case SkipMode.SKIP_MODE_FIRST:
                            self.globals[DYNAMICS][self.dynamic_device_id][HALF_HOUR_LIST_INDEX_SELECTED] = 0
                        case _:  # skipMode == 'latest'
                            self.globals[DYNAMICS][self.dynamic_device_id][HALF_HOUR_LIST_INDEX_SELECTED] = self.globals[DYNAMICS][self.dynamic_device_id][HALF_HOUR_LIST_INDEX_MAX]

                    selected_half_hour_index = self.globals[DYNAMICS][self.dynamic_device_id][HALF_HOUR_LIST_INDEX_SELECTED]
                    self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST_INDEX_SELECTED] = self.globals[DYNAMICS][self.dynamic_device_id][HALF_HOUR_LIST][selected_half_hour_index][1]
                    selected_filename_index = self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST_INDEX_SELECTED]
                    self.globals[DYNAMICS][self.dynamic_device_id][DATE_LIST_INDEX_SELECTED] = self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST][selected_filename_index][2]
                    self.globals[DYNAMICS][self.dynamic_device_id][EVENT_LIST_INDEX_SELECTED] = self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST][selected_filename_index][4]

                case SkipType.SKIP_TYPE_DAY:  # Day(s) at a time
                    match skipMode:
                        case SkipMode.SKIP_MODE_FORWARD:
                            new_index = self.globals[DYNAMICS][self.dynamic_device_id][DATE_LIST_INDEX_SELECTED] + skipNumber
                            if new_index < (self.globals[DYNAMICS][self.dynamic_device_id][DATE_LIST_INDEX_MAX]):
                                self.globals[DYNAMICS][self.dynamic_device_id][DATE_LIST_INDEX_SELECTED] = new_index
                            else:
                                self.globals[DYNAMICS][self.dynamic_device_id][DATE_LIST_INDEX_SELECTED] = self.globals[DYNAMICS][self.dynamic_device_id][DATE_LIST_INDEX_MAX]
                        case SkipMode.SKIP_MODE_BACK:
                            date_list_index_selected = self.globals[DYNAMICS][self.dynamic_device_id][DATE_LIST_INDEX_SELECTED]
                            date_list_Filename_index_selected = self.globals[DYNAMICS][self.dynamic_device_id][DATE_LIST][date_list_index_selected][1]
                            if (skipNumber > 1 or
                                    date_list_Filename_index_selected == self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST_INDEX_SELECTED]):
                                new_index = self.globals[DYNAMICS][self.dynamic_device_id][DATE_LIST_INDEX_SELECTED] - skipNumber
                            else:
                                new_index = self.globals[DYNAMICS][self.dynamic_device_id][DATE_LIST_INDEX_SELECTED]

                            if new_index > 0:
                                self.globals[DYNAMICS][self.dynamic_device_id][DATE_LIST_INDEX_SELECTED] = new_index
                            else:
                                self.globals[DYNAMICS][self.dynamic_device_id][DATE_LIST_INDEX_SELECTED] = 0
                        case SkipMode.SKIP_MODE_FIRST:
                            self.globals[DYNAMICS][self.dynamic_device_id][DATE_LIST_INDEX_SELECTED] = 0
                        case _:  # skipMode == 'latest'
                            self.globals[DYNAMICS][self.dynamic_device_id][DATE_LIST_INDEX_SELECTED] = self.globals[DYNAMICS][self.dynamic_device_id][DATE_LIST_INDEX_MAX]

                    selected_date_index = self.globals[DYNAMICS][self.dynamic_device_id][DATE_LIST_INDEX_SELECTED]
                    self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST_INDEX_SELECTED] = self.globals[DYNAMICS][self.dynamic_device_id][DATE_LIST][selected_date_index][1]
                    selected_filename_index = self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST_INDEX_SELECTED]
                    self.globals[DYNAMICS][self.dynamic_device_id][HALF_HOUR_LIST_INDEX_SELECTED] = self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST][selected_filename_index][3]
                    self.globals[DYNAMICS][self.dynamic_device_id][EVENT_LIST_INDEX_SELECTED] = self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST][selected_filename_index][4]

                case SkipType.SKIP_TYPE_EVENT:  # Day(s) at a time
                    match skipMode:
                        case SkipMode.SKIP_MODE_FORWARD:
                            new_index = self.globals[DYNAMICS][self.dynamic_device_id][EVENT_LIST_INDEX_SELECTED] + skipNumber
                            if new_index < (self.globals[DYNAMICS][self.dynamic_device_id][EVENT_LIST_INDEX_MAX] - 1):
                                self.globals[DYNAMICS][self.dynamic_device_id][EVENT_LIST_INDEX_SELECTED] = new_index
                            else:
                                self.globals[DYNAMICS][self.dynamic_device_id][EVENT_LIST_INDEX_SELECTED] = self.globals[DYNAMICS][self.dynamic_device_id][EVENT_LIST_INDEX_MAX]
                        case SkipMode.SKIP_MODE_BACK:
                            event_list_index_selected = self.globals[DYNAMICS][self.dynamic_device_id][EVENT_LIST_INDEX_SELECTED]
                            event_list_Filename_index_selected = self.globals[DYNAMICS][self.dynamic_device_id][EVENT_LIST][event_list_index_selected][1]
                            if (skipNumber > 1 or
                                    event_list_Filename_index_selected == self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST_INDEX_SELECTED]):
                                new_index = self.globals[DYNAMICS][self.dynamic_device_id][EVENT_LIST_INDEX_SELECTED] - skipNumber
                            else:
                                new_index = self.globals[DYNAMICS][self.dynamic_device_id][EVENT_LIST_INDEX_SELECTED]
                            if new_index > 0:
                                self.globals[DYNAMICS][self.dynamic_device_id][EVENT_LIST_INDEX_SELECTED] = new_index
                            else:
                                self.globals[DYNAMICS][self.dynamic_device_id][EVENT_LIST_INDEX_SELECTED] = 0
                        case SkipMode.SKIP_MODE_FIRST:
                            self.globals[DYNAMICS][self.dynamic_device_id][DATE_LIST_INDEX_SELECTED] = 0
                        case _:  # skipMode == 'latest'
                            self.globals[DYNAMICS][self.dynamic_device_id][EVENT_LIST_INDEX_SELECTED] = self.globals[DYNAMICS][self.dynamic_device_id][EVENT_LIST_INDEX_MAX]

                    selected_event_index = self.globals[DYNAMICS][self.dynamic_device_id][EVENT_LIST_INDEX_SELECTED]
                    self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST_INDEX_SELECTED] = self.globals[DYNAMICS][self.dynamic_device_id][EVENT_LIST][selected_event_index][1]
                    selected_filename_index = self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST_INDEX_SELECTED]
                    self.globals[DYNAMICS][self.dynamic_device_id][DATE_LIST_INDEX_SELECTED] = self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST][selected_filename_index][2]
                    self.globals[DYNAMICS][self.dynamic_device_id][HALF_HOUR_LIST_INDEX_SELECTED] = self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST][selected_filename_index][3]

            selected_date_index = self.globals[DYNAMICS][self.dynamic_device_id][DATE_LIST_INDEX_SELECTED]
            latest_date_index = self.globals[DYNAMICS][self.dynamic_device_id][DATE_LIST_INDEX_MAX]
            selected_date_date = self.globals[DYNAMICS][self.dynamic_device_id][DATE_LIST][selected_date_index][0]
            selected_date_date_ui = f"{selected_date_date[6:8]}-{MONTHS_TRANSLATION[int(selected_date_date[4:6]) - 1]}-{selected_date_date[0:4]}"
            date_selected_number_ui = f"{(selected_date_index + 1)} of {(latest_date_index + 1)}"
            date_selected_number_expanded_ui = f"{date_selected_number_ui} | {selected_date_date_ui}"


            selected_half_hour_index = self.globals[DYNAMICS][self.dynamic_device_id][HALF_HOUR_LIST_INDEX_SELECTED]
            latest_half_hour_index = self.globals[DYNAMICS][self.dynamic_device_id][HALF_HOUR_LIST_INDEX_MAX]
            selected_half_hour_half_hour = self.globals[DYNAMICS][self.dynamic_device_id][HALF_HOUR_LIST][selected_half_hour_index][0]
            selected_half_hour_half_hour_ui = (f"{selected_half_hour_half_hour[6:8]}-{MONTHS_TRANSLATION[int(selected_half_hour_half_hour[4:6]) - 1]}-{selected_half_hour_half_hour[0:4]}, "
                                               f"{selected_half_hour_half_hour[8:10]}:{selected_half_hour_half_hour[10:12]}")
            half_hour_selected_number_ui = f"{(selected_half_hour_index + 1)} of {(latest_half_hour_index + 1)}"
            half_hour_selected_number_expanded_ui = f"{half_hour_selected_number_ui} | {selected_half_hour_half_hour_ui}"

            selected_event_index = self.globals[DYNAMICS][self.dynamic_device_id][EVENT_LIST_INDEX_SELECTED]
            latest_event_index = self.globals[DYNAMICS][self.dynamic_device_id][EVENT_LIST_INDEX_MAX]
            selected_event_event = self.globals[DYNAMICS][self.dynamic_device_id][EVENT_LIST][selected_event_index][0]
            selected_event_event_ui = (f"{selected_event_event[6:8]}-{MONTHS_TRANSLATION[int(selected_event_event[4:6]) - 1]}-{selected_event_event[0:4]}, "
                                               f"{selected_event_event[8:10]}:{selected_event_event[10:12]}:{selected_event_event[12:14]}")
            event_selected_number_ui = f"{(selected_event_index + 1)} of {(latest_event_index + 1)}"
            event_selected_number_expanded_ui = f"{event_selected_number_ui} | {selected_event_event_ui}"

            selected_filename_index = self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST_INDEX_SELECTED]
            latest_filename_index = self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST_INDEX_MAX]
            selected_filename_filename = self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST][selected_filename_index][0]
            selected_filename_filename_ui = (f"{selected_filename_filename[6:8]}-{MONTHS_TRANSLATION[int(selected_filename_filename[4:6]) - 1]}-{selected_filename_filename[0:4]}, "
                                       f"{selected_filename_filename[8:10]}:{selected_filename_filename[10:12]}:{selected_filename_filename[12:14]}")
            filename_selected_number_ui = f"{(selected_filename_index + 1)} of {(latest_filename_index + 1)}"
            filename_selected_number_expanded_ui = f"{filename_selected_number_ui} | {selected_filename_filename_ui}"

            selected_full_filename = self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST][selected_filename_index][1]
            latest_full_filename = self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST][latest_filename_index][1]
            path, selected_filename = os.path.split(self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST][selected_filename_index][1])
            path, latest_filename = os.path.split(self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST][latest_filename_index][1])

            selected_image_number = selected_filename_index + 1
            latest_maximum_number = latest_filename_index + 1

            derivedNumberUI = f"{selected_image_number} of {latest_maximum_number}"

            selected_date_time = self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST][selected_filename_index][0]  # e.g. 20230923134022
            derivedDateUI = f"{selected_date_time[6:8]}-{MONTHS_TRANSLATION[int(selected_date_time[4:6]) - 1]}-{selected_date_time[0:4]}"
            derivedTimeUI = f"{selected_date_time[8:10]}:{selected_date_time[10:12]}:{selected_date_time[12:14]}"
            # derivedHalfHourUI = f"{str(selected_date_time[8:10])}:{str(selected_date_time[10:12])}"
            selected_date_time_ui = f"{derivedDateUI}, {derivedTimeUI}"

            latest_date_time = self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST][latest_filename_index][0]  # e.g. 20230923134022
            derivedDateUI = f"{latest_date_time[6:8]}-{MONTHS_TRANSLATION[int(latest_date_time[4:6]) - 1]}-{latest_date_time[0:4]}"
            derivedTimeUI = f"{latest_date_time[8:10]}:{latest_date_time[10:12]}:{latest_date_time[12:14]}"
            # derivedHalfHourUI = f"{str(selected_date_time[8:10])}:{str(selected_date_time[10:12])}"
            latest_date_time_ui = f"{derivedDateUI}, {derivedTimeUI}"


            keyValueList = [
                dict(key="latestFilename", value=latest_filename),
                dict(key="latestFullFilename", value=latest_full_filename),
                dict(key="latestFileDateTimeUI", value=latest_date_time_ui),
                dict(key="selectedFilename", value=selected_filename),
                dict(key="selectedFullFilename", value=selected_full_filename),
                dict(key="selectedDate", value=selected_date_date),
                dict(key="selectedHalfHour", value=selected_half_hour_half_hour),
                dict(key="selectedEvent", value=selected_event_event),
                # dict(key="selectedImageNumberUI", value=derivedNumber),
                dict(key="latestMaximum", value=latest_maximum_number),
                dict(key="selectedFileDateTimeUI", value=selected_date_time_ui),

                dict(key="selectedDateNumberUI", value=date_selected_number_ui),
                dict(key="selectedDateLongUI", value=date_selected_number_expanded_ui),

                dict(key="selectedHalfHourNumberUI", value=half_hour_selected_number_ui),
                dict(key="selectedHalfHourLongUI", value=half_hour_selected_number_expanded_ui),

                dict(key="selectedEventNumberUI", value=event_selected_number_ui),
                dict(key="selectedEventLongUI", value=event_selected_number_expanded_ui),

                dict(key="selectedImageNumberUI", value=filename_selected_number_ui),
                dict(key="selectedImageLongUI", value=filename_selected_number_expanded_ui),
                dict(key="selectedNumber", value=selected_image_number),

                dict(key="status", value="... refreshing"),
                dict(key="refreshCount", value=str(self.globals[DYNAMICS][self.dynamic_device_id][REFRESH_COUNT]))
            ]
            self.dynamic_device.updateStatesOnServer(keyValueList)
            self.dynamic_device.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)

            timerSeconds = 3.0
            self.globals[DYNAMICS][self.dynamic_device_id][STATUS_TIMER] = threading.Timer(timerSeconds, self.updateStatusTimer, [STATUS_TIMER, self.dynamic_device_id])
            self.globals[DYNAMICS][self.dynamic_device_id][STATUS_TIMER].start()

            # ßselectedFile = f"{self.globals[DYNAMICS][self.dynamic_device_id][ROOT_FOLDER]}/{derivedDate}/{derivedHalfHour[0:8]}-{derivedHalfHour[8:12]}00/{derivedFileName}"

            # symLinkFile = self.globals[DYNAMICS][self.dynamic_device_id][SYM_LINK_FILE]
            # if symLinkFile != "unknown":
            #     process = subprocess.Popen(["unlink", symLinkFile], stdout=subprocess.PIPE)
            #     process = subprocess.Popen(["ln", "-s", derivedFullFileName, symLinkFile], stdout=subprocess.PIPE)
            #
            # symlinkLatestFile = self.globals[DYNAMICS][self.dynamic_device_id][SYM_LINK_LATEST_FILE]
            # if symLinkFile != "unknown":
            #     process = subprocess.Popen(["unlink", symlinkLatestFile], stdout=subprocess.PIPE)
            #     process = subprocess.Popen(["ln", "-s", latestFullFilename, symlinkLatestFile], stdout=subprocess.PIPE)

            date_list_index_selected = self.globals[DYNAMICS][self.dynamic_device_id][DATE_LIST_INDEX_SELECTED]
            half_hour_list_index_selected = self.globals[DYNAMICS][self.dynamic_device_id][HALF_HOUR_LIST_INDEX_SELECTED]
            event_list_index_selected = self.globals[DYNAMICS][self.dynamic_device_id][EVENT_LIST_INDEX_SELECTED]
            filename_list_index_selected = self.globals[DYNAMICS][self.dynamic_device_id][FILENAME_LIST_INDEX_SELECTED]

            if self.debug:
                self.refresh_dynamic_view_logger.debug(
                    f"AFTER SELECTION: Date={date_list_index_selected}, Half-Hour={half_hour_list_index_selected}, Event={event_list_index_selected}, Filename={filename_list_index_selected}")

            return True

        except Exception as exception_error:
            self.refresh_dynamic_view_logger.error(f"_procesSkip: Attempt = {attempt}")
            if attempt == 1:
                if self.debug:
                    pass
                self.refresh_dynamic_view_logger.error("_procesSkip: Attempt 1 failed")
                return False
            else:
                self.exception_handler(exception_error, True)  # Log error and display failing

    def updateStatusTimer(self, timerId, devId):
        try:
            keyValueList = [
                dict(key="status", value="idle")
            ]
            indigo.devices[devId].updateStatesOnServer(keyValueList)  # Just in case I want to update more fields ;-)

            indigo.devices[devId].updateStateImageOnServer(indigo.kStateImageSel.TimerOff)

        except Exception as exception_error:
            self.exception_handler(exception_error, True)  # Log error and display failing
