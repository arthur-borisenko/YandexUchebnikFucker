"""Practice/marker solver. Public wrapper API and BaseProblemSolver contract are preserved.

Place this file at the path of your existing MarkerProblemSolver module if it differs.
"""
from __future__ import annotations

import json
import logging
import re

from main.solver.base import BaseProblemSolver
from main.solver.util.turing import AnswerRemapper, TuringAnswerResolver, TuringResolutionError
from main.util import Status

logger = logging.getLogger(__name__)


class MarkerProblemSolver(BaseProblemSolver):
    SUPPORTED_PROBLEM_TYPES = ["practice"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._turing = TuringAnswerResolver(self.session, max_requests=10)
        self._turing_cache = None
        self._last_answer_error = ""

    def get_clesson_id(self) -> str | int | None:
        try:
            return self.data["data"]["getCLessonRun"]["id"]
        except (KeyError, TypeError):
            logger.warning("Не удалось получить ID исходного урока")
            return None

    def fetch_turing_answers(self) -> dict | None:
        """Legacy helper: return the public active-lesson template (not the assigned variants)."""
        if self._turing_cache is not None:
            return self._turing_cache
        lesson_id = self.get_clesson_id()
        if lesson_id is None:
            return None
        try:
            self._turing_cache = self._turing.repository.fetch(lesson_id)
        except TuringResolutionError as exc:
            self._last_answer_error = str(exc)
            logger.warning("%s", exc)
        return self._turing_cache

    def remap_answers_if_shuffled(self, student_problem: dict, ref_problem: dict,
                                 ref_answers: dict) -> dict:
        """Compatibility helper: validate/remap ALWAYS, not only when a flag is true."""
        reference = dict(ref_problem)
        reference["markup"] = {**ref_problem.get("markup", {}), "answers": ref_answers}
        return AnswerRemapper().remap(student_problem, reference)

    @staticmethod
    def _has_valid_answers(answers: dict | None) -> bool:
        return isinstance(answers, dict) and bool(answers) and any(
            value is not None and value != [] and value != {} and value != ""
            for value in answers.values())

    def get_answers_source(self, problem_idx: int, problem: dict) -> dict:
        """Return verified answers only; on any ambiguity return {} and record an error."""
        self._last_answer_error = ""
        embedded = problem.get("markup", {}).get("answers")
        if self._has_valid_answers(embedded):
            try:
                return AnswerRemapper().remap(problem, problem)
            except TuringResolutionError as exc:
                logger.warning("Встроенные ответы неполны: %s", exc)
        lesson_id = self.get_clesson_id()
        if lesson_id is None:
            self._last_answer_error = "Не найден ID урока"
            return {}
        slug = self.data.get("data", {}).get("getCLessonRun", {}).get("meta", {}).get("slug")
        try:
            return self._turing.resolve(problem, int(problem_idx), int(lesson_id), slug)
        except (TuringResolutionError, ValueError, TypeError) as exc:
            self._last_answer_error = str(exc)
            logger.warning("Ответ для позиции %s не установлен: %s", problem_idx, exc)
            return {}

    @staticmethod
    def _clean_text(text) -> str:
        text = re.sub(r"\\?\{sizedText:[^}]*}|\{\\?sizedText}", "", str(text or ""))
        return text.replace("&amp;", "&")

    def readable_solution(self, problem_idx):
        try:
            problem_idx = int(problem_idx)
        except (ValueError, TypeError):
            return Status.PROBLEM_NOT_FOUND, None
        if problem_idx < 1:
            return Status.PROBLEM_NOT_FOUND, None
        status, problem = self.get_problem(problem_idx)
        if status != Status.OK:
            return status, None
        answers = self.get_answers_source(problem_idx, problem)
        if not answers:
            return Status.UNKNOWN_ERROR, self._last_answer_error or "Ответы не найдены"
        texts, lines = [], []
        for element in problem.get("markup", {}).get("layout", []):
            content = element.get("content", {})
            if element.get("kind") == "text":
                texts.append(self._clean_text(content.get("text")))
            elif element.get("kind") == "marker":
                mid = str(content.get("id"))
                if mid not in answers:
                    continue
                ans = answers[mid]
                kind = content.get("type")
                options = content.get("options", {})
                if kind == "choice":
                    choices = options.get("choices", [])
                    lines.append(" / ".join(self._clean_text(choices[i]) for i in ans))
                elif kind == "inline":
                    def substitute(match):
                        fid = match.group(1)
                        field = options.get("inputs", {}).get(fid, {})
                        value = ans.get(fid)
                        if field.get("type") == "choice":
                            value = field.get("options", {}).get("choices", [])[value]
                        elif isinstance(value, list):
                            value = value[0] if value else ""
                        return self._clean_text(value)
                    lines.append(re.sub(r"\{input:(\d+)}", substitute,
                                        self._clean_text(options.get("text", ""))))
                else:
                    lines.append(f"[{kind}] {json.dumps(ans, ensure_ascii=False)}")
        return Status.OK, "\n".join(texts + lines)

    def _check_solution(self, resp_json, problem_idx):
        answer_obj = resp_json["answers"][str(self.get_problem_id(problem_idx))][-1]
        mistakes = [key for key, value in answer_obj["markers"].items()
                    if value.get("mistakes", 0) > 0]
        return bool(mistakes), mistakes

    def _prepare_solution(self, answers, problem):
        marker_types = {str(e["content"]["id"]): e["content"]["type"]
                        for e in problem.get("markup", {}).get("layout", [])
                        if e.get("kind") == "marker"}
        if not isinstance(answers, dict) or set(map(str, answers)) != set(marker_types):
            return Status.UNKNOWN_ERROR, False
        result = {}
        for mid, kind in marker_types.items():
            value = answers[mid]
            if kind == "inline" and isinstance(value, dict) and value:
                user_answer = {str(fid): v[0] if isinstance(v, list) and v else v
                               for fid, v in value.items()}
            elif kind == "choice" and isinstance(value, list) and value:
                user_answer = value
            elif kind == "dragimage" and isinstance(value, dict) and value:
                user_answer = value
            elif kind in {"macaroni", "coloring", "chooseimage", "highlight"} \
                    and isinstance(value, list) and value:
                # Turing `answers` is a list of accepted alternatives; send one alternative.
                user_answer = value[0]
            else:
                logger.warning("Неверный или неподдерживаемый ответ для маркера %s (%s)", mid, kind)
                return Status.SOLUTION_FAILURE_UNKNOWN_PROBLEM_TYPE, False
            result[mid] = {"user_answer": user_answer}
        return Status.OK, result

    def _send_solution(self, sol, problem_idx) -> tuple[Status, str]:
        clr_id = self.data["data"]["getLatestCLessonResult"]["id"]
        data = {"clessonId": self.cid, "problemLinkId": self.get_problem_id(problem_idx),
                "resultId": clr_id, "answered": True, "completed": True, "answer": sol,
                "sk": self.data["config"]["sk"]}
        # Never log data or response body: data contains a session key and personal results.
        logger.debug("Отправка решения для link ID %s", data["problemLinkId"])
        try:
            resp = self.session.post("https://education.yandex.ru/classroom/api/patch-clesson-results/",
                                     json=data, timeout=15)
        except Exception as exc:
            return Status.UNKNOWN_ERROR, f"Не удалось отправить решение: {type(exc).__name__}"
        if resp.status_code // 100 != 2:
            try:
                errors = resp.json().get("errors", [])
                if any("attempt limit" in str(e.get("message", "")).lower() for e in errors):
                    return Status.SOLUTION_FAILURE_ALREADY_SOLVED_OR_NO_ATTEMPTS, "Превышен лимит попыток"
            except (ValueError, TypeError, AttributeError):
                pass
            return Status.UNKNOWN_ERROR, f"HTTP {resp.status_code} при отправке решения"
        try:
            mistake, markers = self._check_solution(resp.json(), problem_idx)
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            return Status.UNKNOWN_ERROR, "Непонятный формат ответа сервера при проверке"
        if mistake:
            return Status.SOLUTION_FAILURE_WRONG_ANSWER, f"{resp.text}\nMistakes found: {markers}!"
        return Status.OK, f"{resp.text}\nSolved successfully!"

    def send_solution(self, problem_idx, fake_timedelta=0) -> tuple[Status, str]:
        try:
            problem_idx = int(problem_idx)
            if problem_idx < 1:
                return Status.PROBLEM_NOT_FOUND, "Некорректный номер задачи"
            status, problem = self.get_problem(problem_idx)
        except (ValueError, TypeError):
            return Status.PROBLEM_NOT_FOUND, "Некорректный номер задачи"
        if status != Status.OK:
            return status, f"Failed to get problem: {status}"
        answers = self.get_answers_source(problem_idx, problem)
        if not answers:
            return Status.UNKNOWN_ERROR, self._last_answer_error or "Нет проверенных ответов"
        st, prepared = self._prepare_solution(answers, problem)
        if st != Status.OK:
            return st, "Ответ не подготовлен; отправка отменена"
        elapsed_status = self.post_fake_timedelta(problem_idx, fake_timedelta)
        if elapsed_status != Status.OK:
            return elapsed_status, "Не удалось обновить время; отправка отменена"
        return self._send_solution(json.dumps(prepared, ensure_ascii=False, separators=(",", ":")), problem_idx)
