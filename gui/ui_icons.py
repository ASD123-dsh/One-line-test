#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""界面线性图标、状态徽标和分隔握柄；仅使用 Qt 绘图，不增加图片依赖。"""

from functools import lru_cache
from math import cos, pi, sin

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PyQt5.QtWidgets import QLabel, QSplitter, QSplitterHandle
from gui.soft_theme import PALETTE


def _draw_symbol(painter, name):
    """在统一的 24×24 逻辑画布描画常用图标，样式跟随控件而不跟随业务。"""
    path = QPainterPath()
    if name in ("refresh", "loop"):
        painter.drawArc(QRectF(4, 4, 16, 16), 35 * 16, 285 * 16)
        painter.drawPolyline(QPolygonF([QPointF(17, 3), QPointF(21, 6), QPointF(17, 8)]))
        if name == "loop":
            painter.drawPolyline(QPolygonF([QPointF(7, 21), QPointF(3, 18), QPointF(7, 16)]))
    elif name == "copy":
        painter.drawRoundedRect(QRectF(8, 5, 11, 16), 1.5, 1.5)
        path.moveTo(15, 5)
        path.lineTo(15, 3)
        path.lineTo(4, 3)
        path.lineTo(4, 18)
        path.lineTo(8, 18)
    elif name in ("file", "empty"):
        path.moveTo(6, 2)
        path.lineTo(15, 2)
        path.lineTo(20, 7)
        path.lineTo(20, 21)
        path.lineTo(4, 21)
        path.lineTo(4, 2)
        path.closeSubpath()
        path.moveTo(15, 2)
        path.lineTo(15, 7)
        path.lineTo(20, 7)
        for y, right in ((11, 16), (15, 16), (18, 11)):
            path.moveTo(8, y)
            path.lineTo(right, y)
    elif name == "trash":
        painter.drawLine(4, 6, 20, 6)
        painter.drawRoundedRect(QRectF(6, 6, 12, 15), 1.5, 1.5)
        painter.drawLine(9, 3, 15, 3)
        painter.drawLine(9, 3, 9, 6)
        painter.drawLine(15, 3, 15, 6)
        painter.drawLine(10, 10, 10, 17)
        painter.drawLine(14, 10, 14, 17)
    elif name == "settings":
        points = []
        for index in range(32):
            radius = 9.5 if index % 4 in (0, 1) else 7.5
            angle = index * pi / 16
            points.append(QPointF(12 + radius * cos(angle), 12 + radius * sin(angle)))
        painter.drawPolygon(QPolygonF(points))
        painter.drawEllipse(QRectF(8.5, 8.5, 7, 7))
    elif name == "edit":
        painter.drawPolygon(QPolygonF([QPointF(4, 16), QPointF(16, 4), QPointF(20, 8), QPointF(8, 20), QPointF(3, 21)]))
        painter.drawLine(13, 7, 17, 11)
    elif name == "eye":
        path.moveTo(2, 12)
        path.cubicTo(7, 3, 17, 3, 22, 12)
        path.cubicTo(17, 21, 7, 21, 2, 12)
        painter.drawEllipse(QRectF(8, 8, 8, 8))
    elif name == "alert":
        painter.drawEllipse(QRectF(3, 3, 18, 18))
        painter.drawLine(12, 7, 12, 13)
        painter.drawPoint(12, 17)
    painter.drawPath(path)


def _symbol_pixmap(name, color, size):
    """在透明的双倍分辨率画布绘制图标，普通控件和按钮共用原有形状。"""
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.scale(size / 24, size / 24)
    pen = QPen(QColor(color), 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    _draw_symbol(painter, name)
    painter.end()
    return pixmap


@lru_cache(maxsize=64)
def ui_icon(name, color="#263c4b", size=18):
    """缓存高分辨率图标，保留浅色背景控件的原接口和默认深色。"""
    return QIcon(_symbol_pixmap(name, color, size))


@lru_cache(maxsize=32)
def button_icon(name, size=18):
    """修复绿色按钮图标难辨：启用时用白色，禁用时用灰色，不改变尺寸。"""
    icon = QIcon()
    normal = _symbol_pixmap(name, PALETTE["button_icon"], size)
    for mode in (QIcon.Normal, QIcon.Active, QIcon.Selected):
        icon.addPixmap(normal, mode)
    icon.addPixmap(_symbol_pixmap(name, PALETTE["button_icon_disabled"], size), QIcon.Disabled)
    return icon


class StatusBadge(QLabel):
    """保留 QLabel 原文本接口，图标只通过绘制补充，不混入日志和状态文字。"""

    def __init__(self, text, icon="status", parent=None):
        """给图标预留空间，实际色调继续由统一样式属性决定。"""
        super().__init__(text, parent)
        self._icon_name = icon
        self.setContentsMargins(20, 0, 0, 0)

    def set_icon(self, name):
        """切换预览/编辑等静态图标，不引入动画或额外计时器。"""
        if self._icon_name != name:
            self._icon_name = name
            self.update()

    def paintEvent(self, event):
        """在文本左侧绘制连接圆点或状态线性图标。"""
        super().paintEvent(event)
        tone = self.property("badgeTone")
        color = {"ready": PALETTE["badge_ready"], "running": PALETTE["badge_running"],
                 "warning": PALETTE["badge_running"], "error": PALETTE["badge_error"]}.get(tone, PALETTE["badge_muted"])
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self._icon_name == "connection":
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(PALETTE["disconnected"] if tone != "ready" else PALETTE["connected"]))
            painter.drawEllipse(QRectF(9, self.height() / 2 - 4.5, 9, 9))
        else:
            name = self._icon_name
            if name == "status":
                name = "loop" if tone == "running" else "alert" if tone in ("warning", "error") else "eye"
            ui_icon(name, color, 16).paint(painter, 6, (self.height() - 16) // 2, 16, 16)
        painter.end()


class _GripHandle(QSplitterHandle):
    """为上下分隔条提供轻微双线，保留 Qt 原有拖动操作。"""

    def paintEvent(self, event):
        """只绘制握柄，不处理鼠标、尺寸或业务状态。"""
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setPen(QPen(QColor(PALETTE["grip"]), 1))
        middle = self.width() // 2
        painter.drawLine(middle - 10, self.height() // 2 - 1, middle + 10, self.height() // 2 - 1)
        painter.drawLine(middle - 10, self.height() // 2 + 2, middle + 10, self.height() // 2 + 2)
        painter.end()


class GripSplitter(QSplitter):
    """仅改变上下分隔条外观，其余行为与原 QSplitter 相同。"""

    def createHandle(self):
        """由 Qt 创建可拖动的本窗口握柄，不建立额外事件循环。"""
        return _GripHandle(self.orientation(), self)
