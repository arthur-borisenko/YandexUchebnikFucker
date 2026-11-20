from abc import ABC, abstractmethod

import requests

from main.util import Status


class BaseProblemSolver(ABC):
    SUPPORTED_PROBLEM_TYPES = []

    def __init__(
        self,
        cid: int | None,
        aid: int | None,
        session: requests.Session,
        data: dict | None,
    ):
        self.cid, self.aid, self.session, self.data = cid, aid, session, data

    @property
    def problems(self) -> list[dict]:
        if self.data is None:
            return []
        return self.data["data"]["getCLessonRun"]["problems"]

    def get_problem_id(self, problem_idx):
        return self.problems[problem_idx - 1]["id"]

    def post_fake_timedelta(self, problem_idx, fake_timedelta) -> Status:
        clr_id = self.data["data"]["getLatestCLessonResult"]["id"]
        spent_time_json = {
            "link_id": self.get_problem_id(problem_idx),
            "time_delta": fake_timedelta,
            "sk": self.data["config"]["sk"],
        }
        resp = self.session.post(
            f"https://education.yandex.ru/classroom/api/post-clesson-results-update-spent-time/{clr_id}/",
            json=spent_time_json,
        )
        return Status.OK if resp.status_code // 100 == 2 else Status.UNKNOWN_ERROR

    def get_problem(self, problem_idx):
        if self.data is None:
            return Status.NOT_INITIALIZED, "Not initialized"
        idx = int(problem_idx) - 1
        if idx >= len(self.problems):
            return Status.PROBLEM_NOT_FOUND, None
        problem = self.problems[idx]["problem"]
        if problem["type"] not in self.SUPPORTED_PROBLEM_TYPES:
            return Status.WRONG_PROBLEM_TYPE, None
        return Status.OK, problem

    @abstractmethod
    def send_solution(self, problem_idx, fake_timedelta=0) -> tuple[Status, str]:
        pass

    @abstractmethod
    def readable_solution(self, problem_idx) -> tuple[Status, str]:
        pass
