import sys
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtWidgets import QApplication, QGraphicsOpacityEffect, QWidget

class Skeleton(QWidget):
    """
    Animated skeleton widget for loading states.
    Uses QGraphicsOpacityEffect and QPropertyAnimation to create a soft pulse effect.
    Automatically pauses animation when hidden to save CPU cycles.
    """

    def __init__(
        self,
        width: int = 200,
        height: int = 20,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self.setObjectName("Skeleton")

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)

        self.animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.animation.setDuration(1000)
        self.animation.setStartValue(0.3)
        self.animation.setEndValue(1.0)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        self.animation.setLoopCount(-1)

        self.start()

    def start(self) -> None:
        """Starts the pulsing animation if it is not already running."""
        if self.animation.state() != QPropertyAnimation.State.Running:
            self.animation.start()

    def stop(self) -> None:
        """Stops the pulsing animation to save CPU resources."""
        if self.animation.state() == QPropertyAnimation.State.Running:
            self.animation.stop()

    def hideEvent(self, event) -> None:
        """Automatically stops the animation when the widget becomes invisible."""
        self.stop()
        super().hideEvent(event)

    def showEvent(self, event) -> None:
        """Resumes the animation when the widget becomes visible again."""
        self.start()
        super().showEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = QWidget()
    window.resize(400, 200)

    skeleton = Skeleton(width=300, height=28, parent=window)
    skeleton.move(50, 80)

    window.show()
    sys.exit(app.exec())