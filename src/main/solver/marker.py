import json
import logging
import re
import traceback

from main.solver.base import BaseProblemSolver
from main.util import Status

# Настройка отладочного логгера
logger = logging.getLogger("MarkerProblemSolver")
logger.setLevel(logging.DEBUG)
REMAP_ENABLED=False
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter("[%(levelname)s] [%(name)s] %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)


def norm_text(s: str) -> str:
    """Нормализует текст: убирает неразрывные пробелы (\xa0), мягкие переносы (\xad) и лишние пробелы."""
    if not s:
        return ""
    s = str(s).replace("\xa0", " ").replace("\xad", "").strip()
    return re.sub(r"\s+", " ", s).lower()


def remap_choice(student_choices: list, ref_choices: list, ref_ans: list) -> list:
    """Сверяет выбранные индексы ответов из ref_ans по нормализованному тексту с массивом student_choices."""
    if not isinstance(ref_ans, list) or not ref_choices or not student_choices:
        return ref_ans

    norm_student = [norm_text(c) for c in student_choices]
    mapped = []

    for idx in ref_ans:
        if isinstance(idx, int) and 0 <= idx < len(ref_choices):
            ref_txt_raw = ref_choices[idx]
            ref_txt_norm = norm_text(ref_txt_raw)
            if ref_txt_norm in norm_student:
                new_idx = norm_student.index(ref_txt_norm)
                logger.debug(f"[Choice Remap] '{ref_txt_raw}': ref index {idx} -> student index {new_idx}")
                mapped.append(new_idx)
            else:
                logger.warning(f"[Choice Remap] Текст '{ref_txt_raw}' не найден в вариантах студента, оставлен индекс {idx}")
                mapped.append(idx)
        else:
            mapped.append(idx)

    return mapped


def remap_inline(student_inputs: dict, ref_inputs: dict, ref_ans: dict) -> dict:
    """Сверяет выбор для инлайн-полей типа choice по нормализованному тексту."""
    if not isinstance(ref_ans, dict):
        return ref_ans

    mapped = {}
    for inp_id, val in ref_ans.items():
        st_inp = student_inputs.get(str(inp_id), {})
        rf_inp = ref_inputs.get(str(inp_id), {})

        if st_inp.get("type") == "choice" and rf_inp.get("type") == "choice":
            st_choices = st_inp.get("options", {}).get("choices", [])
            rf_choices = rf_inp.get("options", {}).get("choices", [])

            if isinstance(val, int) and 0 <= val < len(rf_choices) and st_choices:
                ref_txt_raw = rf_choices[val]
                ref_txt_norm = norm_text(ref_txt_raw)
                norm_student = [norm_text(c) for c in st_choices]
                if ref_txt_norm in norm_student:
                    new_idx = norm_student.index(ref_txt_norm)
                    logger.debug(f"[Inline Choice Remap] Field {inp_id} '{ref_txt_raw}': ref idx {val} -> student idx {new_idx}")
                    mapped[str(inp_id)] = new_idx
                    continue
                else:
                    logger.warning(f"[Inline Choice Remap] Field {inp_id} '{ref_txt_raw}' не найден у студента")

        mapped[str(inp_id)] = val

    return mapped


def remap_macaroni(
    student_left: list, student_right: list, ref_left: list, ref_right: list, ref_ans: list
) -> list:
    """Сверяет парование левой и правой колонок (macaroni) по нормализованным текстам."""
    if not isinstance(ref_ans, list) or not ref_ans:
        return ref_ans

    norm_st_left = [norm_text(c) for c in student_left]
    norm_st_right = [norm_text(c) for c in student_right]

    pairs_list = (
        ref_ans[0]
        if (isinstance(ref_ans[0], list) and ref_ans[0] and isinstance(ref_ans[0][0], list))
        else ref_ans
    )

    mapped_pairs = []
    for pair in pairs_list:
        if len(pair) == 2 and isinstance(pair[0], int) and isinstance(pair[1], int):
            l_idx, r_idx = pair[0], pair[1]
            l_norm = norm_text(ref_left[l_idx]) if 0 <= l_idx < len(ref_left) else ""
            r_norm = norm_text(ref_right[r_idx]) if 0 <= r_idx < len(ref_right) else ""

            new_l = norm_st_left.index(l_norm) if l_norm in norm_st_left else l_idx
            new_r = norm_st_right.index(r_norm) if r_norm in norm_st_right else r_idx

            logger.debug(f"[Macaroni Remap] Pair ({l_idx}, {r_idx}) -> ({new_l}, {new_r})")
            mapped_pairs.append([new_l, new_r])
        else:
            mapped_pairs.append(pair)

    return [mapped_pairs]


class MarkerProblemSolver(BaseProblemSolver):
    SUPPORTED_PROBLEM_TYPES = ["practice"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._turing_cache = None

    def get_clesson_id(self) -> str | int | None:
        """Достает id урока (clessonId) из данных getCLessonRun."""
        try:
            cl_id = self.data["data"]["getCLessonRun"]["id"]
            logger.debug(f"Получен clessonId: {cl_id}")
            return cl_id
        except (KeyError, TypeError):
            logger.error("Не удалось прочитать clessonId из self.data")
            return None

    def fetch_turing_answers(self) -> dict | None:
        """Запрашивает ответы из Turing API с кэшированием."""
        if self._turing_cache is not None:
            logger.debug("Использование кэшированного ответа Turing API")
            return self._turing_cache

        clesson_id = self.get_clesson_id()
        if not clesson_id:
            logger.error("clessonId отсутствует, запрос к Turing API отменен.")
            return None

        url = f"https://education.yandex.ru/turing-api/lessons/{clesson_id}"
        logger.debug(f"Выполняется GET запрос к Turing API: {url}")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
            "Accept": "application/json",
        }

        try:
            resp = self.session.get(url, headers=headers)
            logger.debug(f"Ответ от Turing API: HTTP {resp.status_code}")
            if resp.status_code // 100 == 2:
                self._turing_cache = resp.json()
                probs_cnt = len(self._turing_cache.get("problems", []))
                logger.debug(f"Успешно получены ответы Turing API. Загружено задач: {probs_cnt}")
                return self._turing_cache
            logger.error(f"Ошибка получения ответов HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            logger.error(f"Исключение при запросе к Turing API: {e}", exc_info=True)

        return None

    def remap_answers_if_shuffled(
        self, student_problem: dict, ref_problem: dict, ref_answers: dict
    ) -> dict:
        """Сверяет исходный ответ с распорядком вариантов текущего студента."""
        if not ref_answers or not ref_problem:
            return ref_answers or {}
        if not REMAP_ENABLED: return ref_answers or {}
        ref_markers = {
            str(el["content"]["id"]): el["content"]
            for el in ref_problem.get("markup", {}).get("layout", [])
            if el.get("kind") == "marker"
        }

        final_answers = {}
        for el in student_problem.get("markup", {}).get("layout", []):
            if el.get("kind") != "marker":
                continue
            mid = str(el["content"]["id"])
            st_mo = el["content"].get("options", {})
            mt = el["content"].get("type")
            ref_ans = ref_answers.get(mid)

            if ref_ans is None:
                continue

            ref_mo = ref_markers.get(mid, {}).get("options", {})
            logger.debug(f"Обработка маркера ID={mid}, Type='{mt}'")

            if mt == "choice":
                final_answers[mid] = remap_choice(
                    st_mo.get("choices", []),
                    ref_mo.get("choices", []),
                    ref_ans,
                )
            elif mt == "inline":
                final_answers[mid] = remap_inline(
                    st_mo.get("inputs", {}),
                    ref_mo.get("inputs", {}),
                    ref_ans,
                )
            elif mt == "macaroni":
                final_answers[mid] = remap_macaroni(
                    st_mo.get("left", {}).get("choices", []),
                    st_mo.get("right", {}).get("choices", []),
                    ref_mo.get("left", {}).get("choices", []),
                    ref_mo.get("right", {}).get("choices", []),
                    ref_ans,
                )
            else:
                logger.debug(f"Маркер '{mt}' сохранен без изменений")
                final_answers[mid] = ref_ans

        return final_answers

    def get_answers_source(self, problem_idx: int, problem: dict) -> dict:
        """Получает ответы из объекта задачи или из иерархии Turing API с нормализованной сверкой."""
        target_p_id = problem.get("id")
        target_link_id = self.get_problem_id(problem_idx)
        logger.debug(f"Поиск ответов для problem_idx={problem_idx} (link_id={target_link_id}, inner_id={target_p_id})")

        turing_data = self.fetch_turing_answers()
        if not turing_data or "problems" not in turing_data:
            logger.warning("Данные Turing API недоступны, используются встроенные в problem ответы.")
            return problem.get("markup", {}).get("answers", {})

        problems_list = turing_data.get("problems", [])
        matched_ref_item = None
        for item in problems_list:
            if item.get("id") == target_link_id or item.get("problem", {}).get("id") == target_p_id:
                matched_ref_item = item.get("problem", {})
                logger.debug(f"Совпадение задачи найдено по ID (link_id={target_link_id} / inner_id={target_p_id})")
                break

        if not matched_ref_item:
            idx = int(problem_idx) - 1
            if 0 <= idx < len(problems_list):
                matched_ref_item = problems_list[idx].get("problem", {})
                logger.debug(f"Совпадение задачи найдено по индексу [{idx}]. Возможны неточности.")

        if not matched_ref_item:
            logger.warning(f"Задание index={problem_idx} не найдено в Turing API. Используются встроенные ответы.")
            return problem.get("markup", {}).get("answers", {})

        ref_answers = matched_ref_item.get("markup", {}).get("answers", {})
        logger.debug(f"Исходные ответы из Turing API: {ref_answers}")

        final_answers = self.remap_answers_if_shuffled(problem, matched_ref_item, ref_answers)
        logger.debug(f"Итоговые сопоставленные ответы: {final_answers}")
        return final_answers

    def readable_solution(self, problem_idx):
        logger.debug(f"Вызов readable_solution для problem_idx={problem_idx}")
        status, problem = self.get_problem(problem_idx)
        if status != Status.OK:
            logger.error(f"Не удалось получить проблему: {status}")
            return status, None

        answers_map = self.get_answers_source(problem_idx, problem)

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
            for ans in [answers_map.get(str(el["content"]["id"]))]
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
                logger.error(f"Неизвестный тип маркера '{m_type}' при подготовке решения")
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
        logger.debug(f"Отправка решения через patch-clesson-results: {data}")
        resp = self.session.post(
            "https://education.yandex.ru/classroom/api/patch-clesson-results/",
            json=data,
        )
        if resp.status_code // 100 != 2:
            logger.error(f"Ошибка сервера при отправке решения: status code={resp.status_code}, data={resp.text}")
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
            except Exception:
                return Status.UNKNOWN_ERROR, traceback.format_exc()
            return (
                Status.UNKNOWN_ERROR,
                f"Server responded with non-200 status code: {resp.status_code} - {resp.text}",
            )
        was_mist, mist = self._check_solution(resp.json(), problem_idx)
        st = Status.OK if not was_mist else Status.SOLUTION_FAILURE_WRONG_ANSWER
        msg = [resp.text]
        if was_mist:
            logger.warning(f"Обнаружены ошибки при проверке: {mist}")
            msg.append(f"Mistakes found: {mist}!")
        else:
            logger.info("Задача успешно решена без ошибок!")
            msg.append("Solved successfully!")
        return st, "\n".join(msg)

    def send_solution(self, problem_idx, fake_timedelta=0) -> tuple[Status, str]:
        logger.info(f"Начало процесса отправки решения для задачи problem_idx={problem_idx}")
        status, problem = self.get_problem(problem_idx)
        if status != Status.OK:
            logger.error(f"Не удалось получить данные проблемы: {status}")
            return status, f"Failed to get problem: {status}"
        answers = self.get_answers_source(problem_idx, problem)
        st, prepared = self._prepare_solution(answers, problem)
        if st == Status.SOLUTION_FAILURE_UNKNOWN_PROBLEM_TYPE:
            logger.error("Ошибка при подготовке решения: неизвестный тип проблемы.")
            return Status.SOLUTION_FAILURE_UNKNOWN_PROBLEM_TYPE, ""
        dt = json.dumps(prepared, separators=(",", ":"))
        logger.debug(f"Подготовленный JSON ответа: {dt}")
        self.post_fake_timedelta(problem_idx, fake_timedelta)
        return self._send_solution(dt, problem_idx)