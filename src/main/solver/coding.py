from main.solver.base import BaseProblemSolver
from main.util import Status


class CodingProblemSolver(BaseProblemSolver):
    def readable_solution(self, problem_idx) -> tuple[Status, str]:
        return self.coding_solution(problem_idx)

    SUPPORTED_PROBLEM_TYPES = ["coding"]

    def coding_solution(self, problem_idx) -> tuple[Status, str]:
        st, problem = self.get_problem(problem_idx)
        if st != Status.OK:
            return st, ""
        sol = problem["markup"]["languages"][0]["author_solution"]
        return Status.OK, sol

    def _send_coding_solution(self, problem_idx, solution):
        data = {
            "attempt": {
                "answered": True,
                "completed": True,
                "markers": {"user_answer": {"code": solution, "language": "python"}},
            },
            "clr_id": self.data["data"]["getLatestCLessonResult"]["id"],
            "lpl_id": self.get_problem_id(problem_idx),
            "sk": self.data["config"]["sk"],
        }
        resp = self.session.post(
            "https://education.yandex.ru/classroom/api/v2/post-attempts/", json=data
        )
        if resp.status_code // 100 != 2:
            return Status.UNKNOWN_ERROR
        return Status.OK

    def send_solution(self, problem_idx, fake_timedelta=0):
        st, sol = self.coding_solution(problem_idx)
        self.post_fake_timedelta(problem_idx, fake_timedelta)
        return self._send_coding_solution(problem_idx, sol)
