import sys, os
from http.cookiejar import MozillaCookieJar

try:
    import requests
except ImportError:
    print("Trying to install requests module.")
    import pip

    pip.main(['install', 'requests'])
    import requests
import json


def parse_cookie_string(cookie_str):
    """Parse cookie string into dictionary"""
    cookies = {}
    items = cookie_str.split('; ')

    for item in items:
        if '=' in item:
            key, value = item.split('=', 1)
            # Remove quotes if present
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            cookies[key] = value

    return cookies


v = 1


def load_cookies():
    path = input("Enter path to cookies.txt or blank to default: ")
    path = path if path else "cookies.txt"
    if not os.path.exists(path):
        print("File not found.")
        exit(1)
    jar = MozillaCookieJar(path)
    jar.load()
    print(f"Loaded cookies: {requests.utils.dict_from_cookiejar(jar)} from {path}.")
    return jar

cid=input("Enter course ID or blank to default: ")
cid = cid if cid else "14848489"
aid = input("Enter assignment ID: ")
has_cookies = False
if os.path.exists(f"data_{aid}.json"):
    v = input("Cached data. override(y/n): ").lower() == "y"
if v:
    cookies = load_cookies()
    has_cookies = True
    error = 0
    URL = f"https://education.yandex.ru/classroom/courses/{cid}/assignments/{aid}/run/1/"
    request = requests.get(URL, cookies=cookies)
    html = request.text
    if "captcha" in html:
        sys.stderr.write(
            "Captcha detected, could not proceed. Please check cookies and wait.")
        exit(1)
    print(html, file=open("zzz.html", "w", encoding="utf-8"))
    datatxt = html[html.find("window._data="):][
        len("window._data="):]
    datatxt = datatxt[:datatxt.find("</script>")]
    print(datatxt,
          file=open(f"data_{aid}.json", "w", encoding="utf-8"))
else:
    datatxt = open(f"data_{aid}.json", "r", encoding="utf-8").read()
data = json.loads(datatxt)
problems = data["data"]["getCLessonRun"]["problems"]
problem_idx = input("Enter problem number or * to show all: ")
if problem_idx == "*":
    for i, problem1 in enumerate(problems, start=1):
        problem = problem1["problem"]
        print(f"{'-' * 25}Problem {i}{'-' * 25}")
        if problem["type"] != "coding":
            print(f"Not a coding problem.")
            continue
        print(problem["markup"]["languages"][0]["author_solution"])
    exit(0)
problem_idx = int(problem_idx)
problem = problems[problem_idx - 1]["problem"]
if problem["type"] != "coding":
    sys.stderr.write("This is not a coding problem.")
    exit(1)
print(problem["markup"]["languages"][0]["author_solution"])
print("loading auto-solver...")
print(problems[problem_idx - 1]["id"])


def send_solution(lpl_id, solution, window_data, c):
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
        "clr_id": window_data["data"]["getLatestCLessonResult"][
            "id"],
        "lpl_id": lpl_id,
        "sk": window_data["config"]["sk"]
    }
    print("Forged request:")
    print(data)
    print("Sending...")
    resp = requests.post(
        "https://education.yandex.ru/classroom/api/v2/post-attempts/",
        json=data, cookies=c)
    print("Response status:", resp.status_code)
    print(resp.json())


def pre_send_solution(lpl_id, window_data, c):
    fake_timedelta = int(
        input("Enter fake solution time(in seconds): "))
    clr_id=window_data["data"]["getLatestCLessonResult"][
            "id"]
    spent_time_ep = f"https://education.yandex.ru/classroom/api/post-clesson-results-update-spent-time/{clr_id}/"
    spent_time_json = {"link_id": lpl_id,
                       "time_delta": fake_timedelta,
                       "id": "57f5cd7f-58ae-426a-994c-5b8bd613377e",
                       "sk": window_data["config"]["sk"]}
    resp = requests.post(spent_time_ep, json=spent_time_json,
                         cookies=c)
    print(resp.status_code, resp.text)


if input("Submit auto-solution? (y/n) ").lower() == "y":
    if not has_cookies:
        cookies = load_cookies()
    s = problem["markup"]["languages"][0]["author_solution"]
    pre_send_solution(problems[problem_idx - 1]["id"], data, cookies)
    send_solution(problems[problem_idx - 1]["id"], s, data, cookies)
