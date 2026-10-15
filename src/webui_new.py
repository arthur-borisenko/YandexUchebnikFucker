# -*- coding: utf-8 -*-
INDEX_HTML = "<!DOCTYPE html><html lang=\"ru\"><head><meta charset=\"UTF-8\"><title>Yandex Uchebnik - REST SPA</title><style>body{background-color:#008080;font-family:'MS Sans Serif',Tahoma,'Segoe UI',sans-serif;font-size:11px;margin:10px;color:#000}.window{background:#c0c0c0;border:none;box-shadow:none;max-width:950px;margin:0 auto}.title-bar{background:linear-gradient(90deg,#000080,#1084d0);padding:3px 6px;display:flex;justify-content:space-between;align-items:center;color:white;font-weight:bold}.window-body{padding:10px}fieldset{border:2px groove #dfdfdf;padding:8px 10px;margin-bottom:8px}legend{padding:0 4px;font-weight:bold}.btn{background:#c0c0c0;border:2px solid;border-color:#dfdfdf #404040 #404040 #dfdfdf;padding:3px 10px;font-family:inherit;font-size:11px;cursor:pointer;box-shadow:1px 1px 0 #000}.btn:active{border-color:#404040 #dfdfdf #dfdfdf #404040;padding:4px 9px 2px 11px;box-shadow:none}.btn:disabled{color:#808080;cursor:not-allowed;border-color:#dfdfdf #808080 #808080 #dfdfdf}input[type=\"text\"],input[type=\"number\"],select{background:#fff;border:2px inset #808080;padding:3px 5px;font-family:inherit;font-size:11px}.task-bar{display:flex;flex-wrap:wrap;gap:4px;padding:6px;background:#e0e0e0;border:2px inset #808080;margin-bottom:8px;min-height:26px}.task-btn{min-width:28px;height:24px;font-weight:bold;font-size:11px;color:#fff;border:2px solid;border-color:#dfdfdf #404040 #404040 #dfdfdf;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;user-select:none}.task-btn.active{outline:1px dotted #000;border-color:#000 #fff #fff #000}.legend-bar{display:flex;gap:12px;font-size:10px;margin-bottom:6px;align-items:center}.legend-item{display:flex;align-items:center;gap:4px}.legend-color{width:10px;height:10px;border:1px solid #000}.content-box{background:#fff;border:2px inset #808080;padding:8px;font-family:'Courier New',monospace;font-size:12px;white-space:pre-wrap;height:200px;overflow-y:auto}.log-box{background:#000;color:#00ff00;border:2px inset #808080;padding:6px;font-family:'Courier New',monospace;font-size:11px;white-space:pre-wrap;height:200px;overflow-y:auto}.status-bar{border-top:1px solid #808080;margin-top:6px;padding-top:4px;display:flex;gap:8px}.status-panel{border:1px inset #808080;padding:2px 6px;font-size:10px}.hidden{display:none !important}</style></head><body><div class=\"window\"><div class=\"title-bar\"><div id=\"titleText\">💾 Yandex.Uchebnik Solver 95 [REST SPA]</div><div><button class=\"btn\" onclick=\"logout()\" style=\"padding:0 3px;height:14px;line-height:10px;\">✕</button></div></div><div class=\"window-body\"><div id=\"view-login\" class=\"hidden\"><fieldset><legend>Идентификация пользователя</legend><div style=\"margin-bottom:8px;\"><label style=\"display:inline-block;width:100px;\">Логин ученика:</label><input type=\"text\" id=\"loginInput\" style=\"width:250px;\"></div><div style=\"margin-bottom:8px;\"><label style=\"display:inline-block;width:100px;\">Код школы:</label><input type=\"text\" id=\"codeInput\" style=\"width:250px;\"></div><button class=\"btn\" onclick=\"doLogin()\">Войти через REST</button></fieldset></div><div id=\"view-courses\" class=\"hidden\"><fieldset><legend>Выбор активного курса</legend><select id=\"coursesSelect\" size=\"6\" style=\"width:100%;margin-bottom:8px;\"></select><br><button class=\"btn\" onclick=\"selectCourse()\">Открыть уроки курса >></button></fieldset></div><div id=\"view-assignments\" class=\"hidden\"><fieldset><legend>Выбор урока / задания</legend><select id=\"assignmentsSelect\" size=\"8\" style=\"width:100%;margin-bottom:8px;\"></select><br><button class=\"btn\" onclick=\"selectAssignment()\">Загрузить инспектор заданий >></button><button class=\"btn\" onclick=\"showCourses()\">Назад к курсам</button></fieldset></div><div id=\"view-dashboard\" class=\"hidden\"><div class=\"legend-bar\"><span style=\"font-weight:bold;\">Статусы:</span><div class=\"legend-item\"><div class=\"legend-color\" style=\"background:#808080;\"></div> Серый (Не запускалась)</div><div class=\"legend-item\"><div class=\"legend-color\" style=\"background:#008000;\"></div> Зеленый (OK)</div><div class=\"legend-item\"><div class=\"legend-color\" style=\"background:#cc0000;\"></div> Красный (Fail)</div><div class=\"legend-item\"><div class=\"legend-color\" style=\"background:#d97706;\"></div> Оранжевый (Не подд.)</div><div class=\"legend-item\"><div class=\"legend-color\" style=\"background:#0055d4;\"></div> Синий (Пропущено)</div></div><div class=\"task-bar\" id=\"taskBar\"></div><div style=\"display:grid;grid-template-columns:1fr 340px;gap:10px;\"><fieldset><legend id=\"taskTitle\">Инспектор задачи</legend><div style=\"margin-bottom:4px;font-weight:bold;\">Условие и готовое решение:</div><div class=\"content-box\" id=\"taskContent\">Загрузка данных...</div><div style=\"margin-top:8px;display:flex;gap:6px;align-items:center;\"><label>Fake TimeDelta:</label><input type=\"number\" id=\"singleTime\" value=\"15\" style=\"width:50px;\"> сек.<button class=\"btn\" id=\"btnSingle\" onclick=\"sendSingle()\">Отправить задачу</button></div></fieldset><fieldset><legend>Пакетное авторешение (Поштучные запросы)</legend><div style=\"margin-bottom:6px;font-weight:bold;\">Диапазон номеров:</div><div style=\"margin-bottom:8px;\">с <input type=\"number\" id=\"taskFrom\" value=\"1\" style=\"width:45px;\"> по <input type=\"number\" id=\"taskTo\" value=\"999\" style=\"width:45px;\"></div><div style=\"margin-bottom:6px;font-weight:bold;\">Фильтр типов:</div><div style=\"display:grid;grid-template-columns:1fr 1fr;gap:4px;margin-bottom:8px;\"><label><input type=\"checkbox\" id=\"chk-coding\" checked> Coding</label><label><input type=\"checkbox\" id=\"chk-practice\" checked> Marker/Pract</label><label><input type=\"checkbox\" id=\"chk-theory\" checked> Theory</label><label><input type=\"checkbox\" id=\"chk-web\" checked> Web</label><label><input type=\"checkbox\" id=\"chk-misc\" checked> Misc</label></div><div style=\"margin-bottom:8px;\"><label>Задержка (сек):</label><br>от <input type=\"number\" id=\"timeMin\" value=\"10\" style=\"width:45px;\"> до <input type=\"number\" id=\"timeMax\" value=\"30\" style=\"width:45px;\"></div><div style=\"display:flex;gap:6px;\"><button class=\"btn\" id=\"btnBatch\" style=\"flex:1;font-weight:bold;height:28px;\" onclick=\"runBatchIndividual()\">▶ Старт авторешения</button><button class=\"btn\" id=\"btnStop\" style=\"display:none;height:28px;background:#cc0000;color:#fff;\" onclick=\"stopBatch()\">■ Стоп</button></div><button class=\"btn\" style=\"width:100%;margin-top:6px;\" onclick=\"showAssignments()\">⬅ Сменить урок</button></fieldset></div></div><fieldset style=\"margin-top:8px;\"><legend>Системный терминал (Полный лог решений и ответов сервера)</legend><div class=\"log-box\" id=\"logBox\"></div><button class=\"btn\" style=\"margin-top:4px;\" onclick=\"clearLogs()\">Очистить лог</button></fieldset><div class=\"status-bar\"><div class=\"status-panel\" id=\"statCourse\">Курс: -</div><div class=\"status-panel\" id=\"statLesson\">Урок: -</div><div class=\"status-panel\" id=\"statCount\">Задач: 0</div><div class=\"status-panel\" style=\"flex:1;\" id=\"statUser\">Не авторизован</div></div></div></div><script>const COLOR_MAP={idle:\"#808080\",ok:\"#008000\",fail:\"#cc0000\",unsupported:\"#d97706\",skipped:\"#0055d4\"};let AppState={currentIdx:1,problemsCount:0,problemStatuses:{}};let isBatchRunning=false;function appendLog(msg){const box=document.getElementById(\"logBox\");box.innerText+=msg+\"\\n\";box.scrollTop=box.scrollHeight;}function setLogs(logs){const box=document.getElementById(\"logBox\");box.innerText=logs.join(\"\\n\\n\");box.scrollTop=box.scrollHeight;}function showView(viewId){\"view-login view-courses view-assignments view-dashboard\".split(\" \").forEach(id=>{document.getElementById(id).classList.add(\"hidden\");});document.getElementById(viewId).classList.remove(\"hidden\");}async function req(url,method=\"GET\",data=null){const opts={method,headers:{}};if(data){opts.headers[\"Content-Type\"]=\"application/json\";opts.body=JSON.stringify(data);}const resp=await fetch(url,opts);if(!resp.ok){const err=await resp.json().catch(()=>({detail:\"Ошибка сети\"}));throw new Error(err.detail||\"Ошибка сервера\");}return await resp.json();}async function init(){try{const state=await req(\"/api/state\");if(!state.authenticated){showView(\"view-login\");return;}document.getElementById(\"statUser\").innerText=\"👤 \"+state.user_name;setLogs(state.logs);if(state.aid){AppState.currentIdx=state.current_idx||1;AppState.problemsCount=state.problems_count;AppState.problemStatuses=state.problem_statuses;updateStatusBar(state.cid,state.aid,state.problems_count);document.getElementById(\"taskFrom\").value=1;document.getElementById(\"taskTo\").value=state.problems_count;renderTaskBar();loadProblem(AppState.currentIdx);showView(\"view-dashboard\");}else if(state.cid){showAssignments();}else{showCourses();}}catch(e){appendLog(\"[ОШИБКА ИНИЦИАЛИЗАЦИИ]: \"+e.message);showView(\"view-login\");}}async function doLogin(){const login=document.getElementById(\"loginInput\").value.trim();const code=document.getElementById(\"codeInput\").value.trim();if(!login||!code)return alert(\"Заполните логин и код!\");try{const res=await req(\"/api/login\",\"POST\",{login,code});document.getElementById(\"statUser\").innerText=\"👤 \"+res.user_name;appendLog(\"> Вход выполнен успешно\");showCourses();}catch(e){alert(e.message);appendLog(\"[FAIL] Авторизация не удалась: \"+e.message);}}async function logout(){await req(\"/api/logout\",\"POST\");location.reload();}async function showCourses(){try{const res=await req(\"/api/courses\");const select=document.getElementById(\"coursesSelect\");select.innerHTML=res.courses.map(c=>`<option value=\"${c.id}\">${c.name} (Заданий: ${c.cnt})</option>`).join(\"\");showView(\"view-courses\");}catch(e){appendLog(\"[ОШИБКА КУРСОВ]: \"+e.message);}}async function selectCourse(){const cid=document.getElementById(\"coursesSelect\").value;if(!cid)return alert(\"Выберите курс!\");try{const res=await req(\"/api/select-course\",\"POST\",{cid});document.getElementById(\"statCourse\").innerText=\"Курс: \"+cid;renderAssignmentsList(res.assignments);showView(\"view-assignments\");}catch(e){alert(e.message);}}function renderAssignmentsList(assignments){const select=document.getElementById(\"assignmentsSelect\");select.innerHTML=assignments.map(a=>`<option value=\"${a.id}\">${a.name} (Задач: ${a.problems})</option>`).join(\"\");}async function showAssignments(){const cid=document.getElementById(\"statCourse\").innerText.replace(\"Курс: \",\"\");if(!cid||cid===\"-\")return showCourses();const res=await req(\"/api/select-course\",\"POST\",{cid});renderAssignmentsList(res.assignments);showView(\"view-assignments\");}async function selectAssignment(){const aid=document.getElementById(\"assignmentsSelect\").value;if(!aid)return alert(\"Выберите урок!\");try{const res=await req(\"/api/select-assignment\",\"POST\",{aid});AppState.problemsCount=res.problems_count;AppState.problemStatuses=res.problem_statuses;AppState.currentIdx=1;document.getElementById(\"statLesson\").innerText=\"Урок: \"+aid;document.getElementById(\"statCount\").innerText=\"Задач: \"+res.problems_count;document.getElementById(\"taskFrom\").value=1;document.getElementById(\"taskTo\").value=res.problems_count;renderTaskBar();loadProblem(1);showView(\"view-dashboard\");}catch(e){alert(e.message);}}function updateStatusBar(cid,aid,count){document.getElementById(\"statCourse\").innerText=\"Курс: \"+(cid||\"-\");document.getElementById(\"statLesson\").innerText=\"Урок: \"+(aid||\"-\");document.getElementById(\"statCount\").innerText=\"Задач: \"+count;}function renderTaskBar(){const bar=document.getElementById(\"taskBar\");bar.innerHTML=\"\";for(let i=1;i<=AppState.problemsCount;i++){const btn=document.createElement(\"div\");btn.className=\"task-btn\"+(i===AppState.currentIdx?\" active\":\"\");const st=AppState.problemStatuses[String(i)]||\"idle\";btn.style.backgroundColor=COLOR_MAP[st]||\"#808080\";btn.innerText=i;btn.onclick=()=>{if(isBatchRunning)return;AppState.currentIdx=i;renderTaskBar();loadProblem(i);};bar.appendChild(btn);}}async function loadProblem(idx){document.getElementById(\"taskTitle\").innerText=`Инспектор задачи #${idx} [Загрузка...]`;document.getElementById(\"taskContent\").innerText=\"Получение условия и решения с сервера...\";try{const res=await req(`/api/problem/${idx}`);document.getElementById(\"taskTitle\").innerText=`Инспектор задачи #${res.idx} [Тип: ${res.type}]`;document.getElementById(\"taskContent\").innerText=res.content;return res;}catch(e){document.getElementById(\"taskContent\").innerText=\"Ошибка: \"+e.message;return null;}}async function sendSingle(){const sec=parseInt(document.getElementById(\"singleTime\").value)||15;const btn=document.getElementById(\"btnSingle\");btn.disabled=true;try{const res=await req(\"/api/solve-one\",\"POST\",{idx:AppState.currentIdx,fake_timedelta:sec});AppState.problemStatuses[String(AppState.currentIdx)]=res.status;renderTaskBar();appendLog(res.log);}catch(e){alert(e.message);}finally{btn.disabled=false;}}async function runBatchIndividual(){if(isBatchRunning)return;const types=[];if(document.getElementById(\"chk-coding\").checked)types.push(\"coding\");if(document.getElementById(\"chk-practice\").checked)types.push(\"practice\");if(document.getElementById(\"chk-theory\").checked)types.push(\"theory\");if(document.getElementById(\"chk-web\").checked)types.push(\"web\");if(document.getElementById(\"chk-misc\").checked)types.push(\"misc\");const tMin=parseInt(document.getElementById(\"timeMin\").value)||10;const tMax=parseInt(document.getElementById(\"timeMax\").value)||30;const tFrom=Math.max(1,parseInt(document.getElementById(\"taskFrom\").value)||1);const tTo=Math.min(AppState.problemsCount,parseInt(document.getElementById(\"taskTo\").value)||AppState.problemsCount);isBatchRunning=true;document.getElementById(\"btnBatch\").style.display=\"none\";document.getElementById(\"btnStop\").style.display=\"block\";document.getElementById(\"btnSingle\").disabled=true;appendLog(`>>> СТАРТ ПОШТУЧНОГО АВТОРЕШЕНИЯ [Диапазон: #${tFrom}..#${tTo}, Типы: ${types.join(\", \")}]`);for(let i=1;i<=AppState.problemsCount;i++){if(!isBatchRunning){appendLog(\">>> АВТОРЕШЕНИЕ ПРИНУДИТЕЛЬНО ОСТАНОВЛЕНО ПОЛЬЗОВАТЕЛЕМ\");break;}if(i<tFrom||i>tTo){AppState.problemStatuses[String(i)]=\"skipped\";renderTaskBar();await req(\"/api/update-status\",\"POST\",{idx:i,status:\"skipped\"});continue;}const prob=await loadProblem(i);if(!prob){AppState.problemStatuses[String(i)]=\"fail\";renderTaskBar();continue;}let typeMatch=false;if(types.includes(prob.type)){typeMatch=true;}else if(![\"coding\",\"practice\",\"theory\",\"web\"].includes(prob.type)&&types.includes(\"misc\")){typeMatch=true;}if(!typeMatch){AppState.problemStatuses[String(i)]=\"skipped\";renderTaskBar();const skipMsg=`Задача #${i} [${prob.type}]: Пропущена фильтром типов`;appendLog(skipMsg);await req(\"/api/append-log\",\"POST\",{log:skipMsg});await req(\"/api/update-status\",\"POST\",{idx:i,status:\"skipped\"});continue;}const randDelay=Math.floor(Math.random()*(Math.max(tMin,tMax)-Math.min(tMin,tMax)+1))+Math.min(tMin,tMax);try{const res=await req(\"/api/solve-one\",\"POST\",{idx:i,fake_timedelta:randDelay});AppState.problemStatuses[String(i)]=res.status;renderTaskBar();appendLog(res.log);}catch(err){AppState.problemStatuses[String(i)]=\"fail\";renderTaskBar();const errMsg=`[FAIL] Ошибка отправки #${i}: ${err.message}`;appendLog(errMsg);await req(\"/api/append-log\",\"POST\",{log:errMsg});await req(\"/api/update-status\",\"POST\",{idx:i,status:\"fail\"});}}isBatchRunning=false;document.getElementById(\"btnBatch\").style.display=\"block\";document.getElementById(\"btnStop\").style.display=\"none\";document.getElementById(\"btnSingle\").disabled=false;appendLog(\">>> ОЧЕРЕДЬ ОТПРАВКИ ЗАВЕРШЕНА\");}function stopBatch(){isBatchRunning=false;}async function clearLogs(){await req(\"/api/clear-logs\",\"POST\");document.getElementById(\"logBox\").innerText=\"\";}window.onload=init;</script></body></html>"

import json
import os
import re
import uuid
from typing import Optional

from fastapi import Cookie, FastAPI, HTTPException, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

from main.uchebnik import YandexUchebnik
from main.util import Status

app = FastAPI(title="Yandex Uchebnik Solver")

SESSIONS_DIR = os.path.join(os.getcwd(), "sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)
SOLVER_CACHE = {}


def get_session_file(token: str) -> str:
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
        "problems": [],
        "problem_statuses": {},
        "current_idx": 1,
        "logs": [],
    }
    path = get_session_file(token)
    if not os.path.exists(path):
        return default_state
    try:
        with open(path, "r", encoding="utf-8") as f:
            default_state.update(json.load(f))
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
    solver = SOLVER_CACHE.get(token)
    if solver is None:
        solver = YandexUchebnik(state.get("cid"), state.get("aid"), state["creds"])
        SOLVER_CACHE[token] = solver
    else:
        solver.cid = state.get("cid")
        solver.aid = state.get("aid")
    return solver


def format_marker_display(raw_text: str) -> str:
    parts = raw_text.split("\t\n\r")
    task_desc = parts[0].strip()
    answers = parts[1:]
    res = [f"[Условие задачи]\n{task_desc}"]
    if answers:
        res.append("\n[Подготовленные ответы]")
        for i, ans in enumerate(answers, 1):
            res.append(f"Ответ #{i}:\n{ans}")
    return "\n".join(res)


class LoginPayload(BaseModel):
    login: str
    code: str

class CoursePayload(BaseModel):
    cid: str

class AssignmentPayload(BaseModel):
    aid: str

class SolveOnePayload(BaseModel):
    idx: int
    fake_timedelta: int = 15

class LogAppendPayload(BaseModel):
    log: str


@app.get("/", response_class=HTMLResponse)
async def serve_static_spa():
    return HTMLResponse(content=INDEX_HTML)


@app.get("/api/state")
async def api_get_state(session_token: Optional[str] = Cookie(None)):
    if not session_token:
        return {"authenticated": False}
    state = load_state(session_token)
    return {
        "authenticated": bool(state.get("creds")),
        "user_name": state.get("user_name"),
        "cid": state.get("cid"),
        "aid": state.get("aid"),
        "courses": state.get("courses", []),
        "assignments": state.get("assignments", []),
        "problems_count": len(state.get("problems", [])),
        "problem_statuses": state.get("problem_statuses", {}),
        "current_idx": state.get("current_idx", 1),
        "logs": state.get("logs", []),
    }


@app.post("/api/login")
async def api_login(payload: LoginPayload, response: Response, session_token: Optional[str] = Cookie(None)):
    token = session_token or str(uuid.uuid4())
    response.set_cookie(key="session_token", value=token, httponly=True)

    creds = {"login": payload.login.strip(), "code": payload.code.strip()}
    solver = YandexUchebnik(None, None, creds)
    st, name = solver.get_name()
    if st != Status.OK:
        raise HTTPException(status_code=401, detail=f"Ошибка авторизации: {st.name}")

    state = load_state(token)
    state["creds"] = creds
    state["user_name"] = name
    state["logs"].append(f"> Авторизован: {name}")
    save_state(token, state)
    SOLVER_CACHE[token] = solver
    return {"status": "ok", "user_name": name}


@app.post("/api/logout")
async def api_logout(response: Response, session_token: Optional[str] = Cookie(None)):
    if session_token:
        SOLVER_CACHE.pop(session_token, None)
        path = get_session_file(session_token)
        if os.path.exists(path):
            os.remove(path)
    response.delete_cookie("session_token")
    return {"status": "ok"}


@app.get("/api/courses")
async def api_get_courses(session_token: Optional[str] = Cookie(None)):
    if not session_token:
        raise HTTPException(status_code=401, detail="Не авторизован")
    state = load_state(session_token)
    solver = get_solver(session_token, state)
    if not solver:
        raise HTTPException(status_code=401, detail="Сессия не найдена")

    st, courses, msg = solver.get_courses()
    if st != Status.OK:
        raise HTTPException(status_code=500, detail=msg)

    state["courses"] = courses
    save_state(session_token, state)
    return {"courses": courses}


@app.post("/api/select-course")
async def api_select_course(payload: CoursePayload, session_token: Optional[str] = Cookie(None)):
    if not session_token:
        raise HTTPException(status_code=401, detail="Не авторизован")
    state = load_state(session_token)
    state["cid"] = payload.cid
    state["aid"] = None
    state["problems"] = []
    state["problem_statuses"] = {}
    save_state(session_token, state)

    solver = get_solver(session_token, state)
    st, assignments, msg = solver.get_lessons(payload.cid)
    if st != Status.OK:
        raise HTTPException(status_code=500, detail=msg)

    state["assignments"] = assignments
    save_state(session_token, state)
    return {"status": "ok", "assignments": assignments}


@app.post("/api/select-assignment")
async def api_select_assignment(payload: AssignmentPayload, session_token: Optional[str] = Cookie(None)):
    if not session_token:
        raise HTTPException(status_code=401, detail="Не авторизован")
    state = load_state(session_token)
    state["aid"] = payload.aid
    solver = get_solver(session_token, state)
    solver.aid = payload.aid
    solver.data = None

    st, problems = solver.get_problems()
    if st != Status.OK:
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки задач: {st.name}")

    state["problems"] = problems
    state["problem_statuses"] = {str(i): "idle" for i in range(1, len(problems) + 1)}
    state["current_idx"] = 1
    save_state(session_token, state)
    return {
        "status": "ok",
        "problems_count": len(problems),
        "problem_statuses": state["problem_statuses"],
    }


@app.get("/api/problem/{idx}")
async def api_get_problem(idx: int, session_token: Optional[str] = Cookie(None)):
    if not session_token:
        raise HTTPException(status_code=401, detail="Не авторизован")
    state = load_state(session_token)
    solver = get_solver(session_token, state)
    if not solver or not state.get("aid"):
        raise HTTPException(status_code=400, detail="Урок не выбран")

    state["current_idx"] = idx
    save_state(session_token, state)

    st_disp, p_type, raw_disp = solver.handle_problem_display_solution(idx)
    if st_disp != Status.OK:
        raise HTTPException(status_code=500, detail=f"Ошибка: {st_disp.name}")

    content = format_marker_display(raw_disp) if p_type == "practice" else raw_disp
    return {"idx": idx, "type": p_type, "content": content}


@app.post("/api/solve-one")
async def api_solve_one(payload: SolveOnePayload, session_token: Optional[str] = Cookie(None)):
    if not session_token:
        raise HTTPException(status_code=401, detail="Не авторизован")
    state = load_state(session_token)
    solver = get_solver(session_token, state)
    if not solver:
        raise HTTPException(status_code=401, detail="Сессия не найдена")

    idx = payload.idx
    st_disp, p_type, disp = solver.handle_problem_display_solution(idx)

    if p_type == "theory":
        st_res = solver.handle_problem_solution(idx)
        st_code = st_res[0] if isinstance(st_res, tuple) else Status.OK
        raw_msg = st_res[2] if isinstance(st_res, tuple) and len(st_res) > 2 else "OK"
    else:
        st_res = solver.handle_problem_solution(idx, fake_timedelta=payload.fake_timedelta)
        st_code = st_res[0] if isinstance(st_res, tuple) else st_res
        raw_msg = st_res[2] if isinstance(st_res, tuple) and len(st_res) > 2 else ""

    statuses = state.get("problem_statuses", {})
    if st_code == Status.OK:
        statuses[str(idx)] = "ok"
    elif st_code in (Status.WRONG_PROBLEM_TYPE, Status.SOLUTION_FAILURE_UNKNOWN_PROBLEM_TYPE):
        statuses[str(idx)] = "unsupported"
    else:
        statuses[str(idx)] = "fail"

    log_blocks = [
        "============================================================",
        f"Задача #{idx} [Тип: {p_type}] | Fake TimeDelta: {payload.fake_timedelta}s",
        "--- ГОТОВОЕ РЕШЕНИЕ / КОД / ОТВЕТ ---",
        disp.strip() if disp else "[Пусто]",
        "--- РЕЗУЛЬТАТ ОТПРАВКИ ---",
        f"Статус решения : {st_code.name}",
        f"Ответ сервера  : {raw_msg.strip() if raw_msg else 'Успешно'}",
        "============================================================"
    ]
    full_log = "\n".join(log_blocks)

    state["logs"].append(full_log)
    state["problem_statuses"] = statuses
    save_state(session_token, state)

    return {
        "status": statuses[str(idx)],
        "type": p_type,
        "st_name": st_code.name,
        "log": full_log
    }


@app.post("/api/append-log")
async def api_append_log(payload: LogAppendPayload, session_token: Optional[str] = Cookie(None)):
    if session_token:
        st = load_state(session_token)
        st["logs"].append(payload.log)
        save_state(session_token, st)
    return {"status": "ok"}


@app.post("/api/update-status")
async def api_update_status(data: dict, session_token: Optional[str] = Cookie(None)):
    if session_token:
        st = load_state(session_token)
        idx = str(data.get("idx"))
        status = data.get("status")
        if idx and status:
            st["problem_statuses"][idx] = status
            save_state(session_token, st)
    return {"status": "ok"}


@app.post("/api/clear-logs")
async def api_clear_logs(session_token: Optional[str] = Cookie(None)):
    if session_token:
        st = load_state(session_token)
        st["logs"] = []
        save_state(session_token, st)
    return {"status": "ok"}


def main():
    print("Запуск авто-решателя: http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")


if __name__ == "__main__":
    main()
