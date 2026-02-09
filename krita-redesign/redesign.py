"""
    Plugin for Krita UI Redesign, Copyright (C) 2020 Kapyia, Pedro Reis

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

from krita import *
from .nuTools.nttoolbox import ntToolBox
from .nuTools.nttooloptions import ntToolOptions
from . import variables
from PyQt6.QtCore import QEvent, QTimer
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QApplication, QMessageBox
    
class Redesign(Extension):

    usesFlatTheme = False
    usesBorderlessToolbar = False
    usesThinDocumentTabs = False
    usesNuToolbox = False
    usesNuToolOptions = False
    ntTB = None
    ntTO = None
 
    def __init__(self, parent):
        super().__init__(parent)
        self._theme_watcher_installed = False
        self._is_refreshing_theme = False
        self._theme_refresh_pending = False
        self._pending_palette = None
        self._palette_watch_timer = None
        self._last_palette_signature = None

    def setup(self):
        if Application.readSetting("Redesign", "usesFlatTheme", "true") == "true":
            self.usesFlatTheme = True

        if Application.readSetting("Redesign", "usesBorderlessToolbar", "true") == "true":
            self.usesBorderlessToolbar = True

        if Application.readSetting("Redesign", "usesThinDocumentTabs", "true") == "true":
            self.usesThinDocumentTabs = True

        if Application.readSetting("Redesign", "usesNuToolbox", "true") == "true":
            self.usesNuToolbox = True
        
        if Application.readSetting("Redesign", "usesNuToolOptions", "true") == "true":
            self.usesNuToolOptions = True

    def createActions(self, window):
        self._installThemeWatcher()
        window.qwindow().installEventFilter(self)
        actions = []

        actions.append(window.createAction("toolbarBorder", "Borderless Toolbars", ""))
        actions[0].setCheckable(True)
        actions[0].setChecked(self.usesBorderlessToolbar) 

        actions.append(window.createAction("tabHeight", "Thin Document Tabs", ""))
        actions[1].setCheckable(True)
        actions[1].setChecked(self.usesThinDocumentTabs)

        actions.append(window.createAction("flatTheme", "Use flat theme", ""))
        actions[2].setCheckable(True)
        actions[2].setChecked(self.usesFlatTheme)

        actions.append(window.createAction("nuToolbox", "NuToolbox", ""))
        actions[3].setCheckable(True)
        actions[3].setChecked(self.usesNuToolbox)

        actions.append(window.createAction("nuToolOptions", "NuToolOptions", ""))
        actions[4].setCheckable(True)

        if Application.readSetting("", "ToolOptionsInDocker", "false") == "true":
            actions[4].setChecked(self.usesNuToolOptions)

        menu = window.qwindow().menuBar().addMenu("Redesign")

        for a in actions:
            menu.addAction(a)

        actions[0].toggled.connect(self.toolbarBorderToggled)
        actions[1].toggled.connect(self.tabHeightToggled)
        actions[2].toggled.connect(self.flatThemeToggled)
        actions[3].toggled.connect(self.nuToolboxToggled)
        actions[4].toggled.connect(self.nuToolOptionsToggled)

        variables.refreshThemeStyles(self._paletteFromWindow(window.qwindow()))

        if (self.usesNuToolOptions and
            Application.readSetting("", "ToolOptionsInDocker", "false") == "true"):
                self.ntTO = ntToolOptions(window)

        if self.usesNuToolbox: 
            self.ntTB = ntToolBox(window)

        self.rebuildStyleSheet(window.qwindow())

        #self.nuToolOptionsToggled(self.usesNuToolOptions)
        #self.nuToolOptionsToggled(self.usesNuToolOptions)

    def _installThemeWatcher(self):
        if self._theme_watcher_installed:
            return

        app = QApplication.instance()
        if not app:
            return

        app.installEventFilter(self)
        if hasattr(app, "paletteChanged"):
            app.paletteChanged.connect(self._onApplicationPaletteChanged)
        self._startPaletteWatchTimer(app)
        self._last_palette_signature = self._paletteSignature(app.palette())
        self._theme_watcher_installed = True

    def eventFilter(self, obj, event):
        if self._isThemeChangeEvent(obj, event):
            self._scheduleThemeRefresh()

        return False

    def _scheduleThemeRefresh(self):
        self._scheduleThemeRefreshWithPalette(None)

    def _scheduleThemeRefreshWithPalette(self, palette=None):
        if palette is not None:
            self._pending_palette = QPalette(palette)

        if self._theme_refresh_pending:
            return

        self._theme_refresh_pending = True
        QTimer.singleShot(50, self._runScheduledThemeRefresh)

    def _runScheduledThemeRefresh(self):
        self._theme_refresh_pending = False
        palette = self._pending_palette
        self._pending_palette = None
        self.refreshAllWindowStyles(palette)

    def _startPaletteWatchTimer(self, app):
        if self._palette_watch_timer:
            return

        self._palette_watch_timer = QTimer(app)
        self._palette_watch_timer.setInterval(300)
        self._palette_watch_timer.timeout.connect(self._pollPaletteChange)
        self._palette_watch_timer.start()

    def _pollPaletteChange(self):
        palette = self._currentThemePalette()
        signature = self._paletteSignature(palette)
        if self._last_palette_signature != signature:
            self._last_palette_signature = signature
            self._scheduleThemeRefreshWithPalette(palette)

    def _onApplicationPaletteChanged(self, palette):
        resolved_palette = self._currentThemePalette()
        self._last_palette_signature = self._paletteSignature(resolved_palette)
        self._scheduleThemeRefreshWithPalette(resolved_palette)

    def _currentThemePalette(self):
        krita_active = Krita.instance().activeWindow()
        if krita_active and krita_active.qwindow():
            return self._paletteFromWindow(krita_active.qwindow())

        app = QApplication.instance()
        if app:
            active = app.activeWindow()
            if active:
                return self._paletteFromWindow(active)
            return app.palette()
        return QPalette()

    def _paletteFromWindow(self, qwindow):
        if qwindow:
            return qwindow.palette()

        return self._currentThemePalette()

    def _paletteSignature(self, palette):
        return (
            palette.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Window).name(),
            palette.color(QPalette.ColorGroup.Active, QPalette.ColorRole.AlternateBase).name(),
            palette.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Highlight).name(),
            palette.color(QPalette.ColorGroup.Active, QPalette.ColorRole.WindowText).name(),
            palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText).name(),
            palette.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Text).name(),
            palette.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Button).name(),
            palette.color(QPalette.ColorGroup.Active, QPalette.ColorRole.ButtonText).name(),
        )

    def _isThemeChangeEvent(self, obj, event):
        app = QApplication.instance()
        if not app:
            return False

        theme_event_types = (
            QEvent.Type.ApplicationPaletteChange,
            QEvent.Type.PaletteChange,
        )
        theme_change = getattr(QEvent.Type, "ThemeChange", None)
        event_type = event.type()
        if theme_change is not None:
            theme_event_types = theme_event_types + (theme_change,)

        if event_type not in theme_event_types:
            return False

        if obj is app:
            return True

        for window in Krita.instance().windows():
            if obj is window.qwindow():
                return True

        return False

    def refreshAllWindowStyles(self, palette=None):
        if self._is_refreshing_theme:
            return

        self._is_refreshing_theme = True
        try:
            source_palette = palette if palette is not None else self._currentThemePalette()
            self._last_palette_signature = self._paletteSignature(source_palette)
            for window in Krita.instance().windows():
                qwindow = window.qwindow()
                if qwindow:
                    self.rebuildStyleSheet(qwindow, qwindow.palette())
        finally:
            self._is_refreshing_theme = False

    def toolbarBorderToggled(self, toggled):
        Application.writeSetting("Redesign", "usesBorderlessToolbar", str(toggled).lower())

        self.usesBorderlessToolbar = toggled

        self.rebuildStyleSheet(Application.activeWindow().qwindow())


    def flatThemeToggled(self, toggled):
        Application.writeSetting("Redesign", "usesFlatTheme", str(toggled).lower())

        self.usesFlatTheme = toggled

        self.rebuildStyleSheet(Application.activeWindow().qwindow())

    
    def tabHeightToggled(self, toggled):
        Application.instance().writeSetting("Redesign", "usesThinDocumentTabs", str(toggled).lower())

        self.usesThinDocumentTabs = toggled

        self.rebuildStyleSheet(Application.activeWindow().qwindow())


    def nuToolboxToggled(self, toggled):
        Application.writeSetting("Redesign", "usesNuToolbox", str(toggled).lower())
        self.usesNuToolbox = toggled

        if toggled:
            self.ntTB = ntToolBox(Application.activeWindow())
            self.ntTB.pad.show() 
            self.ntTB.updateStyleSheet()
        elif not toggled and self.ntTB:
            self.ntTB.close()
            self.ntTB = None

    def nuToolOptionsToggled(self, toggled):
        if Application.readSetting("", "ToolOptionsInDocker", "false") == "true":
            Application.writeSetting("Redesign", "usesNuToolOptions", str(toggled).lower())
            self.usesNuToolOptions = toggled

            if toggled:
                self.ntTO = ntToolOptions(Application.activeWindow())
                self.ntTO.pad.show() 
                self.ntTO.updateStyleSheet()
            elif not toggled and self.ntTO:
                self.ntTO.close()
                self.ntTO = None
        else:
            msg = QMessageBox()
            msg.setText("nuTools requires the Tool Options Location to be set to 'In Docker'. \n\n" +
                        "This setting can be found at Settings -> Configure Krita... -> General -> Tools -> Tool Options Location." +
                        "Once the setting has been changed, please restart Krita.")
            msg.exec()


    def rebuildStyleSheet(self, window, palette=None):
        palette_to_use = palette if palette is not None else self._paletteFromWindow(window)
        variables.refreshThemeStyles(palette_to_use)

        full_style_sheet = ""
        
        # Dockers
        if self.usesFlatTheme:
            full_style_sheet += f"\n {variables.flat_dock_style} \n"
            full_style_sheet += f"\n {variables.flat_button_style} \n"
            full_style_sheet += f"\n {variables.flat_main_window_style} \n"
            full_style_sheet += f"\n {variables.flat_menu_bar_style} \n"
            full_style_sheet += f"\n {variables.flat_combo_box_style} \n"
            full_style_sheet += f"\n {variables.flat_status_bar_style} \n"
            full_style_sheet += f"\n {variables.flat_tree_view_style} \n"
            full_style_sheet += f"\n {variables.flat_tab_base_style} \n"
            if self.usesThinDocumentTabs:
                full_style_sheet += f"\n {variables.flat_tab_small_style} \n"
            else:
                full_style_sheet += f"\n {variables.flat_tab_big_style} \n"
        elif self.usesThinDocumentTabs:
            full_style_sheet += f"\n {variables.small_tab_style} \n"

        # Toolbar
        if self.usesFlatTheme:
            full_style_sheet += f"\n {variables.flat_toolbar_style} \n"
        elif self.usesBorderlessToolbar:
            full_style_sheet += f"\n {variables.no_borders_style} \n"    
        
        # Prevent intermediate layout events
        window.setUpdatesEnabled(False)
        try:
            window.setStyleSheet(full_style_sheet)

            # Overview
            overview = window.findChild(QWidget, 'OverviewDocker')
            overview_style = ""

            if self.usesFlatTheme:
                overview_style += f"\n {variables.flat_overview_docker_style} \n"

            if overview:
                overview.setStyleSheet(overview_style)

            canvas = window.centralWidget()

            # This is ugly, but it's the least ugly way I can get the canvas to 
            # update it's size (for now)
            canvas.resize(canvas.sizeHint())
        finally:
            window.setUpdatesEnabled(True)

        # Update Tool Options stylesheet
        if self.usesNuToolOptions and self.ntTO:
            self.ntTO.updateStyleSheet()

        # Update Toolbox stylesheet
        if self.usesNuToolbox and self.ntTB:
            self.ntTB.updateStyleSheet()  

Krita.instance().addExtension(Redesign(Krita.instance()))
