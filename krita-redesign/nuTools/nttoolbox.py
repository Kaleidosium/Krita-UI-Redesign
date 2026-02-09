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

from PyQt6.QtCore import QSignalBlocker, QTimer, Qt
from PyQt6.QtGui import QIcon, QPalette, QPixmap, QPainter, QColor
from PyQt6.QtWidgets import QMdiArea, QDockWidget, QToolButton
from .ntadjusttosubwindowfilter import ntAdjustToSubwindowFilter
from .ntwidgetpad import ntWidgetPad
from .. import variables

class ntToolBox():

    def __init__(self, window):
        qWin = window.qwindow()
        self.qWin = qWin
        mdiArea = qWin.findChild(QMdiArea)
        toolbox = qWin.findChild(QDockWidget, 'ToolBox')
        self.sourceDocker = toolbox

        # Create "pad"
        self.pad = ntWidgetPad(mdiArea)
        self.pad.setObjectName("toolBoxPad")
        self.pad.borrowDocker(toolbox)
        self.pad.setViewAlignment('left')
        
        # Create and install event filter
        self.adjustFilter = ntAdjustToSubwindowFilter(mdiArea)
        self.adjustFilter.setTargetWidget(self.pad)
        mdiArea.subWindowActivated.connect(self.ensureFilterIsInstalled)
        qWin.installEventFilter(self.adjustFilter)

        # Create visibility toggle action
        action = window.createAction("showToolbox", "Show Toolbox", "settings")
        action.toggled.connect(self.pad.toggleWidgetVisible)
        action.setCheckable(True)
        action.setChecked(True)

        # Disable the related QDockWidget
        self.dockerAction = window.qwindow().findChild(QDockWidget, "ToolBox").toggleViewAction()
        self.sourceDocker.visibilityChanged.connect(self._onDockerVisibilityChanged)
        self._ensureDockerHidden()
        self.dockerAction.setEnabled(False)
        
        # Track if we've completed initial icon setup (skip first recolor)
        self._icons_initialized = False

    def ensureFilterIsInstalled(self, subWin):
        """Ensure that the current SubWindow has the filter installed,
        and immediately move the Toolbox to current View."""
        if subWin:
            subWin.installEventFilter(self.adjustFilter)
            self._ensureDockerHidden()
            self.pad.adjustToView()
            self.updateStyleSheet()

    def _onDockerVisibilityChanged(self, isVisible):
        if isVisible and self._isSourceDockerEffectivelyEmpty():
            self._ensureDockerHidden()

    def _ensureDockerHidden(self):
        if not self._isSourceDockerEffectivelyEmpty():
            return

        if self.sourceDocker and self.sourceDocker.isVisible():
            self.sourceDocker.hide()

        if self.dockerAction and self.dockerAction.isChecked():
            blocker = QSignalBlocker(self.dockerAction)
            self.dockerAction.setChecked(False)

    def _isSourceDockerEffectivelyEmpty(self):
        if not self.sourceDocker:
            return False

        sourceWidget = self.sourceDocker.widget()
        if sourceWidget is None:
            return True

        return sourceWidget.parentWidget() is not self.sourceDocker

    def findDockerAction(self, window, text):
        dockerMenu = None
        
        for m in window.qwindow().actions():
            if m.objectName() == "settings_dockers_menu":
                dockerMenu = m

                for a in dockerMenu.menu().actions():
                    if a.text().replace('&', '') == text:
                        return a
                
        return False

    def updateStyleSheet(self, palette=None):
        if palette is not None:
            palette_to_use = palette
        elif self.sourceDocker:
            palette_to_use = self.sourceDocker.palette()
        else:
            palette_to_use = self.qWin.palette()
        variables.refreshThemeStyles(palette_to_use)
        self.pad.setStyleSheet(variables.nu_toolbox_style)
        self.pad.btnHide.updateStyleSheet()
        self._refreshToolButtonIcons(palette_to_use)

    def _refreshToolButtonIcons(self, palette=None):
        # Skip recoloring on initial setup - icons aren't fully loaded yet
        if not self._icons_initialized:
            self._icons_initialized = True
            return

        if palette is None:
            palette = self.qWin.palette()

        # Get the target text color from the palette
        text_color = palette.color(QPalette.ColorGroup.Active, QPalette.ColorRole.WindowText)

        for button in self.pad.findChildren(QToolButton):
            # Force the button to use the new palette
            button.setPalette(palette)
            button.setForegroundRole(QPalette.ColorRole.WindowText)

            # Store original icon on first encounter (before any recoloring)
            if not hasattr(button, '_original_icon') or button._original_icon is None:
                button._original_icon = button.icon()

            # Recolor the ORIGINAL icon to match the new theme
            original_icon = button._original_icon
            if original_icon and not original_icon.isNull():
                recolored_icon = self._recolorIcon(original_icon, text_color)
                button.setIcon(recolored_icon)

            if button.style():
                button.style().unpolish(button)
                button.style().polish(button)
            
            button.update()

    def _recolorIcon(self, icon, color):
        """Recolor an icon's pixmaps at all available sizes to the specified color."""
        # Get all available sizes from the icon
        sizes = icon.availableSizes()
        
        # If no sizes reported, use common icon sizes
        if not sizes:
            from PyQt6.QtCore import QSize
            sizes = [QSize(16, 16), QSize(22, 22), QSize(24, 24), QSize(32, 32), QSize(48, 48)]

        new_icon = QIcon()
        
        for size in sizes:
            pixmap = icon.pixmap(size)
            if pixmap.isNull():
                continue

            # Create a new pixmap with the target color
            colored_pixmap = QPixmap(pixmap.size())
            colored_pixmap.fill(Qt.GlobalColor.transparent)

            painter = QPainter(colored_pixmap)
            # Draw the original pixmap as a mask
            painter.drawPixmap(0, 0, pixmap)
            # Apply color using SourceIn composition (only affects non-transparent pixels)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(colored_pixmap.rect(), color)
            painter.end()

            new_icon.addPixmap(colored_pixmap)

        return new_icon if not new_icon.isNull() else icon

    def refreshBorrowedDocker(self):
        if not self.sourceDocker:
            return

        self.pad.returnDocker()
        self.pad.borrowDocker(self.sourceDocker)
        self._ensureDockerHidden()
        self.pad.adjustToView()

    def close(self):
        try:
            self.sourceDocker.visibilityChanged.disconnect(self._onDockerVisibilityChanged)
        except (TypeError, RuntimeError):
            pass
        self.dockerAction.setEnabled(True)
        return self.pad.close()
