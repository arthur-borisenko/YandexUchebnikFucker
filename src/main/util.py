import re
import traceback
from enum import Enum
import requests


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
    SOLUTION_FAILURE_WRONG_ANSWER = 9
    SOLUTION_FAILURE_UNKNOWN_PROBLEM_TYPE = 10
    SOLUTION_FAILURE_ALREADY_SOLVED_OR_NO_ATTEMPTS = 11
    NOT_INITIALIZED = 12
    UNKNOWN_ERROR = 13


def login_with_creds(
    username, sch_code, session: requests.Session
) -> tuple[Status, str]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9",
        "Origin": "https://education.yandex.ru",
        "Referer": "https://education.yandex.ru/kids/",
    }

    try:
        response = session.get("https://education.yandex.ru/kids/", headers=headers)
        response.raise_for_status()
        sk_match = re.search(r'"sk":"(.*?)"', response.text)
        if not sk_match:
            sk = session.cookies.get("_csrf", domain=".yandex.ru")
        else:
            sk = sk_match.group(1)

        if not sk:
            return Status.COOKIES_GENERATE_ERROR, "CSRF token not found"

        api_headers = headers.copy()
        api_headers.update(
            {
                "Content-Type": "application/json",
                "x-csrf-token": sk,
                "X-Requested-With": "XMLHttpRequest",
            }
        )

        v_res = session.post(
            "https://education.yandex.ru/classroom/api/post-verify-school-code/",
            json={"schoolCode": sch_code, "sk": sk},
            headers=api_headers,
        )
        if v_res.status_code // 100 >= 4:
            return Status.COOKIES_GENERATE_ERROR, v_res.text

        l_res = session.post(
            "https://education.yandex.ru/classroom/api/post-submit-student-login/",
            json={"studentLogin": username, "sk": sk},
            headers=api_headers,
        )
        if l_res.status_code // 100 >= 4:
            return Status.COOKIES_GENERATE_ERROR, l_res.text

        if "schoolbook-auth-token" in session.cookies:
            return Status.OK, "OK"
        else:
            return Status.COOKIES_GENERATE_ERROR, "Cookie not found"
    except Exception as e:
        traceback.print_exc()
        return Status.UNKNOWN_ERROR, traceback.format_exc()


def install_requests():
    try:
        import requests
    except ImportError:
        print("Trying to install requests module.")
        import pip

        pip.main(["install", "requests"])
