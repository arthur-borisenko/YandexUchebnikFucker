import json
import re
import traceback

from main.solver.base import BaseProblemSolver
from main.util import Status


class MarkerProblemSolver(BaseProblemSolver):
    SUPPORTED_PROBLEM_TYPES = ["practice"]

    def readable_solution(self, problem_idx):
        status, problem = self.get_problem(problem_idx)
        if status != Status.OK:
            return status, None

        c = lambda t: re.sub(
            r"\\?\{sizedText:.*?}|\\?\{\\\\sizedText}", "", str(t or "")
        )

        fmt_inline = lambda mo, ans: re.sub(
            r"\{input:[1-9]\d*}", "{}", c(mo["text"])
        ).format(
            *[
                c(
                    conf.get("options", {}).get("choices", {})[v]
                    if conf.get("type") == "choice" and isinstance(v, int)
                    else (
                        v[0]
                        if conf.get("type") == "field" and isinstance(v, list)
                        else v
                    )
                )
                for tid in re.findall(r"\{input:([1-9]\d*)}", mo["text"])
                for conf in [mo.get("inputs", {}).get(tid, {})]
                for v in [ans.get(tid)]
            ]
        )

        text = c(
            "\n".join(
                el["content"]["text"]
                for el in problem["markup"]["layout"]
                if el["kind"] == "text"
            )
        )

        ans_lines = [
            (
                fmt_inline(mo, ans)
                if mt == "inline"
                else (
                    " / ".join(c(mo["choices"][i]) for i in ans)
                    if mt == "choice"
                    else f"[{mt}] RAW: {ans}"
                )
            )
            for el in problem["markup"]["layout"]
            if el["kind"] == "marker"
            for ans in [problem["markup"]["answers"].get(str(el["content"]["id"]))]
            if ans is not None
            for mo, mt in [(el["content"]["options"], el["content"]["type"])]
        ]

        return Status.OK, text + "\t\n\r".join(ans_lines)

    def _check_solution(self, resp_json, problem_idx):
        answer_obj = resp_json["answers"][str(self.get_problem_id(problem_idx))][-1]
        mist = [k for k, v in answer_obj["markers"].items() if v["mistakes"] > 0]
        return len(mist) > 0, mist

    def _prepare_solution(self, answers, problem):
        marker_types = {}
        for el in problem["markup"]["layout"]:
            if el["kind"] == "marker":
                marker_types[str(el["content"]["id"])] = el["content"]["type"]

        res = {}
        for mid, ans_data in answers.items():
            m_type = marker_types.get(str(mid))
            if m_type == "inline":
                inner_payload = {}
                for inp_id, val in ans_data.items():
                    inner_payload[str(inp_id)] = (
                        val[0] if isinstance(val, list) else val
                    )
                res[str(mid)] = {"user_answer": inner_payload}
            elif m_type in {"choice", "dragimage"}:
                res[str(mid)] = {"user_answer": ans_data}
            elif m_type in {"chooseimage", "highlight"}:
                inner_payload = ans_data[0]
                res[str(mid)] = {"user_answer": inner_payload}
            else:
                return Status.SOLUTION_FAILURE_UNKNOWN_PROBLEM_TYPE, False
        return Status.OK, res

    def _send_solution(self, sol, problem_idx) -> tuple[Status, str]:
        clr_id = self.data["data"]["getLatestCLessonResult"]["id"]
        data = {
            "clessonId": self.cid,
            "problemLinkId": self.get_problem_id(problem_idx),
            "resultId": clr_id,
            "answered": True,
            "completed": True,
            "answer": sol,
            "sk": self.data["config"]["sk"],
        }
        resp = self.session.post(
            "https://education.yandex.ru/classroom/api/patch-clesson-results/",
            json=data,
        )
        if resp.status_code // 100 != 2:
            print(f"status code: {resp.status_code}, data: {resp.text}")
            try:
                response_data = resp.json()
                if len(
                    response_data.get("errors", [])
                ) > 0 and "attempt limit" in response_data.get("errors", [])[0].get(
                    "message"
                ):
                    return (
                        Status.SOLUTION_FAILURE_ALREADY_SOLVED_OR_NO_ATTEMPTS,
                        resp.text,
                    )
            except Exception as e:
                return Status.UNKNOWN_ERROR, traceback.format_exc()
            return (
                Status.UNKNOWN_ERROR,
                f"Server responded with non-200 status code: {resp.status_code} - {resp.text}",
            )
        was_mist, mist = self._check_solution(resp.json(), problem_idx)
        st = Status.OK if not was_mist else Status.SOLUTION_FAILURE_WRONG_ANSWER
        msg = [resp.text]
        if was_mist:
            msg.append(f"Mistakes found: {mist}!")
        else:
            msg.append("Solved successfully!")
        return st, "\n".join(msg)

    def send_solution(self, problem_idx, fake_timedelta=0) -> tuple[Status, str]:
        print("sending solution.....")
        status, problem = self.get_problem(problem_idx)
        if status != Status.OK:
            return status, f"Failed to get problem: {status}"
        st, prepared = self._prepare_solution(problem["markup"]["answers"], problem)
        if st == Status.SOLUTION_FAILURE_UNKNOWN_PROBLEM_TYPE:
            return Status.SOLUTION_FAILURE_UNKNOWN_PROBLEM_TYPE, f""
        dt = json.dumps(prepared, separators=(",", ":"))
        print(dt)
        self.post_fake_timedelta(problem_idx, fake_timedelta)
        return self._send_solution(dt, problem_idx)
