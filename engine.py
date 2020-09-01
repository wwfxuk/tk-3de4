"""
A 3dequalizer4 engine for Tank.

"""
from __future__ import print_function
import datetime
import logging
import os
import re
import shutil
import subprocess
import sys

import sgtk
from sgtk.platform import Engine


class TDE4Engine(Engine):

    @property
    def context_change_allowed(self):
        """
        Whether a context change is allowed without the need for a restart.
        If a bundle supports on-the-fly context changing, this property should
        be overridden in the deriving class and forced to return True.
        :returns: bool
        """
        return True

    @property
    def host_info(self):
        """
        Returns information about the application hosting this engine.
        This should be re-implemented in deriving classes to handle the logic
        specific to the application the engine is designed for.
        A dictionary with at least a "name" and a "version" key should be returned
        by derived implementations, with respectively the host application name
        and its release string as values, e.g. ``{ "name": "Maya", "version": "2017.3"}``.
        :returns: A ``{"name": "unknown", "version" : "unknown"}`` dictionary.
        """
        host_info = {"name": "3DEqualizer4", "version": "unknown"}
        try:
            import tde4
            host_info["name"], host_info["version"] = re.match(
                "^([^\s]+)\s+(.*)$", tde4.get3DEVersion()
            ).groups()
        except:
            # Fallback to initialized above
            pass

        return host_info

    def create_shotgun_menu(self):
        """
        Create the shotgun menu
        """
        if self.has_ui:
            self.register_command(
                "Jump to Shotgun",
                self._jump_to_shotgun,
                {
                    "short_name": "jump_to_sg",
                    "description": "Jump to Entity page in Shotgun.",
                    "type": "context_menu",
                },
            )
            self.register_command(
                "Jump to File System",
                self._jump_to_filesystem,
                {
                    "short_name": "jump_to_fs",
                    "description": "Open relevant folders in the file system.",
                    "type": "context_menu",
                },
            )
            tk_3de4 = self.import_module("tk_3de4")
            menu_generator = tk_3de4.MenuGenerator(self)
            menu_generator.create_menu()

            import tde4
            tde4.rescanPythonDirs()

            return True
        return False

    def post_app_init(self):
        """
        Executed by the system and typically implemented by deriving classes.
        This method called after all apps have been loaded.
        """
        self.create_shotgun_menu()

    def post_qt_init(self):
        """
        Called after the initialization of qt within startup.py.
        """
        self._initialize_dark_look_and_feel()

    def post_context_change(self, old_context, new_context):
        """
        Called after a context change.
        Implemented by deriving classes.
        :param old_context:     The context being changed away from.
        :type old_context: :class:`~sgtk.Context`
        :param new_context:     The context being changed to.
        :type new_context: :class:`~sgtk.Context`
        """
        self.create_shotgun_menu()

    def destroy_engine(self):
        """
        Called when the engine should tear down itself and all its apps.
        Implemented by deriving classes.
        """
        self.logger.debug("%s: Destroying...", self)
        self._cleanup_folders()

    @property
    def has_ui(self):
        """
        Indicates that the host application that the engine is connected to has a UI enabled.
        This always returns False for some engines (such as the shell engine) and may vary
        for some engines, depending if the host application for example is in batch mode or
        UI mode.
        :returns: boolean value indicating if a UI currently exists
        """
        return True

    ##########################################################################################
    # logging

    def _emit_log_message(self, handler, record):
        """
        Called by the engine whenever a new log message is available.
        All log messages from the toolkit logging namespace will be passed to this method.
        .. note:: To implement logging in your engine implementation, subclass
                  this method and display the record in a suitable way - typically
                  this means sending it to a built-in DCC console. In addition to this,
                  ensure that your engine implementation *does not* subclass
                  the (old) :meth:`Engine.log_debug`, :meth:`Engine.log_info` family
                  of logging methods.
                  For a consistent output, use the formatter that is associated with
                  the log handler that is passed in. A basic implementation of
                  this method could look like this::
                      # call out to handler to format message in a standard way
                      msg_str = handler.format(record)
                      # display message
                      print msg_str
        .. warning:: This method may be executing called from worker threads. In DCC
                     environments, where it is important that the console/logging output
                     always happens in the main thread, it is recommended that you
                     use the :meth:`async_execute_in_main_thread` to ensure that your
                     logging code is writing to the DCC console in the main thread.
        :param handler: Log handler that this message was dispatched from
        :type handler: :class:`~python.logging.LogHandler`
        :param record: Std python logging record
        :type record: :class:`~python.logging.LogRecord`
        """
        log_debug = record.levelno < logging.INFO and sgtk.LogManager().global_debug
        log_info_above = record.levelno >= logging.INFO
        if log_debug or log_info_above:
            msg = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
            print(msg, handler.format(record))

    def _create_dialog(self, title, bundle, widget, parent):
        """
        Create a TankQDialog with the specified widget embedded. This also connects to the
        dialogs dialog_closed event so that it can clean up when the dialog is closed.
        .. note:: For more information, see the documentation for :meth:`show_dialog()`.
        :param title: The title of the window
        :param bundle: The app, engine or framework object that is associated with this window
        :param widget: A QWidget instance to be embedded in the newly created dialog.
        :type widget: :class:`PySide.QtGui.QWidget`
        """
        from sgtk.platform.qt import QtCore
        dialog = super(TDE4Engine, self)._create_dialog(title, bundle, widget, parent)
        dialog.setWindowFlags(dialog.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
        dialog.setWindowState(
            (dialog.windowState() & ~QtCore.Qt.WindowMinimized) | QtCore.Qt.WindowActive)
        dialog.raise_()
        dialog.activateWindow()
        return dialog

    #########################################################################################
    # callbacks

    def _jump_to_shotgun(self):
        """
        Jump to shotgun, launch web browser
        """
        from sgtk.platform.qt import QtCore, QtGui
        url = self.context.shotgun_url
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))

    def _jump_to_filesystem(self):
        """
        Jump from context to the filesystem
        """
        # launch one window for each location on disk
        paths = self.context.filesystem_locations
        # get the setting
        system = sys.platform
        # run the app
        if system == "linux2":
            cmd = ["xdg-open"]
        elif system == "darwin":
            cmd = ["open"]
        elif system == "win32":
            cmd = ["cmd.exe", "/C", "start", "Folder"]
        else:
            raise Exception("Platform '%s' is not supported." % system)
        for disk_location in paths:
            args = cmd + [disk_location]
            try:
                subprocess.check_call(args)
            except Exception as error:
                cmdline = subprocess.list2cmdline(args)
                self.logger.error("Failed to launch '%s'!", cmdline)

    def _cleanup_folders(self):
        """
        Clean up the menu folders for the engine.
        """
        custom_scripts_dir_path = os.environ["TK_3DE4_MENU_DIR"]
        if os.path.isdir(custom_scripts_dir_path):
            shutil.rmtree(custom_scripts_dir_path)
