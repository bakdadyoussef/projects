#!/usr/bin/env python3
"""Boardmind — freeform notes on a detective board. PySide6."""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from PySide6.QtCore import (
    QPointF,
    QRectF,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QFont,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QComboBox,
    QFileDialog,
    QFontComboBox,
    QFrame,
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

APP_NAME = "Boardmind"
HANDLE = 10
ROT_GAP = 22


def uid() -> str:
    return uuid.uuid4().hex[:12]


class BoardObject(QGraphicsObject):
    """Movable, rotatable item with resize + rotate handles."""

    changed = Signal()

    def __init__(self, kind: str, item_id: str | None = None):
        super().__init__()
        self.kind = kind
        self.item_id = item_id or uid()
        self._w = 220.0
        self._h = 140.0
        self._resizing = False
        self._rotating = False
        self._resize_origin = QPointF()
        self._start_size = (self._w, self._h)
        self._start_rot = 0.0
        self._press_angle = 0.0
        self.title = "Untitled"
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.setTransformOriginPoint(self._w / 2, self._h / 2)

    def size(self) -> tuple[float, float]:
        return self._w, self._h

    def set_size(self, w: float, h: float) -> None:
        self.prepareGeometryChange()
        self._w = max(48.0, w)
        self._h = max(36.0, h)
        self.setTransformOriginPoint(self._w / 2, self._h / 2)
        self.update()

    def boundingRect(self) -> QRectF:
        pad = ROT_GAP + HANDLE
        return QRectF(-pad, -pad, self._w + pad * 2, self._h + pad * 2)

    def shape_rect(self) -> QRectF:
        return QRectF(0, 0, self._w, self._h)

    def paint_handles(self, painter: QPainter) -> None:
        if not self.isSelected():
            return
        painter.setPen(QPen(QColor("#e8a54b"), 1.2))
        painter.setBrush(QBrush(QColor("#1c1917")))
        r = self.shape_rect()
        painter.drawRect(r)
        for p in self._corners():
            painter.drawRect(QRectF(p.x() - HANDLE / 2, p.y() - HANDLE / 2, HANDLE, HANDLE))
        top = QPointF(self._w / 2, 0)
        knob = QPointF(self._w / 2, -ROT_GAP)
        painter.drawLine(top, knob)
        painter.setBrush(QBrush(QColor("#e8a54b")))
        painter.drawEllipse(knob, HANDLE / 2 + 1, HANDLE / 2 + 1)

    def _corners(self) -> list[QPointF]:
        return [
            QPointF(0, 0),
            QPointF(self._w, 0),
            QPointF(self._w, self._h),
            QPointF(0, self._h),
        ]

    def _hit_handle(self, pos: QPointF) -> str | None:
        if not self.isSelected():
            return None
        knob = QPointF(self._w / 2, -ROT_GAP)
        if (pos - knob).manhattanLength() <= HANDLE + 4:
            return "rot"
        for name, p in zip(("tl", "tr", "br", "bl"), self._corners()):
            if (pos - p).manhattanLength() <= HANDLE + 3:
                return name
        return None

    def mousePressEvent(self, event):
        h = self._hit_handle(event.pos())
        if h == "rot":
            self._rotating = True
            center = QPointF(self._w / 2, self._h / 2)
            v = event.pos() - center
            self._press_angle = _angle(v)
            self._start_rot = self.rotation()
            event.accept()
            return
        if h in ("tl", "tr", "br", "bl"):
            self._resizing = True
            self._handle = h
            self._resize_origin = event.scenePos()
            self._start_size = (self._w, self._h)
            self._start_pos = self.pos()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._rotating:
            center = QPointF(self._w / 2, self._h / 2)
            v = event.pos() - center
            delta = _angle(v) - self._press_angle
            self.setRotation(self._start_rot + delta)
            self.changed.emit()
            event.accept()
            return
        if self._resizing:
            delta = event.scenePos() - self._resize_origin
            # approximate in local axes
            rad = self.rotation() * 3.14159265 / 180.0
            import math

            dx = delta.x() * math.cos(rad) + delta.y() * math.sin(rad)
            dy = -delta.x() * math.sin(rad) + delta.y() * math.cos(rad)
            w, h = self._start_size
            if self._handle in ("tr", "br"):
                w = self._start_size[0] + dx
            else:
                w = self._start_size[0] - dx
            if self._handle in ("bl", "br"):
                h = self._start_size[1] + dy
            else:
                h = self._start_size[1] - dy
            self.set_size(w, h)
            self.changed.emit()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._resizing = False
        self._rotating = False
        super().mouseReleaseEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.changed.emit()
        return super().itemChange(change, value)

    def to_dict(self) -> dict:
        return {
            "id": self.item_id,
            "kind": self.kind,
            "title": self.title,
            "x": self.pos().x(),
            "y": self.pos().y(),
            "w": self._w,
            "h": self._h,
            "rot": self.rotation(),
            "z": self.zValue(),
        }

    def apply_common(self, data: dict) -> None:
        self.set_size(float(data.get("w", self._w)), float(data.get("h", self._h)))
        self.setPos(float(data.get("x", 0)), float(data.get("y", 0)))
        self.setRotation(float(data.get("rot", 0)))
        self.setZValue(float(data.get("z", 0)))
        self.title = data.get("title") or self.title


def _angle(v: QPointF) -> float:
    import math

    return math.degrees(math.atan2(v.y(), v.x()))


class NoteItem(BoardObject):
    def __init__(self, item_id: str | None = None):
        super().__init__("note", item_id)
        self.text = "New note"
        self.font_family = "Georgia"
        self.font_size = 15
        self.text_color = "#1c1917"
        self.bg = "#f6f1e7"
        self.accent = "#e8a54b"
        self._w, self._h = 240.0, 160.0
        self.setTransformOriginPoint(self._w / 2, self._h / 2)
        self.title = "New note"

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        r = self.shape_rect()
        path = QPainterPath()
        path.addRoundedRect(r, 8, 8)
        painter.fillPath(path, QColor(self.bg))
        painter.setPen(QPen(QColor(self.accent), 4))
        painter.drawLine(QPointF(10, 14), QPointF(10, self._h - 14))
        painter.setPen(QPen(QColor("#00000022")))
        painter.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)
        font = QFont(self.font_family, self.font_size)
        painter.setFont(font)
        painter.setPen(QColor(self.text_color))
        text_rect = QRectF(22, 12, self._w - 32, self._h - 24)
        painter.drawText(text_rect, Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignTop, self.text)
        self.paint_handles(painter)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d.update(
            {
                "text": self.text,
                "font_family": self.font_family,
                "font_size": self.font_size,
                "text_color": self.text_color,
                "bg": self.bg,
                "accent": self.accent,
            }
        )
        return d

    def load(self, data: dict) -> None:
        self.apply_common(data)
        self.text = data.get("text", "")
        self.font_family = data.get("font_family", "Georgia")
        self.font_size = int(data.get("font_size", 15))
        self.text_color = data.get("text_color", "#1c1917")
        self.bg = data.get("bg", "#f6f1e7")
        self.accent = data.get("accent", "#e8a54b")
        first = (self.text or "Untitled").strip().splitlines()
        self.title = (first[0][:42] if first else "Untitled") or "Untitled"


class ImageItem(BoardObject):
    def __init__(self, path: str = "", item_id: str | None = None):
        super().__init__("image", item_id)
        self.path = path
        self._pix = QPixmap()
        self._w, self._h = 220.0, 160.0
        self.title = "Image"
        if path:
            self.load_path(path)

    def load_path(self, path: str) -> None:
        self.path = path
        self._pix = QPixmap(path)
        self.title = Path(path).name
        if not self._pix.isNull():
            self.set_size(min(360, self._pix.width()), min(280, self._pix.height()))

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = self.shape_rect()
        painter.setBrush(QColor("#11100e"))
        painter.setPen(QPen(QColor("#3f3a34"), 1))
        painter.drawRoundedRect(r, 6, 6)
        if not self._pix.isNull():
            painter.drawPixmap(r.adjusted(4, 4, -4, -4), self._pix, QRectF(self._pix.rect()))
        else:
            painter.setPen(QColor("#a8a29e"))
            painter.drawText(r, Qt.AlignmentFlag.AlignCenter, "Missing image")
        self.paint_handles(painter)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["path"] = self.path
        return d


class ShapeItem(BoardObject):
    def __init__(self, shape: str = "rect", item_id: str | None = None):
        super().__init__("shape", item_id)
        self.shape = shape  # rect, ellipse, diamond, sticky
        self.fill = "#3f3428" if shape != "sticky" else "#f3d27a"
        self.stroke = "#e8a54b"
        self.text = ""
        self.font_family = "Georgia"
        self.font_size = 14
        self.text_color = "#1c1917" if shape == "sticky" else "#f6f1e7"
        self._w, self._h = (160, 100) if shape != "sticky" else (150, 150)
        self.title = shape.capitalize()

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.shape_rect().adjusted(1, 1, -1, -1)
        painter.setPen(QPen(QColor(self.stroke), 2))
        painter.setBrush(QColor(self.fill))
        if self.shape == "ellipse":
            painter.drawEllipse(r)
        elif self.shape == "diamond":
            path = QPainterPath()
            path.moveTo(r.center().x(), r.top())
            path.lineTo(r.right(), r.center().y())
            path.lineTo(r.center().x(), r.bottom())
            path.lineTo(r.left(), r.center().y())
            path.closeSubpath()
            painter.drawPath(path)
        else:
            painter.drawRoundedRect(r, 6, 6)
        if self.text:
            painter.setPen(QColor(self.text_color))
            painter.setFont(QFont(self.font_family, self.font_size))
            painter.drawText(r.adjusted(10, 8, -10, -8), Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignCenter, self.text)
        self.paint_handles(painter)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d.update(
            {
                "shape": self.shape,
                "fill": self.fill,
                "stroke": self.stroke,
                "text": self.text,
                "font_family": self.font_family,
                "font_size": self.font_size,
                "text_color": self.text_color,
            }
        )
        return d

    def load(self, data: dict) -> None:
        self.apply_common(data)
        self.shape = data.get("shape", "rect")
        self.fill = data.get("fill", self.fill)
        self.stroke = data.get("stroke", self.stroke)
        self.text = data.get("text", "")
        self.font_family = data.get("font_family", "Georgia")
        self.font_size = int(data.get("font_size", 14))
        self.text_color = data.get("text_color", self.text_color)
        self.title = (self.text.splitlines() or [self.shape])[0][:42]


class YarnItem(QGraphicsItem):
    """Red string between two board objects."""

    def __init__(self, a: BoardObject, b: BoardObject, item_id: str | None = None):
        super().__init__()
        self.a = a
        self.b = b
        self.item_id = item_id or uid()
        self.setZValue(-1)
        a.changed.connect(self._refresh)
        b.changed.connect(self._refresh)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)

    def _refresh(self):
        self.prepareGeometryChange()
        self.update()

    def _points(self) -> tuple[QPointF, QPointF]:
        return self.a.sceneBoundingRect().center(), self.b.sceneBoundingRect().center()

    def boundingRect(self) -> QRectF:
        p1, p2 = self._points()
        return QRectF(p1, p2).normalized().adjusted(-12, -12, 12, 12)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        p1, p2 = self._points()
        color = QColor("#e24b4b") if self.isSelected() else QColor("#c44536")
        pen = QPen(color, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        path = QPainterPath(p1)
        mid = (p1 + p2) / 2
        sag = QPointF(0, min(40, abs(p2.x() - p1.x()) * 0.08 + 12))
        path.quadTo(mid + sag, p2)
        painter.drawPath(path)
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(p1, 4, 4)
        painter.drawEllipse(p2, 4, 4)

    def to_dict(self) -> dict:
        return {"id": self.item_id, "kind": "yarn", "a": self.a.item_id, "b": self.b.item_id}


class BoardView(QGraphicsView):
    selection_changed = Signal(object)
    request_edit = Signal(object)

    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.scene().setSceneRect(-4000, -3000, 8000, 6000)
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
            | QPainter.RenderHint.TextAntialiasing
        )
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setBackgroundBrush(QColor("#241f1a"))
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._panning = False
        self._pan_start = QPointF()
        self.link_mode = False
        self._link_from: BoardObject | None = None
        self.scene().selectionChanged.connect(self._on_sel)
        self.yarns: list[YarnItem] = []

    def _on_sel(self):
        items = [i for i in self.scene().selectedItems() if isinstance(i, BoardObject)]
        self.selection_changed.emit(items[0] if len(items) == 1 else None)

    def wheelEvent(self, event):
        factor = 1.12 if event.angleDelta().y() > 0 else 1 / 1.12
        self.scale(factor, factor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton or (
            event.button() == Qt.MouseButton.LeftButton and event.modifiers() & Qt.KeyboardModifier.SpaceModifier
        ):
            self._panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        if self.link_mode and event.button() == Qt.MouseButton.LeftButton:
            item = self._board_at(event.position())
            if isinstance(item, BoardObject):
                if self._link_from is None:
                    self._link_from = item
                    item.setSelected(True)
                elif item is not self._link_from:
                    self.add_yarn(self._link_from, item)
                    self._link_from = None
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()
            self.horizontalScrollBar().setValue(int(self.horizontalScrollBar().value() - delta.x()))
            self.verticalScrollBar().setValue(int(self.verticalScrollBar().value() - delta.y()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._panning and event.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.LeftButton):
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        item = self._board_at(event.position())
        if isinstance(item, (NoteItem, ShapeItem)):
            self.request_edit.emit(item)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _board_at(self, view_pos) -> QGraphicsItem | None:
        for it in self.items(view_pos.toPoint()):
            if isinstance(it, BoardObject):
                return it
        return None

    def drawBackground(self, painter: QPainter, rect: QRectF):
        painter.fillRect(rect, QColor("#241f1a"))
        pen = QPen(QColor("#3a332c"))
        pen.setWidth(0)
        painter.setPen(pen)
        step = 48
        left = int(rect.left()) - (int(rect.left()) % step)
        top = int(rect.top()) - (int(rect.top()) % step)
        x = left
        while x < rect.right():
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
            x += step
        y = top
        while y < rect.bottom():
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            y += step

    def add_item(self, item: BoardObject, pos: QPointF | None = None):
        self.scene().addItem(item)
        if pos is not None:
            item.setPos(pos)
        else:
            center = self.mapToScene(self.viewport().rect().center())
            item.setPos(center - QPointF(item._w / 2, item._h / 2))
        item.setSelected(True)
        return item

    def add_yarn(self, a: BoardObject, b: BoardObject) -> YarnItem | None:
        for y in self.yarns:
            if {y.a, y.b} == {a, b}:
                return None
        yarn = YarnItem(a, b)
        self.scene().addItem(yarn)
        self.yarns.append(yarn)
        return yarn

    def board_items(self) -> list[BoardObject]:
        return [i for i in self.scene().items() if isinstance(i, BoardObject)]

    def remove_selected(self):
        selected = list(self.scene().selectedItems())
        ids = {i.item_id for i in selected if isinstance(i, BoardObject)}
        doomed_yarn = [
            y
            for y in self.yarns
            if y in selected or y.a.item_id in ids or y.b.item_id in ids
        ]
        for y in doomed_yarn:
            self.scene().removeItem(y)
            if y in self.yarns:
                self.yarns.remove(y)
        for i in selected:
            if isinstance(i, BoardObject):
                self.scene().removeItem(i)


class Inspector(QWidget):
    def __init__(self, view: BoardView):
        super().__init__()
        self.view = view
        self.item: BoardObject | None = None
        self._lock = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)
        self.head = QLabel("Nothing selected")
        self.head.setObjectName("section")
        lay.addWidget(self.head)

        self.font_box = QFontComboBox()
        self.font_box.currentFontChanged.connect(self._font)
        lay.addWidget(QLabel("Font"))
        lay.addWidget(self.font_box)

        row = QHBoxLayout()
        self.size = QSpinBox()
        self.size.setRange(8, 96)
        self.size.valueChanged.connect(self._size)
        row.addWidget(QLabel("Size"))
        row.addWidget(self.size)
        lay.addLayout(row)

        self.rot = QSlider(Qt.Orientation.Horizontal)
        self.rot.setRange(-180, 180)
        self.rot.valueChanged.connect(self._rot)
        lay.addWidget(QLabel("Rotate"))
        lay.addWidget(self.rot)

        btn_row = QHBoxLayout()
        self.fg = QPushButton("Text color")
        self.bg = QPushButton("Paper")
        self.fg.clicked.connect(lambda: self._color("text"))
        self.bg.clicked.connect(lambda: self._color("bg"))
        btn_row.addWidget(self.fg)
        btn_row.addWidget(self.bg)
        lay.addLayout(btn_row)

        self.front = QPushButton("Bring forward")
        self.back = QPushButton("Send backward")
        self.front.clicked.connect(lambda: self._z(1))
        self.back.clicked.connect(lambda: self._z(-1))
        lay.addWidget(self.front)
        lay.addWidget(self.back)
        lay.addStretch(1)

        for b in (self.fg, self.bg, self.front, self.back):
            b.setCursor(Qt.CursorShape.PointingHandCursor)

    def show_item(self, item: BoardObject | None):
        self.item = item
        self._lock = True
        if item is None:
            self.head.setText("Nothing selected")
            self._lock = False
            return
        self.head.setText(item.title or item.kind)
        family = getattr(item, "font_family", "Georgia")
        self.font_box.setCurrentFont(QFont(family))
        self.size.setValue(int(getattr(item, "font_size", 15)))
        self.rot.setValue(int(item.rotation()))
        self._lock = False

    def _alive(self) -> BoardObject | None:
        if self._lock or self.item is None or self.item.scene() is None:
            return None
        return self.item

    def _font(self, font: QFont):
        item = self._alive()
        if item and hasattr(item, "font_family"):
            item.font_family = font.family()
            item.update()

    def _size(self, value: int):
        item = self._alive()
        if item and hasattr(item, "font_size"):
            item.font_size = value
            item.update()

    def _rot(self, value: int):
        item = self._alive()
        if item:
            item.setRotation(value)

    def _color(self, which: str):
        item = self._alive()
        if not item:
            return
        current = QColor(getattr(item, "text_color", "#1c1917") if which == "text" else getattr(item, "bg", getattr(item, "fill", "#f6f1e7")))
        color = QColorDialog.getColor(current, self, "Pick color")
        if not color.isValid():
            return
        hex_c = color.name()
        if which == "text" and hasattr(item, "text_color"):
            item.text_color = hex_c
        elif isinstance(item, NoteItem):
            item.bg = hex_c
        elif isinstance(item, ShapeItem):
            item.fill = hex_c
        item.update()

    def _z(self, delta: int):
        item = self._alive()
        if item:
            item.setZValue(item.zValue() + delta)


class EditorDialog(QWidget):
    """Inline editor docked under the toolbar area via the main window."""

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.edit = QTextEdit()
        self.edit.setPlaceholderText("Write the note…")
        lay.addWidget(self.edit)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1280, 800)
        self.project_dir: Path | None = None
        self.view = BoardView()
        self.inspector = Inspector(self.view)
        self.notes = QListWidget()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search notes")
        self.search.textChanged.connect(self._filter_notes)
        self.editor = QTextEdit()
        self.editor.setPlaceholderText("Double-click a note on the board, or select one in the list, then write here.")
        self._editing: NoteItem | ShapeItem | None = None
        self.editor.textChanged.connect(self._editor_changed)

        self._build_ui()
        self._build_menu()
        self.view.selection_changed.connect(self._selected)
        self.view.request_edit.connect(self._begin_edit)
        self.notes.currentItemChanged.connect(self._list_picked)
        self._seed()

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        side = QWidget()
        side.setObjectName("side")
        side.setFixedWidth(280)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(14, 14, 14, 14)
        brand = QLabel("BOARDMIND")
        brand.setObjectName("brand")
        sub = QLabel("Notes on a wall.\nDrag, resize, rotate, connect.")
        sub.setObjectName("sub")
        sl.addWidget(brand)
        sl.addWidget(sub)
        sl.addWidget(self.search)

        tools = QHBoxLayout()
        for label, slot in (
            ("Note", self.add_note),
            ("Image", self.add_image),
            ("Shape", self.add_shape_menu),
        ):
            b = QPushButton(label)
            b.clicked.connect(slot)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            tools.addWidget(b)
        sl.addLayout(tools)

        sl.addWidget(QLabel("Library"))
        sl.addWidget(self.notes, 1)

        yarn_btn = QPushButton("Yarn link")
        yarn_btn.setCheckable(True)
        yarn_btn.setObjectName("yarn")
        yarn_btn.toggled.connect(self._toggle_link)
        yarn_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        sl.addWidget(yarn_btn)
        self.yarn_btn = yarn_btn

        delete = QPushButton("Delete selected")
        delete.clicked.connect(self.view.remove_selected)
        delete.clicked.connect(self.refresh_list)
        delete.setCursor(Qt.CursorShape.PointingHandCursor)
        sl.addWidget(delete)

        right = QWidget()
        right.setObjectName("side")
        right.setFixedWidth(240)
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        title = QLabel("INSPECTOR")
        title.setObjectName("section")
        title.setContentsMargins(12, 14, 12, 0)
        rl.addWidget(title)
        rl.addWidget(self.inspector)

        center = QWidget()
        cl = QVBoxLayout(center)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        hint = QLabel("  Scroll to zoom   ·   Middle-drag to pan   ·   Drag corners to resize   ·   Gold knob rotates   ·   Double-click to edit")
        hint.setObjectName("hint")
        hint.setFixedHeight(28)
        cl.addWidget(hint)
        cl.addWidget(self.view, 1)
        self.editor.setFixedHeight(140)
        cl.addWidget(self.editor)

        outer.addWidget(side)
        outer.addWidget(center, 1)
        outer.addWidget(right)

    def _build_menu(self):
        file = self.menuBar().addMenu("File")
        save = QAction("Save project", self)
        save.setShortcut(QKeySequence.StandardKey.Save)
        save.triggered.connect(self.save_project)
        load = QAction("Open project", self)
        load.setShortcut(QKeySequence.StandardKey.Open)
        load.triggered.connect(self.load_project)
        file.addAction(save)
        file.addAction(load)
        edit = self.menuBar().addMenu("Edit")
        dele = QAction("Delete", self)
        dele.setShortcut(QKeySequence.StandardKey.Delete)
        dele.triggered.connect(self.view.remove_selected)
        dele.triggered.connect(self.refresh_list)
        edit.addAction(dele)

    def _seed(self):
        n = NoteItem()
        n.text = "The case starts here\n\nPin notes, photos, and shapes. Spin the gold knob to rotate. Stretch the corners. Yarn two cards together."
        n.title = "The case starts here"
        n.font_size = 15
        self.view.add_item(n, QPointF(-80, -40))
        s = ShapeItem("sticky")
        s.text = "Suspect seen\nat the station"
        s.title = "Suspect seen"
        self.view.add_item(s, QPointF(220, 40))
        self.view.add_yarn(n, s)
        self.refresh_list()
        self.view.centerOn(80, 40)

    def add_note(self):
        n = NoteItem()
        n.text = "Untitled note"
        n.title = "Untitled note"
        self.view.add_item(n)
        self.refresh_list()
        self._begin_edit(n)

    def add_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Add image", "", "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        if not path:
            return
        stored = path
        if self.project_dir:
            img_dir = self.project_dir / "images"
            img_dir.mkdir(parents=True, exist_ok=True)
            dest = img_dir / f"{uid()}{Path(path).suffix.lower()}"
            shutil.copy(path, dest)
            stored = str(dest)
        item = ImageItem(stored)
        self.view.add_item(item)
        self.refresh_list()

    def add_shape_menu(self):
        # cycle through shapes for a single toolbar button
        order = ["rect", "ellipse", "diamond", "sticky"]
        shape = order[getattr(self, "_shape_i", 0) % 4]
        self._shape_i = getattr(self, "_shape_i", 0) + 1
        s = ShapeItem(shape)
        if shape == "sticky":
            s.text = "Sticky"
        self.view.add_item(s)
        self.refresh_list()

    def _toggle_link(self, on: bool):
        self.view.link_mode = on
        self.view._link_from = None
        self.yarn_btn.setText("Yarn: pick two cards" if on else "Yarn link")
        self.view.setCursor(Qt.CursorShape.CrossCursor if on else Qt.CursorShape.ArrowCursor)

    def _selected(self, item):
        self.inspector.show_item(item)
        if isinstance(item, (NoteItem, ShapeItem)):
            self._editing = item
            self.editor.blockSignals(True)
            self.editor.setPlainText(item.text)
            self.editor.blockSignals(False)
            self._select_in_list(item)
        else:
            self._editing = None

    def _begin_edit(self, item):
        self._selected(item)
        self.editor.setFocus()

    def _editor_changed(self):
        item = self._editing
        if item is None or item.scene() is None:
            return
        item.text = self.editor.toPlainText()
        first = item.text.strip().splitlines()
        item.title = (first[0][:42] if first else "Untitled") or "Untitled"
        item.update()
        self._rename_in_list(item)

    def refresh_list(self):
        self.notes.clear()
        items = sorted(self.view.board_items(), key=lambda i: i.title.lower())
        for it in items:
            row = QListWidgetItem(f"{it.kind[:1].upper()}  {it.title}")
            row.setData(Qt.ItemDataRole.UserRole, it.item_id)
            self.notes.addItem(row)
        self._filter_notes(self.search.text())

    def _rename_in_list(self, item: BoardObject):
        for i in range(self.notes.count()):
            row = self.notes.item(i)
            if row.data(Qt.ItemDataRole.UserRole) == item.item_id:
                row.setText(f"{item.kind[:1].upper()}  {item.title}")
                return

    def _select_in_list(self, item: BoardObject):
        for i in range(self.notes.count()):
            row = self.notes.item(i)
            if row.data(Qt.ItemDataRole.UserRole) == item.item_id:
                self.notes.blockSignals(True)
                self.notes.setCurrentItem(row)
                self.notes.blockSignals(False)
                return

    def _list_picked(self, current, _prev):
        if not current:
            return
        item_id = current.data(Qt.ItemDataRole.UserRole)
        for it in self.view.board_items():
            if it.item_id == item_id:
                self.view.scene().clearSelection()
                it.setSelected(True)
                self.view.centerOn(it)
                return

    def _filter_notes(self, text: str):
        q = text.lower().strip()
        for i in range(self.notes.count()):
            row = self.notes.item(i)
            row.setHidden(q not in row.text().lower())

    def save_project(self):
        if self.project_dir is None:
            path = QFileDialog.getExistingDirectory(self, "Choose a folder for the project")
            if not path:
                return
            self.project_dir = Path(path) / "BoardmindProject"
            self.project_dir.mkdir(parents=True, exist_ok=True)
        self._write()

    def _write(self):
        assert self.project_dir
        img_dir = self.project_dir / "images"
        img_dir.mkdir(exist_ok=True)
        payload = {"items": [], "yarn": []}
        for it in self.view.board_items():
            data = it.to_dict()
            if isinstance(it, ImageItem) and it.path and Path(it.path).exists():
                dest_name = Path(it.path).name
                dest = img_dir / dest_name
                if Path(it.path).resolve() != dest.resolve():
                    shutil.copy(it.path, dest)
                data["path"] = f"images/{dest.name}"
            payload["items"].append(data)
        for y in self.view.yarns:
            payload["yarn"].append(y.to_dict())
        (self.project_dir / "board.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.setWindowTitle(f"{APP_NAME} — {self.project_dir.name}")

    def load_project(self):
        path = QFileDialog.getExistingDirectory(self, "Open a Boardmind project folder")
        if not path:
            return
        folder = Path(path)
        board = folder / "board.json"
        if not board.exists():
            QMessageBox.warning(self, APP_NAME, "That folder has no board.json.")
            return
        self.project_dir = folder
        data = json.loads(board.read_text(encoding="utf-8"))
        self.view.scene().clear()
        self.view.yarns.clear()
        by_id: dict[str, BoardObject] = {}
        for raw in data.get("items", []):
            kind = raw.get("kind")
            if kind == "note":
                item = NoteItem(raw.get("id"))
                item.load(raw)
            elif kind == "image":
                rel = raw.get("path", "")
                full = str((folder / rel) if rel and not Path(rel).is_absolute() else rel)
                item = ImageItem(full, raw.get("id"))
                item.apply_common(raw)
            elif kind == "shape":
                item = ShapeItem(raw.get("shape", "rect"), raw.get("id"))
                item.load(raw)
            else:
                continue
            self.view.scene().addItem(item)
            by_id[item.item_id] = item
        for raw in data.get("yarn", []):
            a = by_id.get(raw.get("a"))
            b = by_id.get(raw.get("b"))
            if a and b:
                self.view.add_yarn(a, b)
        self.refresh_list()
        self.setWindowTitle(f"{APP_NAME} — {folder.name}")


STYLE = """
QMainWindow, QWidget { background: #1c1917; color: #f5f0e8; font-family: "Segoe UI", "Helvetica Neue", sans-serif; font-size: 13px; }
QMenuBar { background: #1c1917; color: #e7e5e4; }
QMenuBar::item:selected { background: #44403c; }
QMenu { background: #292524; color: #f5f0e8; border: 1px solid #44403c; }
#side { background: #231f1b; border-right: 1px solid #3a332c; }
#brand { font-size: 18px; letter-spacing: 3px; font-weight: 700; color: #f3d7a1; }
#sub, #hint { color: #a8a29e; }
#section { color: #e8a54b; font-weight: 700; letter-spacing: 1px; }
#hint { background: #1a1613; }
QLineEdit, QTextEdit, QSpinBox, QComboBox, QFontComboBox {
  background: #1c1917; color: #f5f0e8; border: 1px solid #44403c; border-radius: 6px; padding: 6px;
}
QListWidget { background: #1c1917; border: 1px solid #3a332c; border-radius: 8px; padding: 4px; }
QListWidget::item { padding: 8px 6px; border-radius: 6px; }
QListWidget::item:selected { background: #44403c; color: #f6f1e7; }
QPushButton {
  background: #3f3428; color: #f6f1e7; border: 1px solid #5c4d3a; border-radius: 8px; padding: 8px 10px;
}
QPushButton:hover { background: #5c4a32; }
QPushButton:checked, #yarn:checked { background: #7f1d1d; border-color: #e24b4b; }
QSlider::groove:horizontal { height: 4px; background: #44403c; border-radius: 2px; }
QSlider::handle:horizontal { width: 14px; margin: -6px 0; background: #e8a54b; border-radius: 7px; }
QScrollBar:vertical { background: transparent; width: 10px; }
QScrollBar::handle:vertical { background: #44403c; border-radius: 4px; }
"""


def main():
    app = QApplication([])
    app.setApplicationName(APP_NAME)
    app.setStyleSheet(STYLE)
    win = MainWindow()
    win.show()
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()
