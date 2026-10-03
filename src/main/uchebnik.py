import json
import random

import requests

from main.solver import BaseProblemSolver, get_problem_solvers
from main.util import Status, login_with_creds


class YandexUchebnik:
    MIN_RAND_TD = 20
    MAX_RAND_TD = 180

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

    def _login(self):
        status, msg = login_with_creds(self.username, self.sch, self.session)
        return status

    def _load_data(self, lives=2) -> Status:
        if lives <= 0:
            self.new_msgs.append("Max retries exceeded!")
            print(self.new_msgs[-1])
            return Status.UNKNOWN_ERROR
        status = self._load_cookies_if_necessary()
        if status != Status.OK:
            return status
        URL = f"https://education.yandex.ru/classroom/courses/{self.cid}/assignments/{self.aid}/run/1/"
        request = self.session.get(URL)
        html = request.text
        if "captcha" in html:
            return Status.CAPTCHA_DETECTED
        if request.status_code == 404:
            return Status.ASSIGNMENT_NOT_FOUND
        if request.status_code // 100 != 2:
            return Status.UNKNOWN_ERROR
        if "window._data=" not in html:
            return Status.UNKNOWN_ERROR

        datatxt = html[html.find("window._data=") :][len("window._data=") :]
        datatxt = datatxt[: datatxt.find("</script>")]
        try:
            self.data = json.loads(datatxt)
            if (
                "getCLessonRun" not in self.data["data"]
                or "getLatestCLessonResult" not in self.data["data"]
                or ("id" not in self.data["data"]["getLatestCLessonResult"])
            ) and self.aid:
                self.new_msgs.append(
                    "CLessonRun or CLessonResult not found in data, attempting to start CLesson."
                )
                print(self.new_msgs[-1])
                self.start_clesson()
                self._load_data(lives - 1)
            return Status.OK
        except Exception as e:
            self.new_msgs.append(f"Error parsing JSON: {e}")
            print(self.new_msgs[-1])
            return Status.UNKNOWN_ERROR

    def get_courses(self) -> tuple[Status, list[dict], str]:
        resp = self.session.get(
            "https://education.yandex.ru/classroom/api/get-assigned-courses/"
        )
        if resp.status_code // 100 != 2:
            return Status.UNKNOWN_ERROR, [], f"Failed to get courses: {resp.text}"
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
            return Status.UNKNOWN_ERROR, [], f"Failed to get lessons: {resp.text}"
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
            return st, "ERROR"
        try:
            return Status.OK, self.data["data"]["getMe"]["public_name"]
        except:
            return Status.UNKNOWN_ERROR, "ERROR"

    def get_problems(self) -> tuple[Status, list[dict]]:
        st = self.load_data_if_necessary()
        problems: list[dict] = self.data["data"]["getCLessonRun"]["problems"]
        return st, problems

    def load_data_if_necessary(self) -> Status:
        if (
            self.data is None
            or len(self.data) == 0
            or "getCLessonRun" not in self.data["data"]
            or "getLatestCLessonResult" not in self.data["data"]
            or "id" not in self.data["data"]["getLatestCLessonResult"]
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
        url = "https://education.yandex.ru/classroom/api/post-clesson-results/"
        resp = requests.post(
            url,
            json={"clessonId": self.aid, "sk": self.data["config"]["sk"]},
            cookies=self.cookies,
        )
        return Status.OK if resp.status_code % 100 == 2 else Status.UNKNOWN_ERROR

    def _load_cookies_if_necessary(self) -> Status:
        return Status.OK if self.session.cookies else self._login()

    def get_problem_solver(
        self, problem_idx
    ) -> tuple[Status, BaseProblemSolver | None, str, str]:
        self.load_data_if_necessary()
        self.start_clesson_if_necessary()
        st, problem_type = self.get_problem_type(problem_idx)
        if st != Status.OK:
            return (
                st,
                None,
                "__UNKNOWN_PROBLEM_TYPE__",
                "Error during reading problem type",
            )
        if problem_type not in self.solvers:
            return (
                Status.SOLUTION_FAILURE_UNKNOWN_PROBLEM_TYPE,
                None,
                problem_type,
                f"None of solvers({self.solvers.items()}) support {problem_type} problems.",
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
