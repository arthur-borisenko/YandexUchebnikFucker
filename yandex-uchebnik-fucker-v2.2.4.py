import builtins
import os, re
from enum import Enum
from http.cookiejar import MozillaCookieJar

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
    WRONG_INPUT=7
    COOKIES_GENERATE_ERROR=8
    UNKNOWN_ERROR = 9


class Solver:
    def __init__(self, cid, aid, cookies_path="cookies.txt", credentials=None):
        self.cid = cid
        self.aid = aid
        self.data = None
        self.cookies = {}
        self.use_creds = False
        self.username = None
        self.sch = None
        self.cookies_path = cookies_path
        if credentials:
            self.use_creds=True
            self.username=credentials["login"]
            self.sch=credentials["code"]
        else:
            self.cookies_path = cookies_path

    def _login_with_creds(self):
        """
        Выполняет авторизацию и возвращает объект RequestsCookieJar.
        """
        session = requests.Session()

        # Стандартные заголовки для имитации живого человека
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9',
            'Origin': 'https://education.yandex.ru',
            'Referer': 'https://education.yandex.ru/kids/',
        }

        try:
            response = session.get(
                "https://education.yandex.ru/kids/",
                headers=headers)
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

            verify_url = "https://education.yandex.ru/classroom/api/post-verify-school-code/"
            verify_payload = {"schoolCode": self.sch, "sk": sk}

            v_res = session.post(verify_url, json=verify_payload,
                                 headers=api_headers)
            if v_res.status_code // 100 >= 4:
                return Status.COOKIES_GENERATE_ERROR, None, v_res.text

            login_url = "https://education.yandex.ru/classroom/api/post-submit-student-login/"
            login_payload = {"studentLogin": self.username, "sk": sk}

            l_res = session.post(login_url, json=login_payload,
                                 headers=api_headers)
            if l_res.status_code//100>=4:
                return Status.COOKIES_GENERATE_ERROR, l_res.text
            if 'schoolbook-auth-token' in session.cookies:
                self.cookies=requests.utils.dict_from_cookiejar(session.cookies)
                return Status.OK, "OK"
            else:
                return Status.COOKIES_GENERATE_ERROR, "Cookie not found"

        except Exception as e:
            return Status.UNKNOWN_ERROR, e

    def _load_cookies(self):
        if self.use_creds:
            status, msg=self._login_with_creds()
            print(msg)
            return status
        if not os.path.exists(self.cookies_path):
            return Status.COOKIES_NOT_FOUND
        jar = MozillaCookieJar(self.cookies_path)
        try:
            jar.load()
            print(
                f"Loaded cookies: {requests.utils.dict_from_cookiejar(jar)} from {self.cookies_path}.")
            self.cookies = requests.utils.dict_from_cookiejar(jar)
            return Status.OK
        except Exception as e:
            print(f"Error loading cookies: {e}")
            return Status.COOKIES_PARSE_ERROR

    def _load_data(self):
        v = 1
        if os.path.exists(f"data_{self.aid}.json"):
            v = input("Cached data. override(y/n): ").lower() == "y"
        if v:
            status = self._load_cookies()
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
                print(
                    f"ERROR: server returned {request.status_code} with message: {request.text}")
                return Status.UNKNOWN_ERROR
            if "window._data=" not in html:
                return Status.UNKNOWN_ERROR
            datatxt = html[html.find("window._data="):][
                len("window._data="):]
            datatxt = datatxt[:datatxt.find("</script>")]
            print(datatxt,
                  file=open(f"data_{self.aid}.json", "w",
                            encoding="utf-8"))
        else:
            datatxt = open(f"data_{self.aid}.json", "r",
                           encoding="utf-8").read()
        try:
            self.data = json.loads(datatxt)
            return Status.OK
        except Exception as e:
            print(f"Error parsing JSON: {e}")
            return Status.UNKNOWN_ERROR

    """    cid=input("Enter course ID or blank to default: ")
        cid = cid if cid else "14848489"
        aid = input("Enter assignment ID: ")
            if problem_idx == "*":
            for i, problem1 in enumerate(problems, start=1):
                problem = problem1["problem"]
                print(f"{'-' * 25}Problem {i}{'-' * 25}")
                if problem["type"] != "coding":
                    print(f"Not a coding problem.")
                    continue
                print(problem["markup"]["languages"][0]["author_solution"])
            exit(0)
                problem_idx = input("Enter problem number or * to show all: ")
                    if not has_cookies:
            cookies = load_cookies()"""

    def load_data_if_necessary(self):
        if self.data is None or len(self.data) == 0:
            return self._load_data()
        return Status.OK

    def coding_solution(self, problem_idx):
        self.load_data_if_necessary()
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
                "markers": {
                    "user_answer": {
                        "code": solution,
                        "language": "python"
                    }
                }
            },
            "clr_id": self.data["data"]["getLatestCLessonResult"][
                "id"],
            "lpl_id": lpl_id,
            "sk": self.data["config"]["sk"]
        }
        print("Forged request:")
        print(data)
        print("Sending...")
        resp = requests.post(
            "https://education.yandex.ru/classroom/api/v2/post-attempts/",
            json=data, cookies=self.cookies)
        print("Response status:", resp.status_code)
        if resp.status_code // 100 != 2:
            print(
                f"Error: server responded with status {resp.status_code} and {resp.text}")
            return Status.UNKNOWN_ERROR
        return Status.OK
    def get_name(self):
        st=self.load_data_if_necessary()
        if st!=Status.OK:
            return st, "ERROR"
        try:
            return Status.OK,self.data["data"]["getMe"]["public_name"]
        except Exception as e:
            return Status.UNKNOWN_ERROR, "ERROR"
    def _pre_send_coding_solution(self, lpl_id, fake_timedelta=0):
        clr_id = self.data["data"]["getLatestCLessonResult"][
            "id"]
        spent_time_ep = f"https://education.yandex.ru/classroom/api/post-clesson-results-update-spent-time/{clr_id}/"
        spent_time_json = {"link_id": lpl_id,
                           "time_delta": fake_timedelta,
                           "id": "57f5cd7f-58ae-426a-994c-5b8bd613377e",
                           "sk": self.data["config"]["sk"]}
        resp = requests.post(spent_time_ep, json=spent_time_json,
                             cookies=self.cookies)
        if resp.status_code // 100 != 2:
            print(
                f"Error: server responded with status {resp.status_code} and {resp.text}")
            return Status.UNKNOWN_ERROR
        return Status.OK

    def get_problems(self):
        self.load_data_if_necessary()
        return self.data["data"]["getCLessonRun"]["problems"]

    def submit_coding_solution(self, sol, prid, fake_timedelta=0):
        self.load_data_if_necessary()
        if len(self.cookies) == 0:
            status = self._load_cookies()
            if status != Status.OK:
                return status
        status = self._pre_send_coding_solution(prid, fake_timedelta)
        if status != Status.OK:
            return status
        status = self._send_coding_solution(prid, sol)
        return status

    def get_problem_type(self, problem_idx):
        self.load_data_if_necessary()
        problems = self.data["data"]["getCLessonRun"]["problems"]
        problem_idx = int(problem_idx)
        if problem_idx > len(problems):
            return Status.PROBLEM_NOT_FOUND, None
        problem = problems[problem_idx - 1]["problem"]
        return Status.OK, problem["type"]

    def marker_solution(self, problem_idx):
        self.load_data_if_necessary()
        problems = self.data["data"]["getCLessonRun"]["problems"]
        problem_idx = int(problem_idx)
        if problem_idx > len(problems):
            return Status.PROBLEM_NOT_FOUND, None, None
        problem = problems[problem_idx - 1]["problem"]
        if problem["type"] != "practice":
            return Status.WRONG_PROBLEM_TYPE, None, None
        answers = problem["markup"]["answers"]
        markers = []
        for el in problem["markup"]["layout"]:
            if el["kind"] == "marker":
                markers.append(el)
        readable_answers = []
        for marker in markers:
            i = marker["content"]["id"]
            ans = answers[str(i)]
            mo = marker["content"]["options"]
            if "text" in mo:
                dt=mo["text"]
                input_ids = re.findall(r"\{input:[1-9]\d*}", dt)
                ad = list(
                    map(lambda x, _ans=ans: _ans[x[7:-1]], input_ids))
                template = re.sub(r'\{input:[1-9]\d*}', '{}', dt)
                readable_answers.append(template.format(*ad))
            elif "choices" in mo:
                readable_answers.append(mo["choices"][ans[0]])
            else:
                return Status.WRONG_PROBLEM_TYPE, None, None
        return Status.OK, readable_answers


def print_table(s):
    if "|" not in s:
        print(s)
        return
    lines = s.strip().split('\n')
    rows = []
    for line in lines:
        if line.startswith('|`print'):
            parts = [p.strip(' `') for p in line.split('|')[1:-1]]
            rows.append(parts)

    # Находим максимальные ширины колонок
    max_widths = [0, 0]
    for row in rows:
        max_widths[0] = max(max_widths[0], len(row[0]))
        max_widths[1] = max(max_widths[1], len(row[1]))

    # Вывод таблицы
    print('┌' + '─' * (max_widths[0] + 2) + '┬' + '─' * (
            max_widths[1] + 2) + '┐')
    for row in rows:
        print(
            f'│ {row[0].ljust(max_widths[0])} │ {row[1].ljust(max_widths[1])} │')
        if row != rows[-1]:
            print('├' + '─' * (max_widths[0] + 2) + '┼' + '─' * (
                    max_widths[1] + 2) + '┤')
    print('└' + '─' * (max_widths[0] + 2) + '┴' + '─' * (
            max_widths[1] + 2) + '┘')


def print_marker_solution(s: Solver, i: int):
    st, an = s.marker_solution(i)
    if st != Status.OK:
        print(f"Error: {st.name}")
        return
    for aa in an:
        print_table(aa)


def print_coding_solution(s: Solver, i: int):
    st, sol, prid = s.coding_solution(i)
    if st != Status.OK:
        print(f"Error: {st.name}")
        return
    print(sol)
    if input("Remove comments? (y/n) ").lower() == "y":
        sol=remove_comments(sol)
        print(sol)
    if input("Submit auto-solution? (y/n) ").lower() == "y":
        fake_td = int(input("Enter fake time delta (in seconds): "))
        s.submit_coding_solution(sol, prid, fake_td)

def remove_comments(sol):
    is_multiline_comment=False
    is_start=True
    res=[]
    for l in sol.splitlines():
        line=l.strip()
        if len(line)==0:
            continue
        if line.startswith("#"):
            continue
        if  is_multiline_comment:
            if line.startswith("'''"):
                is_multiline_comment=False
            continue
        if "'''" in line and is_start:
            is_multiline_comment=True
            continue
        is_start=False
        res.append(l)
    return  "\n".join(res)
def print_problem(s: Solver, i: int):
    st, t = s.get_problem_type(i)
    print(f"{'-' * 25}Problem {i}{'-' * 25}")
    if st != Status.OK:
        print(f"Error: {st.name}")
        return
    if t == "theory":
        print("Theory problem. No answer required.")
    elif t == "practice":
        print_marker_solution(s, i)
    elif t == "coding":
        print_coding_solution(s, i)
    else:
        print(f"Unknown problem type: {t}")


def print_all_problems(s: Solver):
    for i, problem in enumerate(s.get_problems(), start=1):
        print_problem(s, i)

def load_ids():
    a=input("Enter course id OR link to assignment: ")
    if a.startswith("https://"):
        cid=a[a.find("courses/")+len("courses/"):a.find("/assignments")]
        aid=a[a.find("assignments/")+len("assignments/"):a.find("/run")]
        if not cid.isdigit() or not aid.isdigit():
            return Status.WRONG_INPUT, None, None
        print(f"Your course ID: {cid}, assignment ID: {aid}")
        return Status.OK, cid, aid
    elif a.isdigit():
        aid=input("Enter assignment ID: ")
        if not aid.isdigit():
            return Status.WRONG_INPUT, None, None
        return Status.OK, a, aid
    return Status.WRONG_INPUT, None, None
def main():
    cookies_path = input(
        "Enter cookies path (or blank to use default) OR '*' to login with credentials: ")
    uname=None
    sch_code=None
    cookies_path = cookies_path if cookies_path else "cookies.txt"
    if cookies_path=="*":
        uname=input("Enter your login: ")
        sch_code=input("Enter your school code: ")
        if not sch_code.isdigit() or not sch_code or not uname:
            print("Error: Incorrect credentials format!")
            exit(1)
    st, cid, aid = load_ids()
    if st!=Status.OK:
        print(f"Error: {st.name}")
        exit(1)
    solver = Solver(cid, aid, cookies_path, {"login": uname, "code": sch_code})
    st, name=solver.get_name()
    if st!=Status.OK:
        print(f"Auth error: {st.name}")
        exit(1)
    print(f"Logged in as: {name}")
    problem_idx = input("Enter problem number or * to show all: ").strip()
    if problem_idx == "*":
        print_all_problems(solver)
    elif problem_idx.isdigit():
        print_problem(solver, int(problem_idx))
    else:
        print("Invalid problem number. Please enter integer or *")
if __name__ == "__main__":
    main()