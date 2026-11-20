import re

from main.solver.base import BaseProblemSolver
from main.util import Status


class TheoryProblemSolver(BaseProblemSolver):
    SUPPORTED_PROBLEM_TYPES = ["theory"]

    def readable_solution(self, problem_idx):
        res = []
        st, problem = self.get_problem(problem_idx)
        if st != Status.OK:
            return st, "error"
        lyt = problem["markup"]["layout"]
        for el in lyt:
            if el["kind"] == "text":
                res.append(el["content"]["text"])
        return Status.OK, re.sub(
            r"\\?\{sizedText:.*?}|\\?\{\\\\sizedText}", "", "\n".join(res)
        )

    def send_solution(self, problem_idx, fake_timedelta=10) -> tuple[Status, str]:
        clr_id = self.data["data"]["getLatestCLessonResult"]["id"]
        data = {
            "clessonId": self.cid,
            "problemLinkId": self.get_problem_id(problem_idx),
            "resultId": clr_id,
            "answered": True,
            "completed": True,
            "answer": "{}",
            "sk": self.data["config"]["sk"],
        }
        resp = self.session.post(
            "https://education.yandex.ru/classroom/api/patch-clesson-results/",
            json=data,
        )
        if resp.status_code // 100 != 2:
            print(f"status code: {resp.status_code}, data: {resp.text}")
            return (
                Status.UNKNOWN_ERROR,
                f"Server responded with non-200 status code: {resp.status_code} - response: {resp.text}",
            )
        return Status.OK, "OK"
