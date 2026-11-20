import json
import random

import requests

from main.solver import BaseProblemSolver, get_problem_solvers
from main.util import (
    FALLBACK_SK_URLS,
    PRIMARY_SK_URLS,
    Status,
    fetch_sk_from_pages,
    login_with_creds,
)


class YandexUchebnik:
    MIN_RAND_TD = 20
    MAX_RAND_TD = 180

    API_BASE = "https://education.yandex.ru/classroom/api"

    def __init__(self, cid, aid, credentials=None):
        self.cid = cid
        self.aid = aid
        self.data = None
        self.cookies = {}
        self.username = credentials["login"]
        self.sch = credentials["code"]
        self.solvers = get_problem_solvers()
        self.session = requests.Session()
        self.new_msgs = []
        # Текст, который модуль вернул вместе с последним статусом (msg).
        # Именно его показывает webui (например, текст ответа сервера при
        # COOKIES_GENERATE_ERROR), а не только имя статуса.
        self.last_msg = ""

    def _login(self):
        status, msg = login_with_creds(self.username, self.sch, self.session)
        if status != Status.OK:
            # Текст ответа сервера (в т.ч. подробности ошибки) не должен теряться
            self.last_msg = str(msg)
            self._add_msg(f"[{status.name}] Ошибка авторизации: {msg}")
        return status

    def _add_msg(self, msg: str):
        """Сообщения самого модуля (их видно в webui/логах)."""
        self.new_msgs.append(msg)
        print(msg)

    def _fail(self, status: Status, msg: str) -> Status:
        """Сохраняет msg (текст ошибки) рядом со статусом и возвращает статус."""
        self.last_msg = str(msg)
        self._add_msg(f"[{status.name}] {msg}")
        return status

    def pop_messages(self) -> list[str]:
        """Забирает и очищает накопленные сообщения модуля."""
        msgs, self.new_msgs = self.new_msgs, []
        return msgs

    def _headers(self) -> dict:
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
            "Accept-Language": "ru-RU,ru;q=0.9",
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://education.yandex.ru",
            "Referer": "https://education.yandex.ru/classroom/",
        }

    def get_sk(self) -> str:
        """CSRF/session-ключ (sk).

        Обычно лежит в window._data загруженной страницы; если страниц недоступна
        (например, гео-блок по IP) — берём со служебных страниц через
        fetch_sk_from_pages (см. main/util.py).
        """
        if self.data and (self.data.get("config") or {}).get("sk"):
            return self.data["config"]["sk"]
        sk, _diag, _geo = fetch_sk_from_pages(
            self.session, self._headers(), FALLBACK_SK_URLS
        )
        if not sk:
            sk, _diag, _geo = fetch_sk_from_pages(
                self.session, self._headers(), PRIMARY_SK_URLS
            )
        return sk or ""

    def _fetch_api_data(self) -> tuple[dict | None, str]:
        """Собирает данные в формате window._data напрямую из API Учебника.

        Нужно для работы из-за границы: HTML-страницы /kids/ и
        /classroom/courses/.../run/1/ закрыты гео-блоком, а API-маршруты
        get-me / get-clesson-run / get-latest-clesson-result открыты и отдают
        ровно те же данные, что и страница.
        """
        hdrs = self._headers()
        payload: dict = {
            "basePath": "https://education.yandex.ru",
            "config": {"sk": self.get_sk()},
            "data": {},
        }

        resp = self.session.get(f"{self.API_BASE}/get-me/", headers=hdrs)
        if resp.status_code // 100 != 2:
            return None, f"get-me -> HTTP {resp.status_code}: {resp.text[:300]}"
        try:
            payload["data"]["getMe"] = resp.json()
        except Exception as e:
            return None, f"get-me -> некорректный JSON: {e}"

        if not self.aid:
            return payload, ""

        resp = self.session.get(
            f"{self.API_BASE}/get-clesson-run/{self.aid}/", headers=hdrs
        )
        if resp.status_code // 100 != 2:
            return (
                None,
                f"get-clesson-run/{self.aid} -> HTTP {resp.status_code}: {resp.text[:300]}",
            )
        try:
            payload["data"]["getCLessonRun"] = resp.json()
        except Exception as e:
            return None, f"get-clesson-run -> некорректный JSON: {e}"

        result: dict = {}
        resp = self.session.get(
            f"{self.API_BASE}/get-latest-clesson-result/{self.aid}/", headers=hdrs
        )
        if resp.status_code // 100 == 2:
            try:
                result = resp.json() or {}
            except Exception:
                result = {}
        if isinstance(result, dict) and result.get("statusCode") == 404:
            # результата ещё нет — урок не начат
            result = {}
        payload["data"]["getLatestCLessonResult"] = result
        return payload, ""

    def _load_data(self, lives=2) -> Status:
        if lives <= 0:
            return self._fail(Status.UNKNOWN_ERROR, "Max retries exceeded!")
        status = self._load_cookies_if_necessary()
        if status != Status.OK:
            return status

        html_problem = "урок не выбран" if not self.aid else ""
        captcha_seen = False
        data = None
        if self.aid:
            URL = f"https://education.yandex.ru/classroom/courses/{self.cid}/assignments/{self.aid}/run/1/"
            request = self.session.get(URL)
            html = request.text
            if "captcha" in html:
                captcha_seen = True
                html_problem = (
                    "Яндекс Учебник запросил подтверждение (captcha) на странице урока, "
                    f"итоговый URL: {request.url}"
                )
            elif request.status_code == 404:
                html_problem = f"Урок не найден (HTTP 404): {URL}"
            elif request.status_code // 100 != 2:
                html_problem = (
                    f"Сервер ответил HTTP {request.status_code}: {html[:300]}"
                )
            elif "window._data=" not in html:
                html_problem = (
                    "Страница урока не отдала данные (window._data), "
                    f"итоговый URL: {request.url}"
                )
            else:
                datatxt = html[html.find("window._data=") :][len("window._data=") :]
                datatxt = datatxt[: datatxt.find("</script>")]
                try:
                    data = json.loads(datatxt)
                except Exception as e:
                    html_problem = f"Error parsing JSON: {e}"

        if data is None:
            # Резервный путь: те же данные напрямую через API.
            # Работает, когда HTML-страницы недоступны (гео-блок, VPN и т.п.).
            api_data, api_err = self._fetch_api_data()
            if api_data is None:
                details = f"{html_problem}\n{api_err}".strip()
                if captcha_seen:
                    return self._fail(Status.CAPTCHA_DETECTED, details)
                return self._fail(Status.UNKNOWN_ERROR, details)
            if html_problem:
                self._add_msg(
                    f"[INFO] HTML-страница недоступна ({html_problem}) — "
                    "данные получены через API."
                )
            data = api_data

        self.data = data

        try:
            if self.aid and (
                "getCLessonRun" not in self.data["data"]
                or "getLatestCLessonResult" not in self.data["data"]
                or "id" not in (self.data["data"]["getLatestCLessonResult"] or {})
            ):
                self._add_msg(
                    "CLessonRun or CLessonResult not found in data, attempting to start CLesson."
                )
                st = self.start_clesson()
                if st != Status.OK:
                    return self._fail(
                        st, "Не удалось начать урок (start_clesson)."
                    )
                fresh, err = self._fetch_api_data()
                if fresh is None:
                    return self._fail(
                        Status.UNKNOWN_ERROR,
                        f"После старта урока данные не получены: {err}",
                    )
                self.data = fresh
            return Status.OK
        except Exception as e:
            return self._fail(Status.UNKNOWN_ERROR, f"Error parsing JSON: {e}")

    def get_courses(self) -> tuple[Status, list[dict], str]:
        resp = self.session.get(
            "https://education.yandex.ru/classroom/api/get-assigned-courses/"
        )
        if resp.status_code // 100 != 2:
            msg = f"Failed to get courses: {resp.text}"
            self._fail(Status.UNKNOWN_ERROR, msg)
            return Status.UNKNOWN_ERROR, [], msg
        data = resp.json()
        courses_debloated = []
        for course in data["courses"]:
            cid = course["id"]
            has_tasks = course["count_of_new_clessons"] > 0
            name = course["name"]
            count_of_tasks = course["count_of_new_clessons"]
            courses_debloated.append(
                {"id": cid, "name": name, "cnt": count_of_tasks, "ht": has_tasks}
            )
        return Status.OK, courses_debloated, "OK"

    def get_lessons(self, cid) -> tuple[Status, list[dict], str]:
        resp = self.session.get(
            f"https://education.yandex.ru/classroom/api/get-course-student-lessons/{cid}/?list_type=active&page_size=100"
        )
        if resp.status_code // 100 != 2:
            msg = f"Failed to get lessons: {resp.text}"
            self._fail(Status.UNKNOWN_ERROR, msg)
            return Status.UNKNOWN_ERROR, [], msg
        data = resp.json()
        lessons_debloated = []
        for lesson in data["clessons"]:
            lid = lesson["id"]
            name = lesson["lesson"]["name"]
            problems_cnt = lesson["assigned_problems"]
            lessons_debloated.append(
                {"id": lid, "name": name, "problems": problems_cnt}
            )
        return Status.OK, lessons_debloated, "OK"

    def start_clesson_if_necessary(self):
        if "getCLessonRun" not in self.data["data"]:
            return self.start_clesson()
        return Status.OK

    def get_name(self):
        st = self.load_data_if_necessary()
        if st != Status.OK:
            if self.last_msg:
                # msg уже получен (например, от _login) — не теряем его
                self._add_msg(
                    f"[{st.name}] Не удалось загрузить данные урока/профиля (getName)."
                )
            else:
                self._fail(
                    st, f"Не удалось загрузить данные урока/профиля ({st.name})."
                )
            return st, "ERROR"
        try:
            return Status.OK, self.data["data"]["getMe"]["public_name"]
        except Exception as e:
            self._fail(
                Status.UNKNOWN_ERROR, f"Не удалось получить имя пользователя: {e}"
            )
            return Status.UNKNOWN_ERROR, "ERROR"

    def get_problems(self) -> tuple[Status, list[dict]]:
        st = self.load_data_if_necessary()
        try:
            problems: list[dict] = self.data["data"]["getCLessonRun"]["problems"]
        except Exception as e:
            self._add_msg(f"[UNKNOWN_ERROR] Не удалось получить список задач: {e}")
            return Status.UNKNOWN_ERROR, []
        return st, problems

    def load_data_if_necessary(self) -> Status:
        if (
            self.data is None
            or len(self.data) == 0
            or "getMe" not in self.data.get("data", {})
        ):
            return self._load_data()
        if self.aid and (
            "getCLessonRun" not in self.data["data"]
            or "getLatestCLessonResult" not in self.data["data"]
            or "id" not in (self.data["data"]["getLatestCLessonResult"] or {})
        ):
            return self._load_data()
        return Status.OK

    def get_problem_type(self, problem_idx) -> tuple[Status, str]:
        self.load_data_if_necessary()
        problems = self.data["data"]["getCLessonRun"]["problems"]
        if int(problem_idx) > len(problems):
            return Status.PROBLEM_NOT_FOUND, "__UNKNOWN_PROBLEM_TYPE__"
        return Status.OK, problems[int(problem_idx) - 1]["problem"]["type"]

    def start_clesson(self):
        url = f"{self.API_BASE}/post-clesson-results/"
        try:
            resp = self.session.post(
                url,
                json={"clessonId": self.aid, "sk": self.get_sk()},
                headers=self._headers(),
            )
        except Exception as e:
            self._add_msg(f"[UNKNOWN_ERROR] Не удалось начать урок: {e}")
            return Status.UNKNOWN_ERROR
        if resp.status_code % 100 != 2:
            self._add_msg(
                f"[UNKNOWN_ERROR] Начало урока: HTTP {resp.status_code}: {resp.text[:300]}"
            )
            return Status.UNKNOWN_ERROR
        return Status.OK

    def _load_cookies_if_necessary(self) -> Status:
        return Status.OK if self.session.cookies else self._login()

    def get_problem_solver(
        self, problem_idx
    ) -> tuple[Status, BaseProblemSolver | None, str, str]:
        self.load_data_if_necessary()
        self.start_clesson_if_necessary()
        st, problem_type = self.get_problem_type(problem_idx)
        if st != Status.OK:
            msg = "Error during reading problem type"
            self.last_msg = msg
            return (
                st,
                None,
                "__UNKNOWN_PROBLEM_TYPE__",
                msg,
            )
        if problem_type not in self.solvers:
            msg = (
                f"None of solvers({self.solvers.items()}) support "
                f"{problem_type} problems."
            )
            self.last_msg = msg
            return (
                Status.SOLUTION_FAILURE_UNKNOWN_PROBLEM_TYPE,
                None,
                problem_type,
                msg,
            )
        elif len(self.solvers[problem_type]) > 1:
            print(
                f'WARNING: multiple solvers support problem type "{problem_type}". Normally this shouldn\'t happen. Defaulting to first detected solver.'
            )
        _solver = self.solvers[problem_type][0](
            self.cid, self.aid, self.session, self.data
        )
        return Status.OK, _solver, problem_type, "OK"

    def handle_problem_display_solution(self, problem_idx) -> tuple[Status, str, str]:
        st, _solver, p_type, msg = self.get_problem_solver(problem_idx)
        if st != Status.OK:
            return st, p_type, msg
        if _solver is None:
            return (
                Status.UNKNOWN_ERROR,
                p_type,
                f"{msg}\n_solver is None, but solver find status is OK. This should never happen, but it happened. This is problem with script, not server, account, etc.",
            )
        st, msg1 = _solver.readable_solution(problem_idx)
        return st, p_type, msg + "\n" + msg1

    def handle_problem_solution(
        self, problem_idx: int, fake_timedelta=-1
    ) -> tuple[Status, str, str]:
        if fake_timedelta == -1:
            fake_timedelta = random.randint(self.MIN_RAND_TD, self.MAX_RAND_TD)
        st, _solver, p_type, msg = self.get_problem_solver(problem_idx)
        if st != Status.OK:
            return st, p_type, msg
        if _solver is None:
            return (
                Status.UNKNOWN_ERROR,
                p_type,
                f"{msg}\n_solver is None, but solver find status is OK. This should never happen, but it happened. This is problem with script, not server, account, etc.",
            )
        st, msg1 = _solver.send_solution(problem_idx, fake_timedelta)
        return st, p_type, msg + "\n" + msg1
