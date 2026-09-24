import builtins
import os, re
import sys
import traceback, random
from enum import Enum
from http.cookiejar import MozillaCookieJar
from itertools import count


print("Beta enabled status:", os.getenv("YUF_ENABLE_BETA_FEATURES", "1"))
ENABLE_BETA_FEATURES = os.getenv("YUF_ENABLE_BETA_FEATURES", "1") == "1"
try:
    import requests
except ImportError:
    print("Trying to install requests module.")
    import pip

    pip.main(['install', 'requests'])
    import requests
import json


def input(prompt):
    return builtins.input(prompt).strip()


class Status(Enum):
    OK = 0
    COOKIES_NOT_FOUND = 1
    COOKIES_PARSE_ERROR = 2
    CAPTCHA_DETECTED = 3
    ASSIGNMENT_NOT_FOUND = 4
    PROBLEM_NOT_FOUND = 5
    WRONG_PROBLEM_TYPE = 6
    WRONG_INPUT = 7
    COOKIES_GENERATE_ERROR = 8
    SOLUTION_FAILURE_WRONG_ANSWER=9
    SOLUTION_FAILURE_UNKNOWN_PROBLEM_TYPE=10
    SOLUTION_FAILURE_ALREADY_SOLVED_OR_NO_ATTEMPTS=11
    UNKNOWN_ERROR = 12


class Solver:
    def __init__(self, cid, aid, cookies_path="cookies.txt",
                 credentials=None):
        self.cid = cid
        self.aid = aid
        self.data = None
        self.cookies = {}
        self.use_creds = False
        self.username = None
        self.sch = None
        self.cookies_path = cookies_path
        if credentials:
            self.use_creds = True
            self.username = credentials["login"]
            self.sch = credentials["code"]
        else:
            self.cookies_path = cookies_path

    def _login_with_creds(self):
        session = requests.Session()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9',
            'Origin': 'https://education.yandex.ru',
            'Referer': 'https://education.yandex.ru/kids/',
        }

        try:
            response = session.get(
                "https://education.yandex.ru/kids/", headers=headers)
            response.raise_for_status()
            sk_match = re.search(r'"sk":"(.*?)"', response.text)
            if not sk_match:
                sk = session.cookies.get('_csrf',
                                         domain='.yandex.ru')
            else:
                sk = sk_match.group(1)

            if not sk:
                return Status.COOKIES_GENERATE_ERROR, "CSRF token not found"

            api_headers = headers.copy()
            api_headers.update({
                'Content-Type': 'application/json',
                'x-csrf-token': sk,
                'X-Requested-With': 'XMLHttpRequest'
            })

            v_res = session.post(
                "https://education.yandex.ru/classroom/api/post-verify-school-code/",
                json={"schoolCode": self.sch, "sk": sk},
                headers=api_headers)
            if v_res.status_code // 100 >= 4:
                return Status.COOKIES_GENERATE_ERROR, None, v_res.text

            l_res = session.post(
                "https://education.yandex.ru/classroom/api/post-submit-student-login/",
                json={"studentLogin": self.username, "sk": sk},
                headers=api_headers)
            if l_res.status_code // 100 >= 4:
                return Status.COOKIES_GENERATE_ERROR, l_res.text

            if 'schoolbook-auth-token' in session.cookies:
                self.cookies = requests.utils.dict_from_cookiejar(
                    session.cookies)
                return Status.OK, "OK"
            else:
                return Status.COOKIES_GENERATE_ERROR, "Cookie not found"

        except Exception as e:
            return Status.UNKNOWN_ERROR, e

    def _load_cookies(self):
        if self.use_creds:
            status, msg = self._login_with_creds()
            print(msg)
            return status
        if not os.path.exists(self.cookies_path):
            return Status.COOKIES_NOT_FOUND
        jar = MozillaCookieJar(self.cookies_path)
        try:
            jar.load()
            self.cookies = requests.utils.dict_from_cookiejar(jar)
            return Status.OK
        except Exception as e:
            print(f"Error loading cookies: {e}")
            return Status.COOKIES_PARSE_ERROR

    def _load_data(self, lives=2):
        if lives <= 0:
            print("Max retries exceeded!")
            return Status.UNKNOWN_ERROR
        status = self._load_cookies_if_necessary()
        if status != Status.OK:
            return status
        URL = f"https://education.yandex.ru/classroom/courses/{self.cid}/assignments/{self.aid}/run/1/"
        request = requests.get(URL, cookies=self.cookies)
        html = request.text
        if "captcha" in html:
            return Status.CAPTCHA_DETECTED
        if request.status_code == 404:
            return Status.ASSIGNMENT_NOT_FOUND
        if request.status_code // 100 != 2:
            return Status.UNKNOWN_ERROR
        if "window._data=" not in html:
            return Status.UNKNOWN_ERROR

        datatxt = html[html.find("window._data="):][
            len("window._data="):]
        datatxt = datatxt[:datatxt.find("</script>")]
        try:
            self.data = json.loads(datatxt)
            if ("getCLessonRun" not in self.data["data"] or "getLatestCLessonResult" not in self.data["data"] or ("id" not in self.data["data"]["getLatestCLessonResult"])) and self.aid:
                print("CLessonRun or CLessonResult not found in data, attempting to start CLesson.")
                self.start_clesson()
                self._load_data(lives-1)
            return Status.OK
        except Exception as e:
            print(f"Error parsing JSON: {e}")
            return Status.UNKNOWN_ERROR
    def get_courses(self):
        resp=requests.get("https://education.yandex.ru/classroom/api/get-assigned-courses/", cookies=self.cookies)
        if resp.status_code // 100 != 2:
            print("Failed to get courses:", resp.text)
            return Status.UNKNOWN_ERROR, None
        data=resp.json()
        courses_debloated=[]
        for course in data["courses"]:
            cid=course["id"]
            has_tasks=course["count_of_new_clessons"]>0
            name=course["name"]
            count_of_tasks=course["count_of_new_clessons"]
            courses_debloated.append({"id": cid, "name": name, "cnt": count_of_tasks, "ht": has_tasks})
        return Status.OK, courses_debloated
    def get_lessons(self, cid):
        resp=requests.get("https://education.yandex.ru/classroom/api/get-course-student-lessons/15834836/?list_type=active&page_size=100", cookies=self.cookies)
        if resp.status_code // 100 != 2:
            print("Failed to get lessons:", resp.text)
            return Status.UNKNOWN_ERROR, None
        data=resp.json()
        lessons_debloated=[]
        for lesson in data["clessons"]:
            lid=lesson["id"]
            name=lesson["lesson"]["name"]
            problems_cnt=lesson["assigned_problems"]
            lessons_debloated.append({"id": lid, "name": name, "problems": problems_cnt})
        return Status.OK, lessons_debloated

    def load_data_if_necessary(self):
        if self.data is None or len(self.data) == 0 or "getCLessonRun" not in self.data["data"] or "getLatestCLessonResult" not in self.data["data"] or "id" not in self.data["data"]["getLatestCLessonResult"]:
            return self._load_data()
        return Status.OK

    def coding_solution(self, problem_idx):
        self.load_data_if_necessary()
        if "getCLessonRun" not in self.data["data"]:
            st = self.start_clesson()
            if st != Status.OK:
                return st, None, None
        problems = self.data["data"]["getCLessonRun"]["problems"]
        problem_idx = int(problem_idx)
        if problem_idx > len(problems):
            return Status.PROBLEM_NOT_FOUND, None, None
        problem = problems[problem_idx - 1]["problem"]
        if problem["type"] != "coding":
            return Status.WRONG_PROBLEM_TYPE, None, None
        sol = problem["markup"]["languages"][0]["author_solution"]
        prid = problems[problem_idx - 1]["id"]
        return Status.OK, sol, prid

    def _send_coding_solution(self, lpl_id, solution):
        data = {
            "attempt": {
                "answered": True,
                "completed": True,
                "markers": {"user_answer": {"code": solution,
                                            "language": "python"}}
            },
            "clr_id": self.data["data"]["getLatestCLessonResult"][
                "id"],
            "lpl_id": lpl_id,
            "sk": self.data["config"]["sk"]
        }
        resp = requests.post(
            "https://education.yandex.ru/classroom/api/v2/post-attempts/",
            json=data, cookies=self.cookies)
        if resp.status_code // 100 != 2:
            return Status.UNKNOWN_ERROR
        return Status.OK

    def get_name(self):
        st = self.load_data_if_necessary()
        if st != Status.OK: return st, "ERROR"
        try:
            return Status.OK, self.data["data"]["getMe"][
                "public_name"]
        except:
            return Status.UNKNOWN_ERROR, "ERROR"

    def _post_fake_timedelta(self, lpl_id, fake_timedelta=0):
        clr_id = self.data["data"]["getLatestCLessonResult"]["id"]
        spent_time_json = {"link_id": lpl_id,
                           "time_delta": fake_timedelta,
                           "sk": self.data["config"]["sk"]}
        resp = requests.post(
            f"https://education.yandex.ru/classroom/api/post-clesson-results-update-spent-time/{clr_id}/",
            json=spent_time_json, cookies=self.cookies)
        return Status.OK if resp.status_code // 100 == 2 else Status.UNKNOWN_ERROR

    def get_problems(self):
        self.load_data_if_necessary()
        return self.data["data"]["getCLessonRun"]["problems"]

    def submit_coding_solution(self, sol, prid, fake_timedelta=0):
        self.load_data_if_necessary()
        self._post_fake_timedelta(prid, fake_timedelta)
        return self._send_coding_solution(prid, sol)

    def get_problem_type(self, problem_idx):
        self.load_data_if_necessary()
        problems = self.data["data"]["getCLessonRun"]["problems"]
        if int(problem_idx) > len(
            problems): return Status.PROBLEM_NOT_FOUND, None
        return Status.OK, problems[int(problem_idx) - 1]["problem"][
            "type"]

    def _check_marker_solution(self, resp_json, prid):
        answer_obj = resp_json["answers"][str(prid)][-1]
        mist = [k for k, v in answer_obj["markers"].items() if
                v["mistakes"] > 0]
        return len(mist) > 0, mist

    def clean_markup(self, text):
        # Очистка текста от тегов типа {sizedText:small}
        return re.sub(
            r'\\?\{sizedText:.*?\}|\\?\{\\\\sizedText\}', '',
            str(text)).replace("\xa0", "")
    def _extract_text(self, problem):
        if problem["problem"]["type"]=="coding": return Status.WRONG_PROBLEM_TYPE, ""
        res=[]
        lyt=problem["problem"]["markup"]["layout"]
        for el in lyt:
            if el["kind"]=="text":
                res.append(el["content"]["text"])
        return Status.OK, self.clean_markup("\n".join(res))
    def extract_text(self, idx):
        problem=self.data["data"]["getCLessonRun"]["problems"][idx-1]
        return self._extract_text(problem)

    def _send_marker_solution(self, sol, prid):
        clr_id = self.data["data"]["getLatestCLessonResult"]["id"]
        data = {
            "clessonId": self.cid, "problemLinkId": prid,
            "resultId": clr_id,
            "answered": True, "completed": True,
            "answer": sol,
            "sk": self.data["config"]["sk"]
        }
        resp = requests.post(
            "https://education.yandex.ru/classroom/api/patch-clesson-results/",
            cookies=self.cookies, json=data)
        if resp.status_code // 100 != 2:
            print(f"status code: {resp.status_code}, data: {resp.text}");
            try:
                data1=resp.json()
                if len(data1.get("errors", [])) > 0 and "attempt limit" in data1.get("errors", [])[0].get("message"):
                    return Status.SOLUTION_FAILURE_ALREADY_SOLVED_OR_NO_ATTEMPTS, (False, []), resp.text
            except Exception as e:
                Status.UNKNOWN_ERROR, (True, [-1]), False
            return Status.UNKNOWN_ERROR, (True, [-1]), False
        was_mist, mist = self._check_marker_solution(resp.json(),
                                    prid)
        return Status.OK if not was_mist else Status.SOLUTION_FAILURE_WRONG_ANSWER, (was_mist, mist), resp.text

    def _prepare_marker_solution(self, answers, problem):
        # 1. Собираем маппинг ID маркера -> Тип маркера
        marker_types = {}
        for el in problem["markup"]["layout"]:
            if el["kind"] == "marker":
                marker_types[str(el["content"]["id"])] = \
                el["content"]["type"]

        res = {}
        for mid, ans_data in answers.items():
            m_type = marker_types.get(str(mid))
            if m_type == "inline":
                inner_payload = {}
                for inp_id, val in ans_data.items():
                    inner_payload[str(inp_id)] = val[
                        0] if isinstance(val, list) else val
                res[str(mid)] = {"user_answer": inner_payload}
            elif m_type == "choice":
                res[str(mid)] = {"user_answer": ans_data}
            elif m_type == "chooseimage":
                inner_payload = ans_data[0]
                res[str(mid)] = {"user_answer": inner_payload}
                #return Status.SOLUTION_FAILURE_UNKNOWN_PROBLEM_TYPE, False # mock
            elif m_type == "dragimage":
                inner_payload = ans_data
                res[str(mid)] = {"user_answer": inner_payload}
            elif m_type=="highlight":
                inner_payload = ans_data[0]
                res[str(mid)] = {"user_answer": inner_payload}
            else:
                return Status.SOLUTION_FAILURE_UNKNOWN_PROBLEM_TYPE, False
                res[str(mid)] = ans_data
        return Status.OK, res

    def _pre_send_marker_solution(self, lpl_id, fake_timedelta=0):
        return self._post_fake_timedelta(lpl_id, fake_timedelta)
    # DANGER - untested
    def send_marker_solution(self, problem_idx, fake_timedelta=0):
        status, problem, answers, prid = self._marker_solution(
            problem_idx)
        if status != Status.OK: return status, ([-1], True), ""
        st, prepared = self._prepare_marker_solution(answers, problem)
        if st==Status.SOLUTION_FAILURE_UNKNOWN_PROBLEM_TYPE:
            return Status.SOLUTION_FAILURE_UNKNOWN_PROBLEM_TYPE, ([-1], True), ""
        dt=json.dumps(prepared, separators=(",", ":"))
        print(dt)
        #return Status.UNKNOWN_ERROR, -1, []
        self._pre_send_marker_solution(prid, fake_timedelta)
        return self._send_marker_solution(dt, prid)

    def _marker_solution(self, problem_idx):
        self.load_data_if_necessary()
        problems = self.data["data"]["getCLessonRun"]["problems"]
        idx = int(problem_idx) - 1
        if idx >= len(
            problems): return Status.PROBLEM_NOT_FOUND, None, None, None
        problem = problems[idx]["problem"]
        if problem[
            "type"] != "practice": return Status.WRONG_PROBLEM_TYPE, None, None, None
        return Status.OK, problem, problem["markup"]["answers"], \
        problems[idx]["id"]
    def send_theory_solution(self, problem_idx, fake_timedelta=10):
        self.load_data_if_necessary()
        problems = self.data["data"]["getCLessonRun"]["problems"]
        idx = int(problem_idx) - 1
        if idx >= len(
            problems): return Status.PROBLEM_NOT_FOUND, None, None, None
        problem = problems[idx]["problem"]
        if problem[
            "type"] != "theory": return Status.WRONG_PROBLEM_TYPE, None, None, None
        clr_id = self.data["data"]["getLatestCLessonResult"]["id"]
        data = {
            "clessonId": self.cid, "problemLinkId": problems[idx]["id"],
            "resultId": clr_id,
            "answered": True, "completed": True,
            "answer": "{}",
            "sk": self.data["config"]["sk"]
        }
        resp = requests.post(
            "https://education.yandex.ru/classroom/api/patch-clesson-results/",
            cookies=self.cookies, json=data)
        if resp.status_code // 100 != 2: print(f"status code: {resp.status_code}, data: {resp.text}");return Status.UNKNOWN_ERROR, False
        return Status.OK

    def marker_solution(self, problem_idx):
        status, problem, answers, prid = self._marker_solution(
            problem_idx)
        if status != Status.OK: return status, None

        def clean_markup(text):
            # Очистка текста от тегов типа {sizedText:small}
            return re.sub(
                r'\\?\{sizedText:.*?\}|\\?\{\\\\sizedText\}', '',
                str(text))


        readable_answers = []
        for el in problem["markup"]["layout"]:
            if el["kind"] == "marker":
                mid = str(el["content"]["id"])
                ans = answers.get(mid)
                if ans is None: continue

                mo = el["content"]["options"]
                mt = el["content"]["type"]

                if mt == "inline":
                    text_template = mo["text"]
                    # Находим все вхождения {input:N}
                    input_tags = re.findall(r"\{input:([1-9]\d*)\}",
                                            text_template)
                    input_configs = mo.get("inputs", {})

                    vals = []
                    for tid in input_tags:
                        v = ans.get(tid)
                        conf = input_configs.get(tid, {})
                        itype = conf.get("type")
                        if itype == "choice":
                            choices = conf["options"]["choices"]
                            vals.append(clean_markup(
                                choices[v] if isinstance(v,
                                                         int) else v))
                        elif itype == "field":
                            # Для field значение лежит в списке [ "текст" ]
                            vals.append(clean_markup(
                                v[0] if isinstance(v, list) else v))
                        else:
                            vals.append(clean_markup(v))

                    # Формируем читаемую строку
                    clean_template = re.sub(r'\{input:[1-9]\d*\}',
                                            '{}', clean_markup(
                            text_template))
                    readable_answers.append(
                        clean_template.format(*vals))

                elif mt == "choice":
                    choices = mo["choices"]
                    selected = [clean_markup(choices[i]) for i in
                                ans]
                    readable_answers.append(" / ".join(selected))

                elif mt == "chooseimage":
                    readable_answers.append(
                        f"Выбранные зоны (ID): {', '.join(map(str,ans))}")

                else:
                    readable_answers.append(f"[{mt}] RAW: {ans}")

        return Status.OK, readable_answers

    def start_clesson(self):
        url = "https://education.yandex.ru/classroom/api/post-clesson-results/"
        resp = requests.post(url, json={"clessonId": self.aid,
                                 "sk": self.data["config"]["sk"]},
                      cookies=self.cookies)
        return Status.OK if resp.status_code % 100 == 2 else Status.UNKNOWN_ERROR

    def _load_cookies_if_necessary(self):
        return Status.OK if self.cookies else self._load_cookies()


def print_table(s):
    if "|" not in s:
        print(s)
        return
    rows = []
    for line in s.strip().split('\n'):
        if "|" in line:
            parts = [p.strip(' `') for p in line.split('|') if
                     p.strip()]
            if parts: rows.append(parts)
    if not rows:
        print(s)
        return

    widths = [max(len(row[i]) for row in rows) for i in
              range(len(rows[0]))]
    sep = '┼'.join('─' * (w + 2) for w in widths)
    print('┌' + '┬'.join('─' * (w + 2) for w in widths) + '┐')
    for i, row in enumerate(rows):
        print('│ ' + ' │ '.join(val.ljust(widths[j]) for j, val in
                                enumerate(row)) + ' │')
        if i < len(rows) - 1: print('├' + sep + '┤')
    print('└' + '┴'.join('─' * (w + 2) for w in widths) + '┘')


def print_marker_solution(s: Solver, i: int, send_by_default=False):
    st, an = s.marker_solution(i)
    if st == Status.OK:
        for aa in an: print_table(aa)
        if ENABLE_BETA_FEATURES and send_by_default or input(
                f"Submit solution for {i}? (y/n): ").lower() in {
            "y", "yes", "1", "д", "да"}:
            a=s.send_marker_solution(i, random.randint(60, 150))
            st, (was_mist, mist), dt=a
            print(f"Solution status: {st}, Response: {dt}")
            if st == Status.SOLUTION_FAILURE_ALREADY_SOLVED_OR_NO_ATTEMPTS:
                print("Failed to send solution. Problem may be already solved or all attempts exhausted.", file=sys.stderr)
            elif was_mist and mist[0]!=-1: print(f"SOLVED WITH MISTAKES! Mistakes: {mist}", file=sys.stderr)
            elif was_mist:
                print("FAILED TO SOLVE: REQUEST ERROR!", file=sys.stderr)

    else:
        print(f"Error: {st.name}")


def print_coding_solution(s: Solver, i: int, send_by_default=False):
    st, sol, prid = s.coding_solution(i)
    if st != Status.OK:
        print(f"Error: {st.name}")
        return
    print(f"\n--- AUTHOR SOLUTION ---\n{sol}\n--- END ---")
    if send_by_default or input("Submit this solution? (y/n): ").lower() == "y":
        td = int(input("Time delta (sec): ") or "30")
        print("Status:", s.submit_coding_solution(sol, prid, td))


def print_problem(s: Solver, i: int, send_by_default=False):
    st, t = s.get_problem_type(i)
    print(f"\n{'=' * 20} Problem {i} ({t}) {'=' * 20}")
    if st != Status.OK:
        print(f"Error: {st.name}")
    elif t == "theory":
        print(s.extract_text(i))
        print("Marking as complete....")
        s.send_theory_solution(i, random.randint(1, 10))
    elif t == "practice":
        print(s.extract_text(i))
        print_marker_solution(s, i, send_by_default)
    elif t == "coding":
        print_coding_solution(s, i, send_by_default)


def load_ids_fallback(cid):
    a="foo"
    while not "education.yandex.ru" in a and not a.isdigit():
        a = input(f"Enter {'course' if cid is not None else 'assignment'} ID or task link: ")
        if not "education.yandex.ru" in a and not a.isdigit():
            print("Must be yandex uchebnik link or integer")
    if cid is None:
        cid=a
        aid="foo"
        while not aid.isdigit():
            aid=input("Enter assignment ID: ")
            if not aid.isdigit():
                print("Must be integer")
    else:
        aid=a
    if "education.yandex.ru" in a:
        cid = re.search(r'courses/(\d+)', a).group(1)
        aid = re.search(r'assignments/(\d+)', a).group(1)
    return Status.OK, cid, aid
def ask_course_and_assignment(solver: Solver):
    st, courses = solver.get_courses()
    if st != Status.OK:
        return st, None, None
    print(f"Select course:")
    for i, c in enumerate(courses):
        print(f"{i+1}:", "; ".join(map(lambda x: "=".join(map(str, x)), c.items())))
    n=-1
    valid=False
    while not valid:
        n=int(input(f"Enter course number(1-{len(courses)}): "))
        if n>len(courses):
            print(f"Course number out of range({n} > {len(courses)}).")
        elif n<1:
            print("Course number out of range(must be at least 1).")
        else:
            valid=True
    cid=courses[n-1]["id"]
    st, assignments=solver.get_lessons(cid)
    if st != Status.OK:
        return st, cid, None
    print(f"Select assignment:")
    for i, a in enumerate(assignments):
        print(f"{i + 1}:", "; ".join(map(lambda x: "=".join(map(str, x)), a.items())))
    n=-1
    valid=False
    while not valid:
        n=int(input(f"Enter assignment number(1-{len(assignments)}): "))
        if n>len(assignments):
            print(f"Assignment number out of range({n} > {len(assignments)}).")
        elif n<1:
            print("Assignment number out of range(must be at least 1).")
        else:
            valid=True
    return st, cid, assignments[n-1]["id"]
def main():
    path = input(
        "Cookies path (blank for cookies.txt) or '*' for login: ")
    creds = None
    if path == "*":
        creds = {"login": input("Login: "),
                 "code": input("School Code: ")}
        path = "cookies.txt"

    solver = Solver(None, None, path or "cookies.txt", creds)
    st, name = solver.get_name()
    if st != Status.OK:
        print("Auth failed.")
        return
    print(f"User: {name}")
    st, cid, aid = ask_course_and_assignment(solver)
    if st != Status.OK:
        print(f"Error: {st.name}")
        print("Falling back to manual selection.")
        st, cid, aid = load_ids_fallback(cid)
    solver.cid = cid
    solver.aid = aid
    cmd = input("Problem number or '*' for all: ")
    if cmd == "*":
        send_by_default = input("Send problems by default? (y/n): ").lower().strip() in {"y", "yes", "д", "да"}
        for i in range(1,
                       len(solver.get_problems()) + 1): print_problem(
            solver, i, send_by_default)
    else:
        print_problem(solver, int(cmd))
    print("Done.")

if __name__ == "__main__":
    main()
