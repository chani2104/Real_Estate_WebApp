"""
QThread 기반 비동기 스크래핑 워커
UI 프리징 방지를 위해 별도 스레드에서 실행
"""

from PySide6.QtCore import QThread, Signal

from Real_Estate_WebApp.scraper import scrape_all_articles


class ScraperWorker(QThread):
    """매물 수집 워커 스레드"""

    progress = Signal(int, int, str)  # current, total, message
    finished_success = Signal(list)    # items
    finished_error = Signal(str)      # error message

    def __init__(self, cortar_no: str, lat: float, lon: float):
        super().__init__()
        self.cortar_no = cortar_no
        self.lat = lat
        self.lon = lon
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            def on_progress(current: int, total: int, message: str):
                self.progress.emit(current, total, message)

            def should_cancel() -> bool:
                return self._cancel

            items = scrape_all_articles(
                cortar_no=self.cortar_no,
                lat=self.lat,
                lon=self.lon,
                progress_callback=on_progress,
                cancel_check=should_cancel,
            )
            self.finished_success.emit(items)
        except Exception as e:
            self.finished_error.emit(str(e))
