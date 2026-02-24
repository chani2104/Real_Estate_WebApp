"""
네이버 부동산 매물 수집기 - 진입점
"""

import sys
from pathlib import Path

# 파일 이동 후에도 실행되도록: 상위 폴더를 path에 추가
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from Real_Estate_WebApp.main_window import MainWindow


def main():
    # High DPI 지원
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("네이버 부동산 매물 수집기")
    app.setOrganizationName("NaverLandScraper")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
