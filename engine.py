"""
A 3dequalizer4 engine for Tank.

"""
import datetime
import logging
import os
import re
import shutil
import sys

import sgtk
from sgtk.platform import Engine


class TDE4Engine(Engine):

    @property
    def context_change_allowed(self):
        return True

    @property
    def host_info(self):
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
        if self.has_ui:
            tk_3de4 = self.import_module("tk_3de4")
            menu_generator = tk_3de4.MenuGenerator(self)
            menu_generator.create_menu()

            import tde4
            tde4.rescanPythonDirs()

            return True
        return False

    def post_app_init(self):
        self.register_command(
            "Jump to Shotgun",
            self._jump_to_sg,
            {
                "short_name": "jump_to_sg",
                "description": "Jump to Entity page in Shotgun.",
                "type": "context_menu",
            },
        )
        self.register_command(
            "Jump to File System",
            self._jump_to_fs,
            {
                "short_name": "jump_to_fs",
                "description": "Open relevant folders in the file system.",
                "type": "context_menu",
            },
        )
        self.create_shotgun_menu()

    def post_qt_init(self):
        self._initialize_dark_look_and_feel()

    def post_context_change(self, old_context, new_context):
        self.create_shotgun_menu()

    def destroy_engine(self):
        self.logger.debug("%s: Destroying...", self)
        self._cleanup_folders()

    @property
    def has_ui(self):
        return True

    ##########################################################################################
    # logging

    def _emit_log_message(self, handler, record):
        log_debug = record.levelno < logging.INFO and sgtk.LogManager().global_debug
        log_info_above = record.levelno >= logging.INFO
        if log_debug or log_info_above:
            msg = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
            msg += " "
            msg += handler.format(record)
            print msg

    def _create_dialog(self, title, bundle, widget, parent):
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

    def _jump_to_sg(self):
        """
        Jump to shotgun, launch web browser
        """
        from sgtk.platform.qt import QtCore, QtGui
        url = self.context.shotgun_url
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))

    def _jump_to_fs(self):
        """
        Jump from context to FS
        """
        # launch one window for each location on disk
        paths = self.context.filesystem_locations
        for disk_location in paths:

            # get the setting
            system = sys.platform

            # run the app
            if system == "linux2":
                cmd = 'xdg-open "%s"' % disk_location
            elif system == "darwin":
                cmd = 'open "%s"' % disk_location
            elif system == "win32":
                cmd = 'cmd.exe /C start "Folder" "%s"' % disk_location
            else:
                raise Exception("Platform '%s' is not supported." % system)

            exit_code = os.system(cmd)
            if exit_code != 0:
                self.logger.error("Failed to launch '%s'!", cmd)

    def _cleanup_folders(self):
        custom_scripts_dir_path = os.environ["TK_3DE4_MENU_DIR"]
        if os.path.isdir(custom_scripts_dir_path):
            shutil.rmtree(custom_scripts_dir_path)
