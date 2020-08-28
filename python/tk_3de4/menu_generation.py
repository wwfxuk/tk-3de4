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
Menu handling for 3DE4

"""
from collections import defaultdict
from itertools import count
import os
import sys
import unicodedata

import sgtk
from sgtk.platform.qt import QtGui, QtCore


class MenuGenerator(object):
    """
    Menu generation functionality for 3DE4
    """
    root_ui_item = "Main Window::Shotgun"

    def __init__(self, engine):
        self._engine = engine
        self._current_menu_index = count()
        self.custom_scripts_dir_path = os.environ["TK_3DE4_MENU_DIR"]

    ##########################################################################################
    # public methods

    @property
    def logger(self):
        return self._engine.logger

    def create_menu(self):
        """
        Render the entire Shotgun menu.
        In order to have commands enable/disable themselves based on the enable_callback,
        re-create the menu items every time.
        """
        self.logger.info("Creating Shotgun menu...")

        # Get temp folder path and create it if needed.
        if not os.path.isdir(self.custom_scripts_dir_path):
            os.makedirs(self.custom_scripts_dir_path)
        # Clear it.
        for item in os.listdir(self.custom_scripts_dir_path):
            os.remove(os.path.join(self.custom_scripts_dir_path, item))

        menu_items = []
        for cmd_name, cmd_details in self._engine.commands.items():
             menu_items.append(AppCommand(cmd_name, cmd_details))

        ctx = self._engine.context
        ctx_name = str(ctx)
        ctx_menu_name = "{}::{}".format(MenuGenerator.root_ui_item, ctx_name)

        other_menu_items = defaultdict(list)
        favourites = []

        for cmd in menu_items:
            if cmd.get_type() == "context_menu":
                self.logger.debug("Adding %s to context menu", cmd.name)
                self._add_command_to_menu(cmd, ctx_menu_name)
            else:
                other_menu_items[cmd.get_app_name()].append(cmd)
            if cmd.favourite:
                favourites.append(cmd)

        for cmd in favourites:
            self.logger.debug("Adding %s to favourites", cmd.name)
            self._add_command_to_menu(cmd, MenuGenerator.root_ui_item)

        for app, cmds in other_menu_items.items():
            if len(cmds) == 1:
                parent_menu = MenuGenerator.root_ui_item
            else:
                parent_menu = "{}::{}".format(MenuGenerator.root_ui_item, app)
            for cmd in cmds:
                self.logger.debug("Adding %s to %s", cmd.name, parent_menu)
                self._add_command_to_menu(cmd, parent_menu)

    ##########################################################################################
    # context menu and UI

    def _add_script_to_menu(self, name, parent_menu, script):
        index = self._current_menu_index.next()
        script_path = os.path.join(self.custom_scripts_dir_path, "{:04d}.py".format(index))
        with open(script_path, "w") as menu_file:
            menu_file.write("# 3DE4.script.name: {}\n".format(name))
            menu_file.write("# 3DE4.script.gui:	{}\n".format(parent_menu))
            menu_file.write("\n".join(script))

    def _add_command_to_menu(self, cmd, parent_menu):
        script = [
            "import sgtk",
            "if __name__ == '__main__':",
            "   engine = sgtk.platform.current_engine()",
            "   engine.commands[{!r}]['callback']()".format(cmd.name),
        ]
        self._add_script_to_menu(cmd.name, parent_menu, script)


class AppCommand(object):
    """
    Wraps around a single command that you get from engine.commands
    """

    def __init__(self, name, command_dict):
        self.name = name
        self.properties = command_dict["properties"]
        self.callback = command_dict["callback"]
        self.favourite = self._is_app_favourite()

    def _is_app_favourite(self):
        if "app" not in self.properties:
            return False
        app_instance = self.properties["app"]
        engine = app_instance.engine
        app_instance_name = self.get_app_instance_name()
        for fav in engine.get_setting("menu_favourites"):
            fav_app_instance_name = fav["app_instance"]
            menu_name = fav["name"]
            if app_instance_name == fav_app_instance_name and self.name == menu_name:
                return True
        return False

    def get_app_name(self):
        """
        Returns the name of the app that this command belongs to
        """
        if "app" in self.properties:
            return self.properties["app"].display_name
        return "Other Items"

    def get_app_instance_name(self):
        """
        Returns the name of the app instance, as defined in the environment.
        Returns None if not found.
        """
        if "app" not in self.properties:
            return None

        app_instance = self.properties["app"]
        engine = app_instance.engine

        for (app_instance_name, app_instance_obj) in engine.apps.items():
            if app_instance_obj == app_instance:
                # found our app!
                return app_instance_name

        return None

    def get_type(self):
        """
        returns the command type. Returns node, custom_pane or default
        """
        return self.properties.get("type", "default")
