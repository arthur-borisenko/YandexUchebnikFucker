import sys, os
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
aid=input("Enter assignment ID: ")
if os.path.exists(f"data_{aid}.json"):
    v=input("Cached data. override(y/n): ").lower() == "y"
if v:
    cookies=parse_cookie_string("spravka=dD0xNzY5NDQwNzk5O2k9MjYwNjo2MDgwOjIwMDE6MjAwMjplOGJlOmM3Y2Q6MjZhZjo3OTE4O0Q9NjQyQUYwOENERjM0MjcwNTExQUExQ0ZFQTA4OTA0Q0FCQzBFOTNDNDJEQjVGODNBRjAzQjgwQzFCM0E2RTE5MDdFNTVGOTBDRDMwMUJFRUNGNEM3ODVFMDA0MEUwQjJEQUU5RkY1ODE3MEFDODI3NkYyMDI0MEY1REQwMzEwRDRFQUFGNUY0RjlDRTVDQkU4NEM0MEMzRUI1QTQ4M0NFOEJCODg4NzQ4M0M7dT0xNzY5NDQwNzk5NzAyNDMwODk3O2g9YmU0ZDYyZWMwOGI1MjQxZjEzMTU5MjA2MDg4NmJmMmY=; _yasc=39VaYXk5OHXDnoLwSIRx8IYAoo8A1Ht0jHJndfoxisyOvTVp79E1fRvbYSxdl2fLKwAE6kUy3k7fZg==;")
    cookies2=parse_cookie_string('i=bO3KjyjW/PGfQSxyMgxS2UPXgVLsHFt138gKsLNd5GRez+O7fM3zqcSkqocMSFwiU7/TMI0s/n0p6n64ezdn3G7++dI=; yandexuid=7838800981769440794; yashr=5815782201769440794; bh=YJ6M3ssGahfcyuH/CJLYobEDn8/14Qyx3POOA7rQAQ==; _csrf=K_rEkZmEZTXPEKXLAAD0Mlry; gdpr=0; _ym_uid=1769440799996007075; _ym_d=1769440801; _ym_visorc=b; _ym_isad=1; yp=1770045603.szm.1:2560x1440:2509x1307; yuidss=7838800981769440794; ymex=2084800806.yrts.1769440806; schoolbook-auth-token="NDAwNDgyX1/QpNCY0JTQldChNzAz:1vkOOM:IMTKKBn68SKbuI46ZqyjOCupRcW2hAQOyiZRpMkUmMY"')
    cookies.update(cookies2)
    error=0
    for key, value in cookies.items():
        for i,char in enumerate(value):
            try:
                char.encode('latin-1')
            except UnicodeEncodeError:
                print(f"Проблемный символ {i} в {key}: {repr(char)} (код: {ord(char)})")
                error=1
    if error:
        exit(1)
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