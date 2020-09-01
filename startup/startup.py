# 3DE4.script.hide: 			true
# 3DE4.script.startup: 			true

import os
import sys
import tde4

sys.path.append(
    os.path.join(os.getenv('TANK_CURRENT_PC'), 'install', 'core', 'python')
)
import sgtk


def _timer():
    """
    Poller to listen to the change of the scene file to determine the new
    context.
    """
    QtCore.QCoreApplication.processEvents()
    # check for open file change
    global g_current_file
    cur_file = tde4.getProjectPath()
    if g_current_file != cur_file:
        if cur_file:
            engine = sgtk.platform.current_engine()
            context = engine.context
            new_context = engine.sgtk.context_from_path(cur_file, context)
            if new_context != context:
                sgtk.platform.change_context(new_context)
        g_current_file = cur_file


if __name__ == '__main__':
    engine = sgtk.platform.current_engine()
    if not engine:
        from tank_vendor.shotgun_authentication import ShotgunAuthenticator
        user = ShotgunAuthenticator(sgtk.util.CoreDefaultsManager()).get_user()
        sgtk.set_authenticated_user(user)
        context = sgtk.context.deserialize(os.environ.get("TANK_CONTEXT"))
        engine = sgtk.platform.start_engine('tk-3de4', context.sgtk, context)

    from sgtk.platform.qt import QtCore, QtGui

    # Qt
    if not QtCore.QCoreApplication.instance():
        QtGui.QApplication([])
        global g_current_file
        g_current_file = tde4.getProjectPath()
        tde4.setTimerCallbackFunction("_timer", 50)
        engine.post_qt_init()
