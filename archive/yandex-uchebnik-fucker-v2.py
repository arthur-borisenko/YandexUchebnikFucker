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
v=1
def load_cookies():
    if os.path.exists("cookies.txt"):
        jar = MozillaCookieJar("cookies.txt")
        jar.load()
    else:
        path=input("Enter path to cookies.txt: ")
        if not os.path.exists(path):
            print("File not found.")
            exit(1)
        jar = MozillaCookieJar(path)
    return jar
aid=input("Enter assignment ID: ")
has_cookies=False
if os.path.exists(f"data_{aid}.json"):
    v=input("Cached data. override(y/n): ").lower() == "y"
if v:
    cookies=load_cookies()
    has_cookies=True
    error=0
    URL=f"https://education.yandex.ru/classroom/courses/14848489/assignments/{aid}/run/5/"
    request=requests.get(URL, cookies=cookies)
    html=request.text
    if "captcha" in html:
        sys.stderr.write("Captcha detected, could not proceed. Please check cookies and wait.")
        exit(1)
    print(html, file=open("zzz.html", "w", encoding="utf-8"))
    datatxt=html[html.find("window._data="):][len("window._data="):]
    datatxt=datatxt[:datatxt.find("</script>")]
    print(datatxt, file=open(f"data_{aid}.json", "w", encoding="utf-8"))
else:
    datatxt=open(f"data_{aid}.json", "r", encoding="utf-8").read()
data=json.loads(datatxt)
problems=data["data"]["getCLessonRun"]["problems"]
problem_idx=input("Enter problem number or * to show all: ")
if problem_idx=="*":
    for i, problem1 in enumerate(problems, start=1):
        problem=problem1["problem"]
        print(f"{'-'*25}Problem {i}{'-'*25}")
        if problem["type"] != "coding":
            print(f"Not a coding problem.")
            continue
        print(problem["markup"]["languages"][0]["author_solution"])
    exit(0)
problem_idx=int(problem_idx)
problem=problems[problem_idx-1]["problem"]
if problem["type"]!="coding":
    sys.stderr.write("This is not a coding problem.")
    exit(1)
print(problem["markup"]["languages"][0]["author_solution"])
print("loading auto-solver...")
print(problems[problem_idx-1]["id"])
def post_solution(lpl_id, solution, window_data, c):
    data={
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
        "clr_id": window_data["data"]["getLatestCLessonResult"]["id"],
        "lpl_id": lpl_id,
        "sk": window_data["config"]["sk"]
    }
    print("Forged request:")
    print(data)
    print("Sending...")
    resp = requests.post("https://education.yandex.ru/classroom/api/v2/post-attempts/", json=data, cookies=c)
    print("Response status:", resp.status_code)
    print(resp.json())
if input("Submit auto-solution? (y/n) ").lower()=="y":
    if not has_cookies:
        cookies=load_cookies()
    s=problem["markup"]["languages"][0]["author_solution"]
    post_solution(problems[problem_idx-1]["id"], s, data, cookies)
