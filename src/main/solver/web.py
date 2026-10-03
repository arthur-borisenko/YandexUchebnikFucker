import traceback
from json import JSONDecodeError

from main.solver.base import BaseProblemSolver
from main.util import Status


class WebProblemSolver(BaseProblemSolver):
    SUPPORTED_PROBLEM_TYPES = ["web"]

    def readable_solution(self, problem_idx) -> tuple[Status, str]:
        status, problem = self.get_problem(problem_idx)
        if status != Status.OK:
            return status, "failed to get problem"

        answer_panes = problem.get("markup", {}).get("answer_panes", [])
        if not answer_panes:
            return Status.SOLUTION_FAILURE_UNKNOWN_PROBLEM_TYPE, "answer_panes not found in problem data."

        readable_text = [
            f"--- {pane.get('name', 'file')} ---\n{pane.get('content', '')}"
            for pane in answer_panes
        ]
        return Status.OK, "\n\n".join(readable_text)

    def send_solution(self, problem_idx, fake_timedelta=0) -> tuple[Status, str]:
        status, problem = self.get_problem(problem_idx)
        if status != Status.OK:
            return status, f"Failed to get problem: {status}"

        answer_panes = problem.get("markup", {}).get("answer_panes")
        if not answer_panes:
            return Status.SOLUTION_FAILURE_UNKNOWN_PROBLEM_TYPE, "Missing answer_panes"

        payload = {
            "lpl_id": self.get_problem_id(problem_idx),
            "clr_id": self.data["data"]["getLatestCLessonResult"]["id"],
            "attempt": {
                "answered": True,
                "completed": True,
                "markers": {
                    "user_answer": {
                        "panes": answer_panes,
                        "verdict": {"status": True, "errors": []},
                    }
                },
            },
            "sk": self.data["config"]["sk"],
        }

        self.post_fake_timedelta(problem_idx, fake_timedelta)

        resp = self.session.post(
            "https://education.yandex.ru/classroom/api/v2/post-attempts/",
            json=payload,
        )

        if resp.status_code // 100 != 2:
            try:
                response_data = resp.json()
                if response_data.get("errors") and "attempt limit" in response_data[
                    "errors"
                ][0].get("message", ""):
                    return (
                        Status.SOLUTION_FAILURE_ALREADY_SOLVED_OR_NO_ATTEMPTS,
                        resp.text,
                    )
                print(resp.text)
            except JSONDecodeError:
                return Status.UNKNOWN_ERROR, f"{resp.text} - {traceback.format_exc()}"
            except Exception:
                return Status.UNKNOWN_ERROR, traceback.format_exc()
            return (
                Status.UNKNOWN_ERROR,
                f"Server responded with status code: {resp.status_code} - {resp.text}",
            )

        resp_json = resp.json()
        result_data = resp_json.get("attempt", {}).get("markers", {}).get("result", {})

        was_mist = any(
            not item.get("answer_status", False) or item.get("mistake_count", 0) > 0
            for item in result_data.values()
        )

        st = Status.OK if not was_mist else Status.SOLUTION_FAILURE_WRONG_ANSWER
        return st, resp.text
