import json
import os
import re
import traceback
from enum import Enum
from typing import Optional

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


# ---------------------------------------------------------------------------
# Получение CSRF/session-токена (sk) у Яндекс Учебника
# ---------------------------------------------------------------------------
# Схема входа ученика:
#   1. GET страницы -> в HTML лежит window._data={"config":{...,"sk":"<ключ>"}}
#   2. POST /classroom/api/post-verify-school-code/  {"schoolCode": ..., "sk": ...}
#   3. POST /classroom/api/post-submit-student-login/{"studentLogin": ..., "sk": ...}
#   4. Cookie schoolbook-auth-token = авторизация
#
# ВАЖНО (обход гео-блока): страницы /kids/ и /classroom/ при запросе из-за
# границы отдают заглушку "Яндекс Учебник временно недоступен в вашей стране",
# в которой нет sk. Но блокировка висит НЕ на всех маршрутах: служебная
# страница /not-found/ (и любой 404 внутри SPA) открывается откуда угодно и
# содержит тот же window._data.config.sk, который сервер принимает при входе.
# Поэтому основной путь — сначала обычные страницы входа, затем эти резервные.
# ---------------------------------------------------------------------------

PRIMARY_SK_URLS = (
    "https://education.yandex.ru/kids/",
    "https://education.yandex.ru/uchebnik/",
    "https://education.yandex.ru/classroom/",
)

# Резервные страницы, которые НЕ попадают под гео-блок, но отдают валидный sk
FALLBACK_SK_URLS = (
    "https://education.yandex.ru/not-found/",
    "https://education.yandex.ru/api/sk/",  # 404 -> редирект на /not-found/
)

# Признаки того, что Яндекс закрыл сервис для нашего IP (гео-блокировка / VPN)
GEOBLOCK_MARKERS = (
    "project/education/unavailable",
    "promo/education/unavailable",
    "недоступен в вашей стране",
)

# Имена csrf-cookie, которые может выставить Яндекс
CSRF_COOKIE_NAMES = ("_csrf", "csrf_token", "csrf")


def extract_sk(html: str) -> Optional[str]:
    """Достаёт sk (ключ сессии) из HTML страницы Яндекс Учебника.

    Актуальная разметка: ``window._data={"basePath":...,"config":{...,"sk":"..."}}``.
    Поэтому сначала разбираем JSON, а уже потом ищем ``"sk":"..."`` регуляркой.
    """
    if not html:
        return None

    marker = "window._data="
    idx = html.find(marker)
    if idx != -1:
        blob = html[idx + len(marker) :]
        end = blob.find("</script>")
        if end != -1:
            blob = blob[:end]
        try:
            data = json.loads(blob)
            sk = (data.get("config") or {}).get("sk")
            if sk:
                return str(sk)
        except Exception:
            pass

    # запасной вариант: sk может лежать прямо в разметке
    match = re.search(r'"sk":"(.*?)"', html)
    if match:
        return match.group(1)
    return None


def find_csrf_cookie(session: requests.Session) -> Optional[str]:
    """Ищет csrf-cookie в банке сессии.

    Раньше здесь был ``session.cookies.get("_csrf", domain=".yandex.ru")`` — но
    Яндекс выставляет эту cookie как host-only для ``education.yandex.ru``,
    поэтому поиск по домену ``.yandex.ru`` никогда ничего не находил.
    """
    for name in CSRF_COOKIE_NAMES:
        for cookie in session.cookies:
            if cookie.name == name and cookie.value:
                return cookie.value
    return None


def is_geoblocked(url: str, html: str) -> bool:
    """Яндекс Учебник недоступен из этой страны/с этого IP на этом маршруте."""
    if any(marker in url for marker in GEOBLOCK_MARKERS):
        return True
    return any(marker in (html or "") for marker in GEOBLOCK_MARKERS)


def _apply_proxy(session: requests.Session) -> Optional[str]:
    """Позволяет завернуть трафик в прокси (YUF_PROXY или HTTPS_PROXY).

    Нужен только если захочется ходить с российского IP: с найденным обходом
    гео-блока (см. FALLBACK_SK_URLS) прокси не обязателен.
    """
    proxy = os.environ.get("YUF_PROXY") or os.environ.get("HTTPS_PROXY")
    if proxy:
        session.proxies.update({"http": proxy, "https": proxy})
    return proxy


def _get(
    session: requests.Session, url: str, headers: dict
) -> tuple[Optional[requests.Response], str]:
    try:
        return session.get(url, headers=headers, allow_redirects=True), ""
    except Exception as exc:
        return None, f"{url} -> ОШИБКА ЗАПРОСА: {exc}"


def fetch_sk_from_pages(
    session: requests.Session,
    headers: dict,
    urls: tuple[str, ...],
    note_geoblock: bool = True,
) -> tuple[Optional[str], str, bool]:
    """Перебирает страницы и ищет на них sk.

    Возвращает (sk, диагностика, видели_ли_гео-заглушку).
    """
    diagnostics: list[str] = []
    geoblocked_anywhere = False
    for url in urls:
        resp, err = _get(session, url, headers)
        if resp is None:
            diagnostics.append(err)
            continue
        diagnostics.append(f"{url} -> HTTP {resp.status_code}, итоговый URL: {resp.url}")
        blocked = is_geoblocked(resp.url, resp.text)
        if blocked:
            geoblocked_anywhere = True
            if note_geoblock:
                diagnostics.append(
                    f"{url}: отдана заглушка 'Яндекс Учебник временно недоступен "
                    "в вашей стране' — этот маршрут закрыт по IP."
                )
        sk = extract_sk(resp.text)
        if sk:
            diagnostics.append(f"{url}: найден sk ({'несмотря на заглушку' if blocked else 'ok'}).")
            return sk, "\n".join(diagnostics), geoblocked_anywhere
        diagnostics.append(f"{url}: sk на странице нет.")
    return None, "\n".join(diagnostics), geoblocked_anywhere


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
        proxy = _apply_proxy(session)
        diag: list[str] = []
        if proxy:
            diag.append(f"Прокси: {proxy}")

        # 1) обычные страницы входа
        sk, d1, geo = fetch_sk_from_pages(session, headers, PRIMARY_SK_URLS)
        diag.append(d1)
        sk_source = "страница входа"

        # 2) обход гео-блока: служебные страницы без гео-фильтра
        if not sk:
            diag.append("— страницы входа не отдали sk, пробую служебные страницы —")
            sk, d2, geo2 = fetch_sk_from_pages(
                session, headers, FALLBACK_SK_URLS, note_geoblock=False
            )
            diag.append(d2)
            geo = geo or geo2
            sk_source = "служебная страница (обход гео-блока)"

        # 3) последний шанс — csrf-cookie
        if not sk:
            sk = find_csrf_cookie(session)
            if sk:
                sk_source = "csrf-cookie"
                diag.append("sk взят из csrf-cookie.")

        if not sk:
            diag.append(
                "Не удалось получить CSRF/session-токен (sk): ни страницы входа, "
                "ни служебные страницы, ни cookies его не отдали."
            )
            return Status.COOKIES_GENERATE_ERROR, "\n".join(diag)

        if geo:
            diag.append(
                "ВНИМАНИЕ: страницы входа закрыты по IP (гео-блок), sk получен в "
                "обход через служебную страницу — вход через API всё равно работает."
            )

        api_headers = headers.copy()
        api_headers.update(
            {
                "Content-Type": "application/json",
                "x-csrf-token": sk,
                "X-Requested-With": "XMLHttpRequest",
            }
        )

        diag.append(f"sk получен ({sk_source}).")

        v_res = session.post(
            "https://education.yandex.ru/classroom/api/post-verify-school-code/",
            json={"schoolCode": sch_code, "sk": sk},
            headers=api_headers,
        )
        diag.append(f"post-verify-school-code -> HTTP {v_res.status_code}")
        if v_res.status_code // 100 >= 4:
            return (
                Status.COOKIES_GENERATE_ERROR,
                "\n".join(
                    diag
                    + [
                        f"Код школы не принят (HTTP {v_res.status_code}): "
                        f"{v_res.text[:1000]}"
                    ]
                ),
            )
        try:
            school = v_res.json().get("school_data", {}).get("name")
            if school:
                diag.append(f"Школа: {school}")
        except Exception:
            pass

        l_res = session.post(
            "https://education.yandex.ru/classroom/api/post-submit-student-login/",
            json={"studentLogin": username, "sk": sk},
            headers=api_headers,
        )
        diag.append(f"post-submit-student-login -> HTTP {l_res.status_code}")
        if l_res.status_code // 100 >= 4:
            return (
                Status.COOKIES_GENERATE_ERROR,
                "\n".join(
                    diag
                    + [
                        f"Логин не принят (HTTP {l_res.status_code}): {l_res.text[:1000]}"
                    ]
                ),
            )

        if "schoolbook-auth-token" in session.cookies:
            return Status.OK, "\n".join(diag + ["Вход выполнен."])
        else:
            diag.append(
                "Cookie 'schoolbook-auth-token' не получен после входа. Cookies: "
                f"{sorted(c.name for c in session.cookies)}"
            )
            return Status.COOKIES_GENERATE_ERROR, "\n".join(diag)
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
