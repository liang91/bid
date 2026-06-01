from dao import JobLogDao
from models import JobLogDto


class TestJobLog:
    def test_create(self):
        dto = JobLogDto(job_name='任务名')
        print(JobLogDao.create(dto))

    def test_update(self):
        JobLogDao.update(1, job_name='任务名1')
