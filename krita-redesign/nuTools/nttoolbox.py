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
from PyQt6.QtGui import QIcon, QPalette, QPixmap, QPainter, QColor, QImage
from PyQt6.QtWidgets import QMdiArea, QDockWidget, QToolButton, QApplication
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
        """Manually recolor icons to match the new theme."""
        # Use simple palette lookup - prefer global application palette for theme changes
        app = QApplication.instance()
        if app:
            palette = app.palette()
        elif palette is None:
            palette = self.qWin.palette()

        # Get the target text color (foreground)
        # Try WindowText first, then ButtonText as fallback
        text_color = palette.color(QPalette.ColorGroup.Active, QPalette.ColorRole.WindowText)
        
        # Debug safety check: if color seems invalid (alpha 0), fallback to white/black based on window color
        if text_color.alpha() == 0:
            window_color = palette.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Window)
            if window_color.value() < 128:
                text_color = QColor(255, 255, 255) # Dark theme -> Light text
            else:
                text_color = QColor(0, 0, 0) # Light theme -> Dark text

        for button in self.pad.findChildren(QToolButton):
            # Store original icon and iconSize on first encounter
            if not hasattr(button, '_original_icon') or button._original_icon is None:
                button._original_icon = button.icon()
                button._original_icon_size = button.iconSize()
                
                # If the button has no icon (e.g. text only), skip
                if button._original_icon.isNull():
                    continue

            # Recolor the ORIGINAL icon to match the new theme
            original_icon = button._original_icon
            original_size = button._original_icon_size
            
            # Use the original size for the pixmap
            recolored_icon = self._recolorIcon(original_icon, text_color, original_size)
            if recolored_icon:
                button.setIcon(recolored_icon)
                # Explicitly preserve the icon size
                button.setIconSize(original_size)

            button.update()

    def _recolorIcon(self, icon, color, size):
        """Recolor an icon's pixmap to the specified color while preserving alpha."""
        pixmap = icon.pixmap(size)
        if pixmap.isNull():
            return None

        # Convert to ARGB32 to ensure we can manipulate pixels correctly
        image = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
        
        # Get the target color components
        r, g, b = color.red(), color.green(), color.blue()
        
        # Iterate over all pixels and recolor while preserving alpha
        for y in range(image.height()):
            for x in range(image.width()):
                pixel = image.pixelColor(x, y)
                alpha = pixel.alpha()
                if alpha > 0:  # Only modify non-transparent pixels
                    # Create new color with target RGB and original Alpha
                    new_color = QColor(r, g, b, alpha)
                    image.setPixelColor(x, y, new_color)
        
        return QIcon(QPixmap.fromImage(image))

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
