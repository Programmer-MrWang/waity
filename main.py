import sys
import argparse
import os

from PySide6.QtWidgets import QApplication, QWidget, QHBoxLayout, QVBoxLayout, QSystemTrayIcon, QMenu
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QIcon, QAction
from qfluentwidgets import (
    BodyLabel,
    FluentIcon,
    MessageBoxBase,
    PrimaryPushButton,
    PushButton,
    SubtitleLabel,
    Theme,
    setTheme,
    setThemeColor,
)
from qframelesswindow.utils import getSystemAccentColor


def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller/Nuitka"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        # Nuitka or development
        base_path = os.path.dirname(__file__)
    return os.path.join(base_path, relative_path)


def format_time(seconds: int) -> str:
    """将秒数格式化为 X 分 X 秒 或 X 秒"""
    if seconds >= 60:
        minutes = seconds // 60
        rem_seconds = seconds % 60
        if rem_seconds == 0:
            return f" {minutes} 分钟"
        return f" {minutes} 分 {rem_seconds} 秒"
    return f" {seconds} 秒"


class ShutdownMessageBox(MessageBoxBase):
    """基于 MessageBoxBase 的关机提示框"""

    def __init__(self, parent, args) -> None:
        super().__init__(parent)
        self.args = args
        self.remaining = args.countdown if args.countdown else 60

        # 设置固定宽度
        self.widget.setFixedWidth(580)

        self._setup_content()
        self._setup_buttons()

    def _setup_content(self) -> None:
        self.titleLabel = SubtitleLabel("即将关机", self)
        time_text = format_time(self.remaining)
        self.contentLabel = BodyLabel(
            f"计算机将在{time_text}后自动关闭。请及时保存您的工作或选择其他操作。", self
        )
        self.contentLabel.setWordWrap(True)

        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.contentLabel)

    def _setup_buttons(self) -> None:
        # 隐藏默认按钮
        self.yesButton.hide()
        self.cancelButton.hide()

        # 创建自定义按钮
        delay_text = format_time(self.args.delay)
        self.primary_btn = PrimaryPushButton(FluentIcon.ACCEPT, "已阅", self)
        self.secondary_btn = PushButton(FluentIcon.POWER_BUTTON, "立即关机", self)
        self.third_btn = PushButton(FluentIcon.DATE_TIME, f"延迟 {delay_text}", self)
        self.close_btn = PushButton(FluentIcon.CLOSE, "取消关机计划", self)

        self.buttonLayout.addWidget(self.primary_btn)
        self.buttonLayout.addStretch(1)
        self.buttonLayout.addWidget(self.secondary_btn)
        self.buttonLayout.addWidget(self.third_btn)
        self.buttonLayout.addWidget(self.close_btn)

    def update_subtitle(self) -> None:
        time_text = format_time(self.remaining)
        self.contentLabel.setText(
            f"计算机将在{time_text}后自动关闭。请及时保存您的工作或选择其他操作。"
        )


class MainWindow(QWidget):
    """全屏透明主窗口"""

    def __init__(self, args) -> None:
        super().__init__()
        self.args = args
        setTheme(Theme.AUTO)
        # 获取系统主题色（仅 Windows 和 macOS）
        if sys.platform in ["win32", "darwin"]:
            setThemeColor(getSystemAccentColor(), save=False)
        self.icon_path = get_resource_path("icon.png")

        # 设置全屏透明窗口
        self.setWindowTitle("Waity")
        self.setWindowIcon(QIcon(self.icon_path))
        
        # 根据参数设置是否显示在任务栏
        window_flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        if not self.args.show_in_taskbar:
            window_flags |= Qt.Tool  # 不显示在任务栏
        
        self.setWindowFlags(window_flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.showFullScreen()

        # 初始化倒计时
        if self.args.countdown:
            self.remaining = self.args.countdown
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.update_countdown)
            self.timer.start(1000)

        self._init_ui()
        self._init_tray()

    def _init_ui(self) -> None:
        # 创建消息框
        self.message_box = ShutdownMessageBox(self, self.args)
        self.message_box.remaining = self.remaining
        self.message_box.update_subtitle()

        # 连接按钮信号
        self.message_box.primary_btn.clicked.connect(self.on_primary_clicked)
        self.message_box.secondary_btn.clicked.connect(self.on_secondary_clicked)
        self.message_box.third_btn.clicked.connect(self.on_third_clicked)
        self.message_box.close_btn.clicked.connect(self.cancel_shutdown)

        # 显示消息框
        self.message_box.show()

    def _init_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(self.icon_path))
        time_text = format_time(self.remaining)
        self.tray_icon.setToolTip(f"Waity：{time_text}后自动关机")

        # 创建托盘菜单
        tray_menu = QMenu()

        self.time_action = QAction(f"剩余时间：{time_text}", self)
        tray_menu.addAction(self.time_action)

        delay_text = format_time(self.args.delay)
        delay_action = QAction(f"延迟 {delay_text}", self)
        delay_action.triggered.connect(self.on_third_clicked)
        tray_menu.addAction(delay_action)

        cancel_action = QAction("取消关机计划", self)
        cancel_action.triggered.connect(self.cancel_shutdown)
        tray_menu.addAction(cancel_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_reminder()

    def update_ui(self):
        self.message_box.remaining = self.remaining
        self.message_box.update_subtitle()
        time_text = format_time(self.remaining)
        self.time_action.setText(f"剩余时间：{time_text}")
        self.tray_icon.setToolTip(f"Waity：{time_text}后自动关机")

    def closeEvent(self, event):
        event.ignore()
        self.hide()

    def update_countdown(self):
        self.remaining -= 1
        if self.remaining == self.args.reminder:
            self.show_reminder()

        if self.remaining > 0:
            self.update_ui()
        else:
            self.timer.stop()
            # 执行关机
            self.perform_shutdown()

    def show_reminder(self):
        """显示提醒窗口"""
        self.showFullScreen()
        self.message_box.show()
        self.raise_()
        self.activateWindow()

    def perform_shutdown(self):
        # 这里添加关机命令
        import os
        os.system("shutdown /s /t 0")

    def cancel_shutdown(self):
        self.message_box.close()
        # 延迟关闭窗口，让 MessageBox 动画播放完成
        QTimer.singleShot(500, self.quit_app)

    def quit_app(self):
        if hasattr(self, 'timer'):
            self.timer.stop()
        QApplication.quit()

    def on_primary_clicked(self):
        self.message_box.hide()
        self.hide()

    def on_secondary_clicked(self):
        self.perform_shutdown()

    def on_third_clicked(self):
        if hasattr(self, 'timer') and self.timer.isActive():
            self.remaining += self.args.delay
            self.update_ui()
        else:
            self.remaining = self.args.delay
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.update_countdown)
            self.timer.start(1000)
            self.update_ui()
        self.message_box.close()
        # 延迟关闭窗口，让 MessageBox 动画播放完成
        QTimer.singleShot(300, self.hide)


def main() -> None:
    parser = argparse.ArgumentParser(description='Waity')
    parser.add_argument('--countdown', type=int, default=60, help='倒计时时长（秒），默认 60 秒')
    parser.add_argument('--delay', type=int, default=180, help='延迟选项时长（秒），默认 180 秒（3 分钟）')
    parser.add_argument('--reminder', type=int, default=60, help='关机前再次提醒的时长（秒），默认 60 秒')
    parser.add_argument('--show-in-taskbar', action='store_true', help='显示在任务栏中（默认不显示）')
    args = parser.parse_args()

    if args.countdown <= 0 or args.delay <= 0 or args.reminder <= 0:
        print("错误：--countdown, --delay, --reminder 参数必须为大于 0 的整数")
        sys.exit(1)

    if args.reminder > args.delay:
        print("错误：--reminder 必须小于 --delay")
        sys.exit(1)

    app = QApplication(sys.argv)
    window = MainWindow(args)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
