# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Hook that loads defines all the available actions, broken down by publish type.


Originally from ``tk-multi-loader2/tk-maya_actions.py``, this file can be
replaced by:

1. Creating our own copy of ``tk-multi-loader2`` repository
2. Edit the ``tk-multi-loader2/tk-maya_actions.py`` in there
3. Point to our ``tk-multi-loader2`` repository in
   ``env/includes/app_locations.yml:apps.tk-multi-loader2.location``
"""
import glob
from itertools import groupby, izip
import os
import re
import sgtk
from sgtk.platform.qt import QtCore, QtGui

import tde4


HookBaseClass = sgtk.get_hook_baseclass()


class FileExistenceError(Exception):
    def __init__(self, path):
        message = "Could not find file on disk for published file path: {!r}"
        super(FileExistenceError, self).__init__(message.format(path))


def key_func(items):
    return items[1] - items[0]


def get_frame_numbers(paths):
    numbers = []
    frame_pattern = re.compile(r".(\d+).")
    for path in paths:
        match = frame_pattern.search(path)
        if match:
            numbers.append(int(match.group(1)))
    return sorted(numbers)


def get_hash_path_and_range_info_from_seq(path):
    frame_pattern = re.compile(r"(%0(\d+)d)")
    frame_match = frame_pattern.search(path)
    if frame_match:
        has_frame_spec = True
        frame_spec = frame_match.group(1)
        glob_path = path.replace(frame_spec, "*")
        frame_files = glob.glob(glob_path)
        numbers = get_frame_numbers(frame_files)
        steps = []
        if not frame_files:
            raise FileExistenceError(path)
        for step, _ in groupby(izip(numbers[:-1], numbers[1:]), key_func):
            steps.append(step)
        if len(steps) > 1:
            raise Exception("Inconsistent frame steps")
        hashed_path = path.replace(frame_spec, "#" * int(frame_match.group(2)))
        start = min(numbers)
        end = max(numbers)
        step = steps[0]
        return hashed_path, start, end, step
    return path, 1, 1, 1


def check_file_exists(path):
    if not os.path.exists(path):
        raise FileExistenceError(path)


def is_sequence_camera(cam_id):
    return tde4.getCameraType(cam_id) == "SEQUENCE"

class TDE4Actions(HookBaseClass):

    ##############################################################################################################
    # public interface - to be overridden by deriving classes

    def generate_actions(self, sg_publish_data, actions, ui_area):
        """
        Returns a list of action instances for a particular publish.
        This method is called each time a user clicks a publish somewhere in the UI.
        The data returned from this hook will be used to populate the actions menu for a publish.

        The mapping between Publish types and actions are kept in a different place
        (in the configuration) so at the point when this hook is called, the loader app
        has already established *which* actions are appropriate for this object.

        The hook should return at least one action for each item passed in via the
        actions parameter.

        This method needs to return detailed data for those actions, in the form of a list
        of dictionaries, each with name, params, caption and description keys.

        Because you are operating on a particular publish, you may tailor the output
        (caption, tooltip etc) to contain custom information suitable for this publish.

        The ui_area parameter is a string and indicates where the publish is to be shown.
        - If it will be shown in the main browsing area, "main" is passed.
        - If it will be shown in the details area, "details" is passed.
        - If it will be shown in the history area, "history" is passed.

        Please note that it is perfectly possible to create more than one action "instance" for
        an action! You can for example do scene introspection - if the action passed in
        is "character_attachment" you may for example scan the scene, figure out all the nodes
        where this object can be attached and return a list of action instances:
        "attach to left hand", "attach to right hand" etc. In this case, when more than
        one object is returned for an action, use the params key to pass additional
        data into the run_action hook.

        :param sg_publish_data: Shotgun data dictionary with all the standard publish fields.
        :param actions: List of action strings which have been defined in the app configuration.
        :param ui_area: String denoting the UI Area (see above).
        :returns List of dictionaries, each with keys name, params, caption and description
        """
        app = self.parent
        app.logger.debug(
            "Generate actions called for UI element %s. "
            "Actions: %s. Publish Data: %s" % (ui_area, actions, sg_publish_data)
        )

        action_instances = []

        if "import_image_seq" in actions:
            action_instances.append(
                {
                    "name": "import_image_seq",
                    "params": {},
                    "caption": "Import Sequence",
                    "description": "Import image sequence and attach to selected sequence camera(s).",
                }
            )

        return action_instances

    def execute_multiple_actions(self, actions):
        """
        Executes the specified action on a list of items.

        The default implementation dispatches each item from ``actions`` to
        the ``execute_action`` method.

        The ``actions`` is a list of dictionaries holding all the actions to execute.
        Each entry will have the following values:

            name: Name of the action to execute
            sg_publish_data: Publish information coming from Shotgun
            params: Parameters passed down from the generate_actions hook.

        .. note::
            This is the default entry point for the hook. It reuses the ``execute_action``
            method for backward compatibility with hooks written for the previous
            version of the loader.

        .. note::
            The hook will stop applying the actions on the selection if an error
            is raised midway through.

        :param list actions: Action dictionaries.
        """
        for single_action in actions:
            name = single_action["name"]
            sg_publish_data = single_action["sg_publish_data"]
            params = single_action["params"]
            self.execute_action(name, params, sg_publish_data)

    def execute_action(self, name, params, sg_publish_data):
        """
        Execute a given action. The data sent to this be method will
        represent one of the actions enumerated by the generate_actions method.

        :param name: Action name string representing one of the items returned by generate_actions.
        :param params: Params data, as specified by generate_actions.
        :param sg_publish_data: Shotgun data dictionary with all the standard publish fields.
        :returns: No return value expected.
        """
        app = self.parent
        app.logger.debug(
            "Execute action called for action %s. "
            "Parameters: %s. Publish Data: %s" % (name, params, sg_publish_data)
        )

        # resolve path
        # toolkit uses utf-8 encoded strings internally and Maya API expects unicode
        # so convert the path to ensure filenames containing complex characters are supported
        path = self.get_publish_path(sg_publish_data).decode("utf-8")

        if name == "import_image_seq":
            self._import_image_seq(path, sg_publish_data)

    ##############################################################################################################
    # helper methods which can be subclassed in custom hooks to fine tune the behaviour of things

    def _import_image_seq(self, path, sg_publish_data):
        app = self.parent
        path, start, end, step = get_hash_path_and_range_info_from_seq(path)
        name = app.parent.context.entity["name"]

        camera_count = tde4.getNoCameras()
        if camera_count:
            selected_cameras = filter(is_sequence_camera, tde4.getCameraList(True))
            if not selected_cameras:
                QtGui.QMessageBox.warning(
                    None,
                    "No sequence cameras selected",
                    "Please select a sequence camera and try again"
                )
                return
            app.logger.info("%d sequence cameras selected, assigning to all", len(selected_cameras))
            for cam_id in selected_cameras:
                current_name = tde4.getCameraName(cam_id)
                if not current_name.startswith(name):
                    cam_name = name
                    count = 0
                    while tde4.findCameraByName(cam_name):
                        count += 1
                        cam_name = "{}__{:02}".format(name, count)
                        app.logger.info("Renaming '%s' to '%s'", current_name, cam_name)
                    tde4.setCameraName(cam_id, cam_name)
                else:
                    app.logger.info("'%s' already has name referring to Shot", current_name)
                tde4.setCameraSequenceAttr(cam_id, start, end, step)
                tde4.setCameraFrameOffset(cam_id, start)
                tde4.setCameraFrameRangeCalculationFlag(cam_id, 1)
                tde4.setCameraPath(cam_id, path)
        else:
            QtGui.QMessageBox.warning(
                None,
                "No cameras exist",
                "Please create a sequence camera and try again"
            )
