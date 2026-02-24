"""
메인 윈도우 - PySide6 GUI
"""

import os
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QProgressBar,
    QLabel,
    QComboBox,
    QFileDialog,
    QMessageBox,
    QHeaderView,
    QStatusBar,
    QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from Real_Estate_WebApp.worker import ScraperWorker
from Real_Estate_WebApp.utils import TABLE_COLUMNS, item_to_row, save_to_excel, default_filename, REGION_CONFIG


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker: ScraperWorker | None = None
        self.items: list = []
        self.region_name = ""
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("네이버 부동산 매물 수집기")
        self.setMinimumSize(900, 600)
        self.resize(1000, 700)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # ---- 상단: 지역 입력 ----
        top_layout = QHBoxLayout()
        top_layout.setSpacing(8)

        self.region_combo = QComboBox()
        self.region_combo.setMinimumWidth(220)
        self.region_combo.setEditable(True)
        self.region_combo.setPlaceholderText("지역 선택 또는 법정동코드 입력")
        for cortar_no, (_, _, name) in REGION_CONFIG.items():
            self.region_combo.addItem(f"{name} ({cortar_no})", cortar_no)
        self.region_combo.currentIndexChanged.connect(self._on_region_changed)

        self.start_btn = QPushButton("수집 시작")
        self.start_btn.setMinimumWidth(100)
        self.start_btn.clicked.connect(self._on_start_scrape)

        self.cancel_btn = QPushButton("중단")
        self.cancel_btn.setMinimumWidth(80)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._on_cancel_scrape)

        top_layout.addWidget(QLabel("지역:"))
        top_layout.addWidget(self.region_combo, 1)
        top_layout.addWidget(self.start_btn)
        top_layout.addWidget(self.cancel_btn)

        layout.addLayout(top_layout)

        # ---- 진행 상태 ----
        progress_frame = QFrame()
        progress_frame.setFrameStyle(QFrame.StyledPanel)
        progress_layout = QVBoxLayout(progress_frame)
        progress_layout.setContentsMargins(12, 8, 12, 8)

        self.progress_label = QLabel("대기 중...")
        self.progress_label.setStyleSheet("color: #555;")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)

        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)
        layout.addWidget(progress_frame)

        # ---- 테이블 ----
        headers = [col[1] for col in TABLE_COLUMNS]
        self.table = QTableWidget()
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        idx = next((i for i, h in enumerate(headers) if h == "특징"), len(headers) - 1)
        self.table.horizontalHeader().setSectionResizeMode(idx, QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table, 1)

        # ---- 하단: 엑셀 저장 ----
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        self.excel_btn = QPushButton("엑셀로 저장")
        self.excel_btn.setMinimumWidth(120)
        self.excel_btn.clicked.connect(self._on_save_excel)
        self.excel_btn.setEnabled(False)

        self.count_label = QLabel("총 0건")
        self.count_label.setStyleSheet("font-weight: bold; color: #333;")

        bottom_layout.addWidget(self.excel_btn)
        bottom_layout.addWidget(self.count_label)

        layout.addLayout(bottom_layout)

        # ---- 상태바 ----
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("지역을 선택하고 '수집 시작'을 클릭하세요.")

    def _on_region_changed(self, index: int):
        pass  # 필요시 처리

    def _get_cortar_and_coords(self) -> tuple[str, float, float] | None:
        """선택된 지역의 cortarNo, lat, lon 반환"""
        index = self.region_combo.currentIndex()
        if index >= 0:
            cortar_no = self.region_combo.itemData(index)
            if cortar_no and cortar_no in REGION_CONFIG:
                lat, lon, _ = REGION_CONFIG[cortar_no]
                return cortar_no, lat, lon

        # 직접 입력: "5119000000" 또는 "지역명 (5119000000)" 형태
        text = self.region_combo.currentText().strip()
        if not text:
            return None

        # 괄호 안 cortarNo 추출
        if "(" in text and ")" in text:
            start = text.rfind("(") + 1
            end = text.rfind(")")
            cortar_no = text[start:end].strip()
        else:
            cortar_no = text

        if cortar_no.isdigit() and cortar_no in REGION_CONFIG:
            lat, lon, _ = REGION_CONFIG[cortar_no]
            return cortar_no, lat, lon

        # 등록되지 않은 cortarNo
        if cortar_no.isdigit():
            return None  # utils.REGION_CONFIG에 좌표 추가 필요

        return None

    def _on_start_scrape(self):
        result = self._get_cortar_and_coords()
        if not result:
            QMessageBox.warning(
                self,
                "입력 오류",
                "지역을 선택하거나 법정동코드(예: 5119000000)를 입력해 주세요.\n"
                "등록된 지역은 드롭다운에서 선택할 수 있습니다.",
            )
            return

        cortar_no, lat, lon = result
        self._start_worker(cortar_no, lat, lon)

    def _start_worker(self, cortar_no: str, lat: float, lon: float):
        self.items = []
        self._clear_table()
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.excel_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_label.setText("수집 준비 중...")
        self.status_bar.showMessage("매물 수집 중...")

        self.worker = ScraperWorker(cortar_no, lat, lon)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_success.connect(self._on_finished_success)
        self.worker.finished_error.connect(self._on_finished_error)
        self.worker.start()

    def _on_progress(self, current: int, total: int, message: str):
        if total > 0:
            pct = int(100 * current / total)
        else:
            pct = 0
        self.progress_bar.setValue(pct)
        self.progress_bar.setMaximum(100)
        self.progress_label.setText(f"{message} ({current}/{total})")

    def _on_finished_success(self, items: list):
        self.items = items
        self._populate_table(items)
        self._finish_scrape()
        self.status_bar.showMessage(f"수집 완료: {len(items)}건")
        self.count_label.setText(f"총 {len(items)}건")
        self.excel_btn.setEnabled(len(items) > 0)

        if len(items) == 0:
            QMessageBox.information(
                self,
                "수집 완료",
                "해당 지역에 매물이 없습니다.",
            )

    def _on_finished_error(self, message: str):
        self._finish_scrape()
        QMessageBox.critical(
            self,
            "수집 오류",
            f"매물 수집 중 오류가 발생했습니다:\n\n{message}",
        )
        self.status_bar.showMessage("오류 발생")

    def _finish_scrape(self):
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress_bar.setValue(100)
        self.progress_label.setText("완료")
        if self.worker:
            self.worker = None

    def _on_cancel_scrape(self):
        if self.worker:
            self.worker.cancel()

    def _clear_table(self):
        self.table.setRowCount(0)

    def _populate_table(self, items: list):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(items))
        for row_idx, item in enumerate(items):
            row_data = item_to_row(item)
            for col_idx, val in enumerate(row_data):
                self.table.setItem(row_idx, col_idx, QTableWidgetItem(str(val)))
        self.table.setSortingEnabled(True)
        self.count_label.setText(f"총 {len(items)}건")

    def _on_save_excel(self):
        if not self.items:
            QMessageBox.warning(
                self,
                "저장 불가",
                "저장할 매물 데이터가 없습니다.",
            )
            return

        region = self.region_combo.currentText() or "지역"
        if "(" in region:
            region = region.split("(")[0].strip()
        default_name = default_filename(region)

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "엑셀 파일 저장",
            default_name,
            "Excel 파일 (*.xlsx)",
        )

        if not filepath:
            return

        if not filepath.endswith(".xlsx"):
            filepath += ".xlsx"

        try:
            saved = save_to_excel(self.items, filepath)
            QMessageBox.information(
                self,
                "저장 완료",
                f"엑셀 파일이 저장되었습니다.\n\n{saved}",
            )
            self.status_bar.showMessage(f"저장 완료: {saved}")
        except Exception as e:
            QMessageBox.critical(
                self,
                "저장 오류",
                f"파일 저장 중 오류가 발생했습니다:\n\n{str(e)}",
            )
