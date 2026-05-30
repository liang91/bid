from services import ScheduleService

from loguru import logger

logger.add("log.txt", rotation="1 day", retention="7 days", encoding="utf-8")


class TestScheduleService:
    def test_start(self):
        ScheduleService.start()
