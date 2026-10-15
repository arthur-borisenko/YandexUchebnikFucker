# -*- coding: utf-8 -*-
import html
import json
import os
import re
import uuid
from typing import Optional

from fastapi import Cookie, FastAPI, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
import uvicorn

from main.uchebnik import YandexUchebnik
from main.util import Status

app = FastAPI(title="Yandex Uchebnik Multi-User Web UI")

SESSIONS_DIR = os.path.join(os.getcwd(), "sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)

# Кэш объектов солверов в памяти процесса: {session_id: YandexUchebnik}
SOLVER_CACHE = {}


# --- Работа с состоянием на диске ---

def get_session_file(token: str) -> str:
    # Защита от traversal атаки
    safe_token = re.sub(r"[^a-zA-Z0-9_-]", "", token)
    return os.path.join(SESSIONS_DIR, f"{safe_token}.json")


def load_state(token: str) -> dict:
    default_state = {
        "creds": None,
        "user_name": None,
        "cid": None,
        "aid": None,
        "courses": [],
        "assignments": [],
        "logs": [],
        "error": None,
    }
    path = get_session_file(token)
    if not os.path.exists(path):
        return default_state
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            default_state.update(data)
            return default_state
    except Exception:
        return default_state


def save_state(token: str, state: dict):
    path = get_session_file(token)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def get_solver(token: str, state: dict) -> Optional[YandexUchebnik]:
    if not state.get("creds"):
        return None

    # Достаем из кэша памяти, чтобы не перелогиниваться
    solver = SOLVER_CACHE.get(token)
    if solver is None:
        solver = YandexUchebnik(state.get("cid"), state.get("aid"), state["creds"])
        SOLVER_CACHE[token] = solver
    else:
        # Синхронизируем текущий выбранный курс и задание
        solver.cid = state.get("cid")
        solver.aid = state.get("aid")

    return solver


def add_log(token: str, msg: str):
    st = load_state(token)
    st["logs"].append(msg)
    save_state(token, st)


# --- Рендеринг HTML ---

def render_shell(content: str, token: str) -> HTMLResponse:
    state = load_state(token)
    user_badge = (
        f'<span>👤 <b>{html.escape(state["user_name"])}</b> | <a href="/logout" style="color: #ef4444; text-decoration: none;">Выйти</a></span>'
        if state.get("user_name")
        else "<span>Гость</span>"
    )
    error_box = (
        f'<div class="alert error">{html.escape(state["error"])}</div>'
        if state.get("error")
        else ""
    )

    log_box = ""
    if state.get("logs"):
        joined_logs = html.escape("\n".join(state["logs"]))
        log_box = f"""
        <div style="margin-top: 24px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                <span style="font-weight:600; font-size:14px; color:#94a3b8;">Лог выполнения:</span>
                <a href="/clear-logs" style="font-size:12px; color:#64748b; text-decoration:none;">Очистить лог</a>
            </div>
            <pre>{joined_logs}</pre>
        </div>
        """

    page = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Яндекс Учебник - Web UI</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background: #090d16;
            color: #f1f5f9;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            display: flex;
            justify-content: center;
            padding: 30px 15px;
        }}
        .card {{
            background: #111827;
            border: 1px solid #1f2937;
            width: 100%;
            max-width: 800px;
            border-radius: 12px;
            padding: 28px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.6);
        }}
        .topbar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #1f2937;
            padding-bottom: 14px;
            margin-bottom: 20px;
            font-size: 14px;
            color: #94a3b8;
        }}
        h2 {{ font-size: 20px; margin-bottom: 14px; color: #f8fafc; }}
        .form-row {{ margin-bottom: 16px; }}
        label {{ display: block; font-size: 13px; color: #94a3b8; margin-bottom: 6px; }}
        input, select {{
            width: 100%;
            padding: 10px 14px;
            background: #030712;
            border: 1px solid #374151;
            color: #f8fafc;
            border-radius: 6px;
            font-size: 14px;
            outline: none;
        }}
        input:focus, select:focus {{ border-color: #ef4444; }}
        .btn {{
            width: 100%;
            padding: 11px;
            background: #ef4444;
            color: #fff;
            border: none;
            border-radius: 6px;
            font-weight: 600;
            font-size: 14px;
            cursor: pointer;
            transition: background 0.15s;
        }}
        .btn:hover {{ background: #dc2626; }}
        .btn-ghost {{ background: #1f2937; margin-top: 8px; }}
        .btn-ghost:hover {{ background: #374151; }}
        .alert.error {{
            background: rgba(239, 68, 68, 0.12);
            border: 1px solid #ef4444;
            color: #fca5a5;
            padding: 12px;
            border-radius: 6px;
            margin-bottom: 16px;
            font-size: 14px;
        }}
        .grid-2 {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            margin-top: 15px;
        }}
        pre {{
            background: #030712;
            border: 1px solid #1f2937;
            padding: 14px;
            border-radius: 6px;
            color: #38bdf8;
            font-family: ui-monospace, Menlo, Consolas, monospace;
            font-size: 12px;
            white-space: pre-wrap;
            word-break: break-word;
            max-height: 400px;
            overflow-y: auto;
        }}
        .badge {{
            display: inline-block;
            background: #1f2937;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 12px;
            color: #cbd5e1;
            margin-bottom: 12px;
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="topbar">
            <span style="font-weight:700; color:#fff;">Яндекс.Учебник Авторешатель</span>
            {user_badge}
        </div>
        {error_box}
        {content}
        {log_box}
    </div>
</body>
</html>"""
    if state.get("error"):
        state["error"] = None
        save_state(token, state)
    return HTMLResponse(content=page)


# --------------------------------------------------------------------------
# Роуты
# --------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index(response: Response, session_token: Optional[str] = Cookie(None)):
    if not session_token:
        session_token = str(uuid.uuid4())
        response.set_cookie(key="session_token", value=session_token, httponly=True)

    state = load_state(session_token)
    if not state.get("creds"):
        content = """
        <h2>Вход в аккаунт</h2>
        <form method="post" action="/login">
            <div class="form-row">
                <label>Логин:</label>
                <input type="text" name="login" required autocomplete="off">
            </div>
            <div class="form-row">
                <label>Код школы:</label>
                <input type="text" name="code" required autocomplete="off">
            </div>
            <button class="btn" type="submit">Авторизоваться</button>
        </form>
        """
        resp = render_shell(content, session_token)
        resp.set_cookie(key="session_token", value=session_token, httponly=True)
        return resp

    return RedirectResponse(url="/courses", status_code=303)


@app.post("/login")
async def do_login(
    login: str = Form(...),
    code: str = Form(...),
    session_token: Optional[str] = Cookie(None)
):
    token = session_token or str(uuid.uuid4())
    creds = {"login": login.strip(), "code": code.strip()}
    solver = YandexUchebnik(None, None, creds)
    st, name = solver.get_name()
    state = load_state(token)

    if st != Status.OK:
        state["error"] = f"Ошибка авторизации: {st.name}"
        save_state(token, state)
        resp = RedirectResponse(url="/", status_code=303)
        resp.set_cookie(key="session_token", value=token, httponly=True)
        return resp

    state["creds"] = creds
    state["user_name"] = name
    state["logs"].append(f"Успешный вход под пользователем: {name}")
    save_state(token, state)
    SOLVER_CACHE[token] = solver

    resp = RedirectResponse(url="/courses", status_code=303)
    resp.set_cookie(key="session_token", value=token, httponly=True)
    return resp


@app.get("/logout")
async def logout(session_token: Optional[str] = Cookie(None)):
    if session_token:
        SOLVER_CACHE.pop(session_token, None)
        path = get_session_file(session_token)
        if os.path.exists(path):
            os.remove(path)
    resp = RedirectResponse(url="/", status_code=303)
    resp.delete_cookie("session_token")
    return resp


@app.get("/clear-logs")
async def clear_logs(session_token: Optional[str] = Cookie(None)):
    if session_token:
        state = load_state(session_token)
        state["logs"] = []
        save_state(session_token, state)
        if state.get("aid"):
            return RedirectResponse(url="/dashboard", status_code=303)
    return RedirectResponse(url="/courses", status_code=303)


@app.get("/courses", response_class=HTMLResponse)
async def courses_page(session_token: Optional[str] = Cookie(None)):
    if not session_token:
        return RedirectResponse(url="/", status_code=303)

    state = load_state(session_token)
    solver = get_solver(session_token, state)
    if not solver:
        return RedirectResponse(url="/", status_code=303)

    st, courses, msg = solver.get_courses()
    if st != Status.OK:
        state["error"] = f"Не удалось загрузить курсы: {msg}"
        save_state(session_token, state)
        fallback_content = """
        <h2>Ручной ввод</h2>
        <form method="post" action="/manual-ids">
            <div class="form-row">
                <label>Ссылка на урок или Course ID:</label>
                <input type="text" name="course_input" required>
            </div>
            <div class="form-row">
                <label>Assignment ID (если не ссылка):</label>
                <input type="text" name="assignment_input">
            </div>
            <button class="btn" type="submit">Открыть вручную</button>
        </form>
        """
        return render_shell(fallback_content, session_token)

    state["courses"] = courses
    save_state(session_token, state)

    options = "".join(
        f'<option value="{c["id"]}" {"selected" if str(c["id"]) == str(state.get("cid")) else ""}>{c["name"]} (Новых: {c["cnt"]})</option>'
        for c in courses
    )

    content = f"""
    <h2>Выбор курса</h2>
    <form method="post" action="/select-course">
        <div class="form-row">
            <select name="cid" required>
                {options}
            </select>
        </div>
        <button class="btn" type="submit">Далее к урокам ➜</button>
    </form>
    <div style="margin-top:20px; border-top:1px dashed #374151; padding-top:15px;">
        <details>
            <summary style="font-size:13px; color:#94a3b8; cursor:pointer;">Или ввести ID / ссылку вручную</summary>
            <form method="post" action="/manual-ids" style="margin-top:10px;">
                <div class="form-row">
                    <input type="text" name="course_input" placeholder="https://education.yandex.ru/courses/... или ID" required>
                </div>
                <div class="form-row">
                    <input type="text" name="assignment_input" placeholder="Assignment ID (если в поле выше число)">
                </div>
                <button class="btn btn-ghost" type="submit">Загрузить вручную</button>
            </form>
        </details>
    </div>
    """
    return render_shell(content, session_token)


@app.post("/select-course")
async def select_course(cid: str = Form(...), session_token: Optional[str] = Cookie(None)):
    if not session_token:
        return RedirectResponse(url="/", status_code=303)
    state = load_state(session_token)
    state["cid"] = cid
    save_state(session_token, state)
    return RedirectResponse(url="/assignments", status_code=303)


@app.get("/assignments", response_class=HTMLResponse)
async def assignments_page(session_token: Optional[str] = Cookie(None)):
    if not session_token:
        return RedirectResponse(url="/", status_code=303)

    state = load_state(session_token)
    solver = get_solver(session_token, state)
    cid = state.get("cid")
    if not solver or not cid:
        return RedirectResponse(url="/courses", status_code=303)

    st, assignments, msg = solver.get_lessons(cid)
    if st != Status.OK:
        state["error"] = f"Не удалось получить список уроков: {msg}"
        save_state(session_token, state)
        return RedirectResponse(url="/courses", status_code=303)

    state["assignments"] = assignments
    save_state(session_token, state)

    options = "".join(
        f'<option value="{a["id"]}" {"selected" if str(a["id"]) == str(state.get("aid")) else ""}>{a["name"]} (Задач: {a["problems"]})</option>'
        for a in assignments
    )

    content = f"""
    <div class="badge">Курс ID: {cid}</div>
    <h2>Выбор урока</h2>
    <form method="post" action="/select-assignment">
        <div class="form-row">
            <select name="aid" required>
                {options}
            </select>
        </div>
        <button class="btn" type="submit">Открыть задачи ➜</button>
        <a href="/courses"><button class="btn btn-ghost" type="button">⬅ Сменить курс</button></a>
    </form>
    """
    return render_shell(content, session_token)


@app.post("/select-assignment")
async def select_assignment(aid: str = Form(...), session_token: Optional[str] = Cookie(None)):
    if not session_token:
        return RedirectResponse(url="/", status_code=303)
    state = load_state(session_token)
    state["aid"] = aid
    save_state(session_token, state)
    return RedirectResponse(url="/dashboard", status_code=303)


@app.post("/manual-ids")
async def manual_ids(
    course_input: str = Form(...),
    assignment_input: Optional[str] = Form(None),
    session_token: Optional[str] = Cookie(None)
):
    if not session_token:
        return RedirectResponse(url="/", status_code=303)

    cin = course_input.strip()
    if "education.yandex.ru" in cin:
        c_m = re.search(r"courses/(\d+)", cin)
        a_m = re.search(r"assignments/(\d+)", cin)
        cid = c_m.group(1) if c_m else None
        aid = a_m.group(1) if a_m else None
    else:
        cid = cin
        aid = assignment_input.strip() if assignment_input else None

    state = load_state(session_token)
    if not cid or not aid:
        state["error"] = "Не удалось распознать Course ID и Assignment ID"
        save_state(session_token, state)
        return RedirectResponse(url="/courses", status_code=303)

    state["cid"] = cid
    state["aid"] = aid
    save_state(session_token, state)
    return RedirectResponse(url="/dashboard", status_code=303)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(session_token: Optional[str] = Cookie(None)):
    if not session_token:
        return RedirectResponse(url="/", status_code=303)

    state = load_state(session_token)
    solver = get_solver(session_token, state)
    if not solver or not state.get("cid") or not state.get("aid"):
        return RedirectResponse(url="/courses", status_code=303)

    st, problems = solver.get_problems()
    problems_count = len(problems) if st == Status.OK else 0

    content = f"""
    <div class="badge">Курс: {state["cid"]} | Урок: {state["aid"]}</div>
    <h2>Задачи урока (Всего: {problems_count})</h2>

    <div class="grid-2">
        <form method="post" action="/solve-all">
            <label>Задержка (сек, -1 = рандом):</label>
            <input type="number" name="timedelta" value="-1" style="margin-bottom: 8px;">
            <button class="btn" type="submit">🚀 Решить ВСЕ задачи</button>
        </form>

        <form method="post" action="/solve-one">
            <label>Номер задачи (1..{max(1, problems_count)}):</label>
            <input type="number" name="idx" min="1" max="{max(1, problems_count)}" value="1" style="margin-bottom: 8px;" required>
            <button class="btn" type="submit">🎯 Решить конкретную</button>
        </form>
    </div>

    <div style="margin-top: 15px;">
        <a href="/assignments"><button class="btn btn-ghost" type="button">⬅ Назад к урокам</button></a>
    </div>
    """
    return render_shell(content, session_token)


@app.post("/solve-one")
async def solve_one(idx: int = Form(...), session_token: Optional[str] = Cookie(None)):
    if not session_token:
        return RedirectResponse(url="/", status_code=303)

    state = load_state(session_token)
    solver = get_solver(session_token, state)
    if not solver:
        return RedirectResponse(url="/", status_code=303)

    st, p_type, disp = solver.handle_problem_display_solution(idx)
    add_log(session_token, f"\n{'='*20} Задача #{idx} ({p_type}) {'='*20}")

    if st != Status.OK:
        add_log(session_token, f"Ошибка получения решения: {st.name}")
    elif p_type == "theory":
        add_log(session_token, f"Теория:\n{disp}\nОтмечаем как пройденную...")
        solver.handle_problem_solution(idx)
        add_log(session_token, "Успешно просмотрено!")
    else:
        add_log(session_token, f"Решение:\n{disp}")
        st_res, _, msg = solver.handle_problem_solution(idx, fake_timedelta=-1)
        add_log(session_token, f"Статус отправки: {st_res.name}\nОтвет: {msg}")

    return RedirectResponse(url="/dashboard", status_code=303)


@app.post("/solve-all")
async def solve_all(timedelta: int = Form(-1), session_token: Optional[str] = Cookie(None)):
    if not session_token:
        return RedirectResponse(url="/", status_code=303)

    state = load_state(session_token)
    solver = get_solver(session_token, state)
    if not solver:
        return RedirectResponse(url="/", status_code=303)

    st, problems = solver.get_problems()
    if st != Status.OK:
        add_log(session_token, f"Ошибка получения списка задач: {st.name}")
        return RedirectResponse(url="/dashboard", status_code=303)

    add_log(session_token, f"\n--- Начат пакетный прогон ({len(problems)} задач) ---")
    for i in range(1, len(problems) + 1):
        st_p, p_type, disp = solver.handle_problem_display_solution(i)
        if st_p != Status.OK:
            add_log(session_token, f"Задача #{i}: Ошибка ({st_p.name})")
            continue

        if p_type == "theory":
            solver.handle_problem_solution(i)
            add_log(session_token, f"Задача #{i} (theory): Прочитано и сдано")
        else:
            st_res, _, msg = solver.handle_problem_solution(i, fake_timedelta=timedelta)
            add_log(session_token, f"Задача #{i} ({p_type}): {st_res.name} (Ответ: {msg})")

    add_log(session_token, "--- Пакетная отправка завершена ---")
    return RedirectResponse(url="/dashboard", status_code=303)


def main():
    print(f"Каталог сессий: {SESSIONS_DIR}")
    print("Запуск сервера: http://0.0.0.0:8000")
    # 0.0.0.0 чтобы было доступно по локальной сети для других пользователей
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")


if __name__ == "__main__":
    main()
