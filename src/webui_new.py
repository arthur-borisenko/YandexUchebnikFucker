# -*- coding: utf-8 -*-
"""
Web UI (SPA) для Yandex Uchebnik Fucker v3.

Отличия от простой версии:

* ПОЛНЫЕ ЛОГИ в реальном времени. Всё, что модули ``main.*`` печатают в
  ``stdout``/``stderr`` (включая ``traceback.print_exc()``), перехватывается и
  попадает в терминал веб-интерфейса, а не теряется в консоли сервера.
* СТЕКТРЕЙСЫ. Любая ошибка возвращается в API вместе с полным ``traceback``,
  он показывается в панели ошибок и в терминале.
* СООБЩЕНИЯ САМОГО YANDEX UCHEBNIK. ``YandexUchebnik.new_msgs`` (например
  ``COOKIES_GENERATE_ERROR: <ответ сервера>``, ``Max retries exceeded!``,
  ``CLessonRun or CLessonResult not found in data ...``) теперь выводятся
  в веб-интерфейсе отдельным источником ``yandex``.
* LIVE-ОБНОВЛЕНИЕ логов через SSE (``/api/logs/stream``) + отчёт о состоянии
  соединения в статус-баре.
"""

from __future__ import annotations

import asyncio
import contextvars
import io
import json
import logging
import os
import re
import sys
import threading
import time
import traceback
import uuid
from typing import Any, Callable, Optional

from fastapi import Cookie, FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel
import uvicorn

from main.uchebnik import YandexUchebnik
from main.util import Status

# ---------------------------------------------------------------------------
# Клиентская часть (SPA)
# ---------------------------------------------------------------------------

INDEX_HTML = r"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Yandex Uchebnik Solver 95 [REST SPA]</title>
<style>
body{background-color:#008080;font-family:'MS Sans Serif',Tahoma,'Segoe UI',sans-serif;font-size:11px;margin:10px;color:#000}
.window{background:#c0c0c0;border:none;box-shadow:none;max-width:1150px;margin:0 auto}
.title-bar{background:linear-gradient(90deg,#000080,#1084d0);padding:3px 6px;display:flex;justify-content:space-between;align-items:center;color:white;font-weight:bold}
.window-body{padding:10px}
fieldset{border:2px groove #dfdfdf;padding:8px 10px;margin-bottom:8px}
legend{padding:0 4px;font-weight:bold}
.btn{background:#c0c0c0;border:2px solid;border-color:#dfdfdf #404040 #404040 #dfdfdf;padding:3px 10px;font-family:inherit;font-size:11px;cursor:pointer;box-shadow:1px 1px 0 #000}
.btn:active{border-color:#404040 #dfdfdf #dfdfdf #404040;padding:4px 9px 2px 11px;box-shadow:none}
.btn:disabled{color:#808080;cursor:not-allowed;border-color:#dfdfdf #808080 #808080 #dfdfdf}
input[type="text"],input[type="number"],select{background:#fff;border:2px inset #808080;padding:3px 5px;font-family:inherit;font-size:11px}
.task-bar{display:flex;flex-wrap:wrap;gap:4px;padding:6px;background:#e0e0e0;border:2px inset #808080;margin-bottom:8px;min-height:26px}
.task-btn{min-width:28px;height:24px;font-weight:bold;font-size:11px;color:#fff;border:2px solid;border-color:#dfdfdf #404040 #404040 #dfdfdf;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;user-select:none}
.task-btn.active{outline:1px dotted #000;border-color:#000 #fff #fff #000}
.legend-bar{display:flex;gap:12px;font-size:10px;margin-bottom:6px;align-items:center;flex-wrap:wrap}
.legend-item{display:flex;align-items:center;gap:4px}
.legend-color{width:10px;height:10px;border:1px solid #000}
.content-box{background:#fff;border:2px inset #808080;padding:8px;font-family:'Courier New',monospace;font-size:12px;white-space:pre-wrap;height:220px;overflow-y:auto}
.log-box{background:#000;color:#9ee493;border:2px inset #808080;padding:6px;font-family:'Courier New',monospace;font-size:11px;white-space:pre-wrap;height:340px;overflow-y:auto}
.log-line{white-space:pre-wrap;word-break:break-word}
.log-ts{color:#5f8f5f}
.log-tag{color:#7f9fd0}
.log-toolbar{display:flex;gap:10px;align-items:center;margin-top:5px;flex-wrap:wrap}
.log-status{margin-left:auto;font-size:10px;color:#333333}
.error-box{background:#ffe4e4;border:2px solid #cc0000;padding:6px 8px;margin-bottom:8px;color:#660000}
.error-head{font-weight:bold;font-size:12px}
.error-status{font-size:10px;margin-top:2px;color:#883333}
.error-msg{font-size:11px;margin-top:4px;white-space:pre-wrap;word-break:break-word;background:#fff6f6;border:1px solid #e0a0a0;padding:4px}
.error-detail{font-size:11px;margin-top:3px;white-space:pre-wrap;word-break:break-word}
.error-trace{background:#000;color:#ff9dff;border:1px inset #808080;padding:6px;margin:4px 0 0;font-family:'Courier New',monospace;font-size:11px;white-space:pre-wrap;max-height:240px;overflow:auto}
.status-bar{border-top:1px solid #808080;margin-top:6px;padding-top:4px;display:flex;gap:8px;flex-wrap:wrap}
.status-panel{border:1px inset #808080;padding:2px 6px;font-size:10px}
.hidden{display:none !important}
</style>
</head>
<body>
<div class="window">
  <div class="title-bar">
    <div id="titleText">💾 Yandex.Uchebnik Solver 95 [REST SPA]</div>
    <div><button class="btn" onclick="logout()" style="padding:0 3px;height:14px;line-height:10px;">✕</button></div>
  </div>
  <div class="window-body">

    <div id="errorBox" class="error-box hidden"></div>

    <div id="view-login" class="hidden">
      <fieldset><legend>Идентификация пользователя</legend>
        <div style="margin-bottom:8px;"><label style="display:inline-block;width:100px;">Логин ученика:</label><input type="text" id="loginInput" style="width:250px;"></div>
        <div style="margin-bottom:8px;"><label style="display:inline-block;width:100px;">Код школы:</label><input type="text" id="codeInput" style="width:250px;"></div>
        <button class="btn" onclick="doLogin()">Войти через REST</button>
      </fieldset>
    </div>

    <div id="view-courses" class="hidden">
      <fieldset><legend>Выбор активного курса</legend>
        <select id="coursesSelect" size="6" style="width:100%;margin-bottom:8px;"></select><br>
        <button class="btn" onclick="selectCourse()">Открыть уроки курса &gt;&gt;</button>
      </fieldset>
    </div>

    <div id="view-assignments" class="hidden">
      <fieldset><legend>Выбор урока / задания</legend>
        <select id="assignmentsSelect" size="8" style="width:100%;margin-bottom:8px;"></select><br>
        <button class="btn" onclick="selectAssignment()">Загрузить инспектор заданий &gt;&gt;</button>
        <button class="btn" onclick="showCourses()">Назад к курсам</button>
      </fieldset>
    </div>

    <div id="view-dashboard" class="hidden">
      <div class="legend-bar">
        <span style="font-weight:bold;">Статусы:</span>
        <div class="legend-item"><div class="legend-color" style="background:#808080;"></div> Серый (Не запускалась)</div>
        <div class="legend-item"><div class="legend-color" style="background:#008000;"></div> Зеленый (OK)</div>
        <div class="legend-item"><div class="legend-color" style="background:#cc0000;"></div> Красный (Fail)</div>
        <div class="legend-item"><div class="legend-color" style="background:#d97706;"></div> Оранжевый (Не подд.)</div>
        <div class="legend-item"><div class="legend-color" style="background:#0055d4;"></div> Синий (Пропущено)</div>
      </div>
      <div class="task-bar" id="taskBar"></div>
      <div style="display:grid;grid-template-columns:1fr 340px;gap:10px;">
        <fieldset><legend id="taskTitle">Инспектор задачи</legend>
          <div style="margin-bottom:4px;font-weight:bold;">Условие и готовое решение:</div>
          <div class="content-box" id="taskContent">Загрузка данных...</div>
          <div style="margin-top:8px;display:flex;gap:6px;align-items:center;">
            <label>Fake TimeDelta:</label><input type="number" id="singleTime" value="15" style="width:50px;"> сек.
            <button class="btn" id="btnSingle" onclick="sendSingle()">Отправить задачу</button>
          </div>
        </fieldset>
        <fieldset><legend>Пакетное авторешение (Поштучные запросы)</legend>
          <div style="margin-bottom:6px;font-weight:bold;">Диапазон номеров:</div>
          <div style="margin-bottom:8px;">с <input type="number" id="taskFrom" value="1" style="width:45px;"> по <input type="number" id="taskTo" value="999" style="width:45px;"></div>
          <div style="margin-bottom:6px;font-weight:bold;">Фильтр типов:</div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;margin-bottom:8px;">
            <label><input type="checkbox" id="chk-coding" checked> Coding</label>
            <label><input type="checkbox" id="chk-practice" checked> Marker/Pract</label>
            <label><input type="checkbox" id="chk-theory" checked> Theory</label>
            <label><input type="checkbox" id="chk-web" checked> Web</label>
            <label><input type="checkbox" id="chk-misc" checked> Misc</label>
          </div>
          <div style="margin-bottom:8px;"><label>Задержка (сек):</label><br>от <input type="number" id="timeMin" value="10" style="width:45px;"> до <input type="number" id="timeMax" value="30" style="width:45px;"></div>
          <div style="display:flex;gap:6px;">
            <button class="btn" id="btnBatch" style="flex:1;font-weight:bold;height:28px;" onclick="runBatchIndividual()">▶ Старт авторешения</button>
            <button class="btn" id="btnStop" style="display:none;height:28px;background:#cc0000;color:#fff;" onclick="stopBatch()">■ Стоп</button>
          </div>
          <button class="btn" style="width:100%;margin-top:6px;" onclick="showAssignments()">⬅ Сменить урок</button>
        </fieldset>
      </div>
    </div>

    <fieldset id="logPanel">
      <legend>Системный терминал (полные логи, стектрейсы, сообщения Yandex Uchebnik)</legend>
      <div class="log-box" id="logBox"></div>
      <div class="log-toolbar">
        <label><input type="checkbox" id="chkFollow" checked> Автопрокрутка</label>
        <label><input type="checkbox" id="chkStack" checked> Показывать стектрейсы</label>
        <button class="btn" onclick="clearLogs()">Очистить лог</button>
        <button class="btn" onclick="copyLogs()">Копировать лог</button>
        <span class="log-status" id="logStatus">Лог-стрим: не подключен</span>
      </div>
    </fieldset>

    <div class="status-bar">
      <div class="status-panel" id="statCourse">Курс: -</div>
      <div class="status-panel" id="statLesson">Урок: -</div>
      <div class="status-panel" id="statCount">Задач: 0</div>
      <div class="status-panel" style="flex:1;" id="statUser">Не авторизован</div>
    </div>

  </div>
</div>

<script>
const $=(id)=>document.getElementById(id);
const COLOR_MAP={idle:"#808080",ok:"#008000",fail:"#cc0000",unsupported:"#d97706",skipped:"#0055d4"};
let AppState={currentIdx:1,problemsCount:0,problemStatuses:{}};
let isBatchRunning=false;
let logStream=null, logStreamOk=false, lastSeq=0;

/* Токен сессии. Cookies в webview/iframe могут не сохраняться, поэтому держим
   токен ещё и в localStorage и шлём его заголовком X-Session-Token. */
let SESSION="";
try{SESSION=localStorage.getItem("yuf_token")||"";}catch(e){SESSION="";}
function setSession(t){
  SESSION=t||"";
  try{ if(SESSION){localStorage.setItem("yuf_token",SESSION);}else{localStorage.removeItem("yuf_token");} }catch(e){}
}

/* -------------------- работа с логами -------------------- */
function fmtTs(ts){const d=new Date(ts*1000);const p=(n,l)=>String(n).padStart(l,"0");return p(d.getHours(),2)+":"+p(d.getMinutes(),2)+":"+p(d.getSeconds(),2)+"."+p(d.getMilliseconds(),3);}
function lvlColor(e){
  if(e.source==="traceback") return "#ff9dff";
  if(e.source==="yandex") return "#ffd866";
  if(e.source==="stderr") return "#ff8080";
  if(e.source==="solver") return "#8ab4f8";
  if(e.source==="webui") return "#e8e8e8";
  return {INFO:"#9ee493",WARN:"#ffd866",ERROR:"#ff8080",TRACE:"#ff9dff"}[e.level]||"#d0d0d0";
}
function followOn(){return $("chkFollow").checked;}
function stackOn(){return $("chkStack").checked;}
function appendEntry(e){
  if(!e) return;
  if(e.seq){ if(e.seq<=lastSeq) return; lastSeq=e.seq; }
  if(!stackOn() && (e.source==="traceback" || e.level==="TRACE")) return;
  const box=$("logBox");
  const line=document.createElement("div");
  line.className="log-line";
  const ts=document.createElement("span");
  ts.className="log-ts";
  ts.textContent=fmtTs(e.ts);
  const tag=document.createElement("span");
  tag.className="log-tag";
  tag.textContent="["+e.level+"/"+e.source+"]";
  const body=document.createElement("span");
  body.className="log-body";
  body.textContent=e.text;
  body.style.color=lvlColor(e);
  line.appendChild(ts);
  line.appendChild(document.createTextNode(" "));
  line.appendChild(tag);
  line.appendChild(document.createTextNode(" "));
  line.appendChild(body);
  box.appendChild(line);
  while(box.childElementCount>3000){box.removeChild(box.firstChild);}
  if(followOn()){box.scrollTop=box.scrollHeight;}
}
function appendLocal(level,source,text){
  appendEntry({seq:0,ts:Date.now()/1000,level:level,source:source,text:text});
}
function setLogs(entries){
  const box=$("logBox");
  box.innerHTML="";
  lastSeq=0;
  (entries||[]).forEach(appendEntry);
}
function clearLogBox(){$("logBox").innerHTML="";lastSeq=0;}

/* -------------------- панель ошибок -------------------- */
function showError(title,detail,tb,status,msg){
  const box=$("errorBox");
  box.innerHTML="";
  box.classList.remove("hidden");
  const head=document.createElement("div");
  head.className="error-head";
  head.textContent="⚠ "+(title||"Ошибка");
  box.appendChild(head);
  if(status){
    const st=document.createElement("div");
    st.className="error-status";
    st.textContent="Статус: "+status;
    box.appendChild(st);
  }
  if(msg){
    const m=document.createElement("div");
    m.className="error-msg";
    m.textContent="Ответ Yandex Uchebnik: "+msg;
    box.appendChild(m);
  }
  if(detail && detail!==title){
    const d=document.createElement("div");
    d.className="error-detail";
    d.textContent=detail;
    box.appendChild(d);
  }
  if(tb){
    const det=document.createElement("details");
    det.open=true;
    const sm=document.createElement("summary");
    sm.textContent="Полный стектрейс";
    const pre=document.createElement("pre");
    pre.className="error-trace";
    pre.textContent=tb;
    det.appendChild(sm);
    det.appendChild(pre);
    box.appendChild(det);
  }
}
function hideError(){const box=$("errorBox");box.classList.add("hidden");box.innerHTML="";}

/* -------------------- запросы -------------------- */
async function req(url,method,data){
  const opts={method:method||"GET",headers:{}};
  if(SESSION){opts.headers["X-Session-Token"]=SESSION;}
  if(data){opts.headers["Content-Type"]="application/json";opts.body=JSON.stringify(data);}
  let resp;
  try{resp=await fetch(url,opts);}
  catch(e){
    const msg="Сеть недоступна: "+e.message;
    showError(msg,"",e.stack||"","network");
    appendLocal("ERROR","webui",msg+(e.stack?("\n"+e.stack):""));
    throw new Error(msg);
  }
  let payload=null;
  try{payload=await resp.json();}catch(e){payload=null;}
  if(!resp.ok || (payload && payload.ok===false)){
    const message=(payload && (payload.error||payload.detail))||("Ошибка сервера: HTTP "+resp.status);
    const tb=(payload && payload.traceback)||"";
    const status=(payload && payload.status)||("HTTP "+resp.status);
    const msg=(payload && payload.msg)||"";
    showError(message,"",tb,status,msg);
    if(payload && payload.log_entries && payload.log_entries.length){
      payload.log_entries.forEach(appendEntry);
    }else{
      appendLocal("ERROR","webui",message+(tb?("\n"+tb):""));
    }
    if(msg){appendLocal("ERROR","yandex","Ответ Yandex Uchebnik: "+msg);}
    const err=new Error(message);
    err.payload=payload;
    err.traceback=tb;
    err.msg=msg;
    throw err;
  }
  return payload||{};
}

/* -------------------- live-стрим логов (SSE) -------------------- */
function setStreamStatus(txt){$("logStatus").textContent=txt;}
function connectStream(){
  if(logStream){logStream.close();logStream=null;}
  logStreamOk=false;
  setStreamStatus("Лог-стрим: подключение...");
  try{
    const streamUrl="/api/logs/stream"+(SESSION?("?token="+encodeURIComponent(SESSION)):"");
    logStream=new EventSource(streamUrl);
    logStream.onopen=function(){logStreamOk=true;setStreamStatus("Лог-стрим: подключено (live)");};
    logStream.onerror=function(){logStreamOk=false;setStreamStatus("Лог-стрим: ошибка, переподключение...");};
    logStream.onmessage=function(ev){
      let data=null;
      try{data=JSON.parse(ev.data);}catch(e){return;}
      if(data.type==="backlog" && data.entries){data.entries.forEach(appendEntry);}
      else if(data.type==="entry"){appendEntry(data.entry);}
    };
  }catch(e){setStreamStatus("Лог-стрим недоступен: "+e.message);}
}

/* -------------------- навигация -------------------- */
function showView(viewId){
  ["view-login","view-courses","view-assignments","view-dashboard"].forEach(function(id){$(id).classList.add("hidden");});
  $(viewId).classList.remove("hidden");
}
async function init(){
  try{
    const state=await req("/api/state");
    connectStream();
    if(!state.authenticated){showView("view-login");return;}
    $("statUser").innerText="👤 "+state.user_name;
    setLogs(state.log_entries||[]);
    if(state.aid){
      AppState.currentIdx=state.current_idx||1;
      AppState.problemsCount=state.problems_count;
      AppState.problemStatuses=state.problem_statuses||{};
      updateStatusBar(state.cid,state.aid,state.problems_count);
      $("taskFrom").value=1;
      $("taskTo").value=state.problems_count;
      renderTaskBar();
      loadProblem(AppState.currentIdx);
      showView("view-dashboard");
    }else if(state.cid){showAssignments();}
    else{showCourses();}
  }catch(e){showView("view-login");}
}
async function doLogin(){
  const login=$("loginInput").value.trim();
  const code=$("codeInput").value.trim();
  if(!login||!code){alert("Заполните логин и код!");return;}
  hideError();
  try{
    const res=await req("/api/login","POST",{login:login,code:code});
    if(res.token){setSession(res.token);}
    $("statUser").innerText="👤 "+res.user_name;
    appendLocal("INFO","webui","> Вход выполнен успешно");
    connectStream();
    showCourses();
  }catch(e){}
}
async function logout(){
  try{await req("/api/logout","POST");}catch(e){}
  setSession("");
  location.reload();
}
async function showCourses(){
  try{
    const res=await req("/api/courses");
    const select=$("coursesSelect");
    select.innerHTML="";
    (res.courses||[]).forEach(function(c){
      const o=document.createElement("option");
      o.value=c.id;
      o.textContent=c.name+" (Заданий: "+c.cnt+")";
      select.appendChild(o);
    });
    showView("view-courses");
  }catch(e){}
}
async function selectCourse(){
  const cid=$("coursesSelect").value;
  if(!cid){alert("Выберите курс!");return;}
  try{
    const res=await req("/api/select-course","POST",{cid:cid});
    $("statCourse").innerText="Курс: "+cid;
    renderAssignmentsList(res.assignments);
    showView("view-assignments");
  }catch(e){}
}
function renderAssignmentsList(assignments){
  const select=$("assignmentsSelect");
  select.innerHTML="";
  (assignments||[]).forEach(function(a){
    const o=document.createElement("option");
    o.value=a.id;
    o.textContent=a.name+" (Задач: "+a.problems+")";
    select.appendChild(o);
  });
}
async function showAssignments(){
  const cid=$("statCourse").innerText.replace("Курс:","");
  if(!cid||cid==="-"){showCourses();return;}
  try{
    const res=await req("/api/select-course","POST",{cid:cid});
    renderAssignmentsList(res.assignments);
    showView("view-assignments");
  }catch(e){}
}
async function selectAssignment(){
  const aid=$("assignmentsSelect").value;
  if(!aid){alert("Выберите урок!");return;}
  try{
    const res=await req("/api/select-assignment","POST",{aid:aid});
    AppState.problemsCount=res.problems_count;
    AppState.problemStatuses=res.problem_statuses||{};
    AppState.currentIdx=1;
    $("statLesson").innerText="Урок: "+aid;
    $("statCount").innerText="Задач: "+res.problems_count;
    $("taskFrom").value=1;
    $("taskTo").value=res.problems_count;
    renderTaskBar();
    loadProblem(1);
    showView("view-dashboard");
  }catch(e){}
}
function updateStatusBar(cid,aid,count){
  $("statCourse").innerText="Курс: "+(cid||"-");
  $("statLesson").innerText="Урок: "+(aid||"-");
  $("statCount").innerText="Задач: "+count;
}
function renderTaskBar(){
  const bar=$("taskBar");
  bar.innerHTML="";
  for(let i=1;i<=AppState.problemsCount;i++){
    const btn=document.createElement("div");
    btn.className="task-btn"+(i===AppState.currentIdx?" active":"");
    const st=AppState.problemStatuses[String(i)]||"idle";
    btn.style.backgroundColor=COLOR_MAP[st]||"#808080";
    btn.innerText=i;
    btn.onclick=function(){
      if(isBatchRunning) return;
      AppState.currentIdx=i;
      renderTaskBar();
      loadProblem(i);
    };
    bar.appendChild(btn);
  }
}
async function loadProblem(idx){
  $("taskTitle").innerText="Инспектор задачи #"+idx+" [Загрузка...]";
  $("taskContent").innerText="Получение условия и решения с сервера...";
  try{
    const res=await req("/api/problem/"+idx);
    $("taskTitle").innerText="Инспектор задачи #"+res.idx+" [Тип: "+res.type+"]";
    $("taskContent").innerText=res.content;
    return res;
  }catch(e){
    $("taskContent").innerText="Ошибка: "+e.message;
    return null;
  }
}
async function sendSingle(){
  const sec=parseInt($("singleTime").value)||15;
  const btn=$("btnSingle");
  btn.disabled=true;
  hideError();
  try{
    const res=await req("/api/solve-one","POST",{idx:AppState.currentIdx,fake_timedelta:sec});
    AppState.problemStatuses[String(AppState.currentIdx)]=res.status;
    renderTaskBar();
    if(!logStreamOk && res.log){appendLocal(res.st_name==="OK"?"INFO":"ERROR","solver",res.log);}
  }catch(e){
  }finally{btn.disabled=false;}
}
async function runBatchIndividual(){
  if(isBatchRunning) return;
  const types=[];
  if($("chk-coding").checked) types.push("coding");
  if($("chk-practice").checked) types.push("practice");
  if($("chk-theory").checked) types.push("theory");
  if($("chk-web").checked) types.push("web");
  if($("chk-misc").checked) types.push("misc");
  const tMin=parseInt($("timeMin").value)||10;
  const tMax=parseInt($("timeMax").value)||30;
  const tFrom=Math.max(1,parseInt($("taskFrom").value)||1);
  const tTo=Math.min(AppState.problemsCount,parseInt($("taskTo").value)||AppState.problemsCount);
  isBatchRunning=true;
  $("btnBatch").style.display="none";
  $("btnStop").style.display="block";
  $("btnSingle").disabled=true;
  appendLocal("INFO","webui",">>> СТАРТ ПОШТУЧНОГО АВТОРЕШЕНИЯ [Диапазон: #"+tFrom+"..#"+tTo+", Типы: "+types.join(", ")+"]");
  for(let i=1;i<=AppState.problemsCount;i++){
    if(!isBatchRunning){appendLocal("WARN","webui",">>> АВТОРЕШЕНИЕ ПРИНУДИТЕЛЬНО ОСТАНОВЛЕНО ПОЛЬЗОВАТЕЛЕМ");break;}
    if(i<tFrom||i>tTo){
      AppState.problemStatuses[String(i)]="skipped";
      renderTaskBar();
      try{await req("/api/update-status","POST",{idx:i,status:"skipped"});}catch(e){}
      continue;
    }
    const prob=await loadProblem(i);
    if(!prob){
      AppState.problemStatuses[String(i)]="fail";
      renderTaskBar();
      continue;
    }
    let typeMatch=types.indexOf(prob.type)>=0;
    if(!typeMatch && ["coding","practice","theory","web"].indexOf(prob.type)<0 && types.indexOf("misc")>=0){typeMatch=true;}
    if(!typeMatch){
      AppState.problemStatuses[String(i)]="skipped";
      renderTaskBar();
      const skipMsg="Задача #"+i+" ["+prob.type+"]: Пропущена фильтром типов";
      appendLocal("INFO","webui",skipMsg);
      try{await req("/api/append-log","POST",{log:skipMsg});}catch(e){}
      try{await req("/api/update-status","POST",{idx:i,status:"skipped"});}catch(e){}
      continue;
    }
    const randDelay=Math.floor(Math.random()*(Math.max(tMin,tMax)-Math.min(tMin,tMax)+1))+Math.min(tMin,tMax);
    try{
      const res=await req("/api/solve-one","POST",{idx:i,fake_timedelta:randDelay});
      AppState.problemStatuses[String(i)]=res.status;
      renderTaskBar();
      if(!logStreamOk && res.log){appendLocal(res.st_name==="OK"?"INFO":"ERROR","solver",res.log);}
    }catch(err){
      AppState.problemStatuses[String(i)]="fail";
      renderTaskBar();
      const errMsg="[FAIL] Ошибка отправки #"+i+": "+err.message;
      appendLocal("ERROR","webui",errMsg);
      try{await req("/api/append-log","POST",{log:errMsg});}catch(e){}
      try{await req("/api/update-status","POST",{idx:i,status:"fail"});}catch(e){}
    }
  }
  isBatchRunning=false;
  $("btnBatch").style.display="block";
  $("btnStop").style.display="none";
  $("btnSingle").disabled=false;
  appendLocal("INFO","webui",">>> ОЧЕРЕДЬ ОТПРАВКИ ЗАВЕРШЕНА");
}
function stopBatch(){isBatchRunning=false;}
async function clearLogs(){
  try{await req("/api/clear-logs","POST");}catch(e){}
  clearLogBox();
}
async function copyLogs(){
  const text=$("logBox").innerText;
  try{
    await navigator.clipboard.writeText(text);
    appendLocal("INFO","webui","Лог скопирован в буфер обмена.");
  }catch(e){appendLocal("ERROR","webui","Не удалось скопировать лог: "+e.message);}
}
window.onload=init;
</script>
</body>
</html>"""

# ---------------------------------------------------------------------------
# Инфраструктура логирования
# ---------------------------------------------------------------------------

GLOBAL_SESSION = "-"          # лог без привязки к сессии
CURRENT_SESSION: contextvars.ContextVar[str] = contextvars.ContextVar(
    "yuf_current_session", default=GLOBAL_SESSION
)

# Токен последней успешной авторизации. Нужен, потому что в webview/iframe
# (например, превью на телефоне) cookies могут не сохраняться вовсе — тогда
# единственный способ связать запросы с сессией это заголовок X-Session-Token,
# который шлёт наш же фронтенд, либо этот «активный» токен по умолчанию.
ACTIVE_TOKEN: str = GLOBAL_SESSION


def resolve_token(
    session_token: Optional[str] = None, request: Optional[Request] = None
) -> str:
    """Определяет токен сессии по запросу.

    Порядок: заголовок X-Session-Token -> ?token= -> cookie -> активная сессия.
    """
    if request is not None:
        header_token = request.headers.get("X-Session-Token")
        if header_token:
            return header_token
        query_token = request.query_params.get("token")
        if query_token:
            return query_token
    return session_token or ACTIVE_TOKEN or GLOBAL_SESSION


MAX_ENTRY_CHARS = 20000        # максимальная длина одной записи лога
MAX_ENTRIES_PER_SESSION = 4000  # сколько записей храним в памяти на сессию


class LogHub:
    """Хранилище логов: запись, чтение, live-подписка (SSE) и seed из файла.

    Потокобезопасно: записи могут приходить из потоков солвера (asyncio.to_thread).
    """

    def __init__(self, max_entries: int = MAX_ENTRIES_PER_SESSION):
        self._lock = threading.Lock()
        self._max_entries = max_entries
        self._entries: dict[str, list[dict]] = {}
        self._subscribers: dict[str, list[tuple[Any, asyncio.Queue]]] = {}
        self._seeded: set[str] = set()
        self._seq = 0

    # -- внутренние helpers -------------------------------------------------
    @staticmethod
    def _session(session: Optional[str]) -> str:
        return session or GLOBAL_SESSION

    # -- запись -------------------------------------------------------------
    def add(
        self,
        session: Optional[str],
        level: str,
        source: str,
        text: str,
    ) -> dict:
        if text is None:
            return {}
        text = str(text)
        if not text.strip():
            return {}
        if len(text) > MAX_ENTRY_CHARS:
            text = (
                text[:MAX_ENTRY_CHARS]
                + f"\n... [обрезано, всего символов: {len(text)}]"
            )
        session = self._session(session)
        with self._lock:
            self._seq += 1
            entry = {
                "seq": self._seq,
                "ts": time.time(),
                "level": level,
                "source": source,
                "text": text,
            }
            bucket = self._entries.setdefault(session, [])
            bucket.append(entry)
            if len(bucket) > self._max_entries:
                del bucket[: len(bucket) - self._max_entries]
            subs = list(self._subscribers.get(session, ()))
        for loop, queue in subs:
            try:
                loop.call_soon_threadsafe(queue.put_nowait, entry)
            except RuntimeError:  # цикл уже закрыт
                pass
        return entry

    # -- чтение -------------------------------------------------------------
    def get(self, session: Optional[str], since_seq: int = 0) -> list[dict]:
        session = self._session(session)
        with self._lock:
            bucket = self._entries.get(session, [])
            if since_seq <= 0:
                return list(bucket)
            return [e for e in bucket if e["seq"] > since_seq]

    def entries_since(self, session: Optional[str], seq: int) -> list[dict]:
        return self.get(session, since_seq=seq)

    def last_seq(self, session: Optional[str]) -> int:
        session = self._session(session)
        with self._lock:
            bucket = self._entries.get(session, [])
            return bucket[-1]["seq"] if bucket else 0

    def format_lines(self, session: Optional[str]) -> list[str]:
        return [format_entry(e) for e in self.get(session)]

    # -- очистка / восстановление ------------------------------------------
    def clear(self, session: Optional[str]) -> None:
        session = self._session(session)
        with self._lock:
            self._entries.pop(session, None)
            self._seeded.add(session)

    def seed(self, session: Optional[str], lines) -> None:
        """Восстанавливает логи из файла сессии (только если их ещё нет)."""
        session = self._session(session)
        with self._lock:
            if session in self._seeded:
                return
            self._seeded.add(session)
            bucket = self._entries.setdefault(session, [])
            if bucket:
                return
            for line in lines or []:
                self._seq += 1
                bucket.append(
                    {
                        "seq": self._seq,
                        "ts": time.time(),
                        "level": "INFO",
                        "source": "legacy",
                        "text": str(line),
                    }
                )

    # -- live-подписка ------------------------------------------------------
    def subscribe(self, session: Optional[str], loop) -> asyncio.Queue:
        session = self._session(session)
        queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        with self._lock:
            self._subscribers.setdefault(session, []).append((loop, queue))
        return queue

    def unsubscribe(self, session: Optional[str], queue: asyncio.Queue) -> None:
        session = self._session(session)
        with self._lock:
            subs = self._subscribers.get(session, [])
            self._subscribers[session] = [s for s in subs if s[1] is not queue]
            if not self._subscribers[session]:
                self._subscribers.pop(session, None)


hub = LogHub()


def format_entry(entry: dict) -> str:
    ts = entry.get("ts", time.time())
    stamp = time.strftime("%H:%M:%S", time.localtime(ts)) + ".%03d" % int(
        (ts % 1) * 1000
    )
    return "[%s] [%s] [%s] %s" % (
        stamp,
        entry.get("level", "INFO"),
        entry.get("source", "webui"),
        entry.get("text", ""),
    )


# ---------------------------------------------------------------------------
# Перехват print()/логов из main.*
# ---------------------------------------------------------------------------


class _StreamTee(io.TextIOBase):
    """Дублирует поток вывода в терминал веб-интерфейса."""

    def __init__(self, original, source: str):
        self._original = original
        self._source = source

    def write(self, data: str) -> int:  # noqa: D102
        try:
            self._original.write(data)
            self._original.flush()
        except Exception:
            pass
        try:
            text = str(data).rstrip("\n")
            if text.strip():
                level = "ERROR" if self._source == "stderr" else "INFO"
                hub.add(CURRENT_SESSION.get(), level, self._source, text)
        except Exception:
            pass
        return len(data)

    def flush(self) -> None:  # noqa: D102
        try:
            self._original.flush()
        except Exception:
            pass

    def isatty(self) -> bool:
        return False

    def writable(self) -> bool:
        return True

    def readable(self) -> bool:
        return False

    def fileno(self) -> int:
        return self._original.fileno()


class _HubLoggingHandler(logging.Handler):
    """Забирает записи стандартного модуля logging (вместе с traceback)."""

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D102
        try:
            if record.levelno >= logging.ERROR:
                level = "ERROR"
            elif record.levelno >= logging.WARNING:
                level = "WARN"
            else:
                level = "INFO"
            text = self.format(record)
            if record.exc_info:
                text += "\n" + "".join(
                    traceback.format_exception(*record.exc_info)
                )
            hub.add(CURRENT_SESSION.get(), level, "logging", text)
        except Exception:
            pass


_ORIGINAL_STDOUT = None
_ORIGINAL_STDERR = None


def install_output_capture() -> None:
    """Включает перехват stdout/stderr и logging (вызывается один раз)."""
    global _ORIGINAL_STDOUT, _ORIGINAL_STDERR
    if getattr(sys.stdout, "_yuf_capture", False):
        return
    _ORIGINAL_STDOUT = sys.stdout
    _ORIGINAL_STDERR = sys.stderr
    sys.stdout = _StreamTee(_ORIGINAL_STDOUT, "stdout")
    sys.stderr = _StreamTee(_ORIGINAL_STDERR, "stderr")
    try:
        sys.stdout._yuf_capture = True  # type: ignore[attr-defined]
        sys.stderr._yuf_capture = True  # type: ignore[attr-defined]
    except Exception:
        pass

    handler = _HubLoggingHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not any(isinstance(h, _HubLoggingHandler) for h in root.handlers):
        root.addHandler(handler)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).setLevel(logging.INFO)


install_output_capture()


# ---------------------------------------------------------------------------
# Приложение
# ---------------------------------------------------------------------------

app = FastAPI(title="Yandex Uchebnik Solver")

SESSIONS_DIR = os.path.join(os.getcwd(), "sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)
SOLVER_CACHE: dict[str, YandexUchebnik] = {}


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
    finally:
        # логи живут в LogHub; из файла берём только то, чего ещё нет в памяти
        hub.seed(token, default_state.get("logs") or [])


def save_state(token: str, state: dict):
    # в файл сессии кладём только последние строки лога, чтобы он не разрастался
    state["logs"] = hub.format_lines(token)[-1000:]
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


# ---------------------------------------------------------------------------
# Логирование «сообщений самого Yandex Uchebnik» и запуск блокирующего кода
# ---------------------------------------------------------------------------

_ERROR_MARKERS = (
    "ERROR",
    "FAIL",
    "NOT FOUND",
    "EXCEEDED",
    "CAPTCHA",
    "TRACEBACK",
)


def drain_solver_messages(solver: Optional[YandexUchebnik], token: str) -> list[str]:
    """Забирает new_msgs из YandexUchebnik и кладёт их в общий лог."""
    messages: list[str] = []
    if solver is None:
        return messages
    try:
        pop = getattr(solver, "pop_messages", None)
        if callable(pop):
            messages = [str(m) for m in pop()]
        else:
            messages = [str(m) for m in getattr(solver, "new_msgs", [])]
            solver.new_msgs.clear()
    except Exception:
        messages = []
    for msg in messages:
        upper = msg.upper()
        level = "ERROR" if any(marker in upper for marker in _ERROR_MARKERS) else "WARN"
        hub.add(token, level, "yandex", msg)
    return messages


async def run_blocking(token: str, func: Callable, *args, **kwargs):
    """Выполняет блокирующий код солвера в отдельном потоке.

    Нужно, чтобы (а) event loop не подвисал, (б) SSE-стрим успевал отдавать
    логи в реальном времени, (в) контекст сессии корректно пробросился в поток.
    """

    def _runner():
        CURRENT_SESSION.set(token)
        return func(*args, **kwargs)

    return await asyncio.to_thread(_runner)


async def call_solver(token: str, solver: YandexUchebnik, method: str, *args, **kwargs):
    """Вызывает метод солвера в потоке и сразу подхватывает его сообщения.

    Возвращает пару (результат, список_сообщений_модуля).
    """
    result = await run_blocking(token, getattr(solver, method), *args, **kwargs)
    msgs = drain_solver_messages(solver, token)
    return result, msgs


def log_traceback(token: str, exc: BaseException) -> str:
    tb = "".join(
        traceback.format_exception(type(exc), exc, exc.__traceback__)
    )
    hub.add(token, "ERROR", "traceback", tb)
    return tb


# ---------------------------------------------------------------------------
# Ответы API
# ---------------------------------------------------------------------------


def ok_response(payload: dict, token: str) -> JSONResponse:
    data = dict(payload)
    data.setdefault("ok", True)
    data["log_entries"] = hub.get(token)
    resp = JSONResponse(content=data)
    resp.set_cookie(key="session_token", value=token, httponly=True, samesite="lax")
    return resp


def error_response(
    status_code: int,
    message: str,
    token: str,
    traceback_text: str = "",
    msg: str = "",
    extra: Optional[dict] = None,
) -> JSONResponse:
    data = {
        "ok": False,
        "error": message,
        "detail": message,
        # msg — текст, который вернул сам модуль yandex uchebnik
        # (например, ответ сервера при COOKIES_GENERATE_ERROR)
        "msg": msg,
        "traceback": traceback_text,
        "log_entries": hub.get(token),
        "logs": hub.format_lines(token),
    }
    if extra:
        data.update(extra)
    resp = JSONResponse(status_code=status_code, content=data)
    resp.set_cookie(key="session_token", value=token, httponly=True, samesite="lax")
    return resp


# ---------------------------------------------------------------------------
# Модели
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Роуты
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def serve_static_spa():
    return HTMLResponse(content=INDEX_HTML)


@app.get("/api/state")
async def api_get_state(
    request: Request, session_token: Optional[str] = Cookie(None)
):
    token = resolve_token(session_token, request)
    CURRENT_SESSION.set(token)
    state = load_state(token)
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
        "logs": hub.format_lines(token),
        "log_entries": hub.get(token),
    }


@app.get("/api/logs/stream")
async def api_logs_stream(
    request: Request, session_token: Optional[str] = Cookie(None)
):
    """Live-стрим логов (SSE)."""
    token = resolve_token(session_token, request)
    CURRENT_SESSION.set(token)
    loop = asyncio.get_running_loop()
    queue = hub.subscribe(token, loop)

    async def event_stream():
        try:
            backlog = hub.get(token)
            if backlog:
                yield "data: %s\n\n" % json.dumps(
                    {"type": "backlog", "entries": backlog}, ensure_ascii=False
                )
            while True:
                try:
                    entry = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    continue
                yield "data: %s\n\n" % json.dumps(
                    {"type": "entry", "entry": entry}, ensure_ascii=False
                )
        except asyncio.CancelledError:  # pragma: no cover
            raise
        finally:
            hub.unsubscribe(token, queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/logs")
async def api_get_logs(
    request: Request, session_token: Optional[str] = Cookie(None)
):
    token = resolve_token(session_token, request)
    CURRENT_SESSION.set(token)
    return {"logs": hub.format_lines(token), "log_entries": hub.get(token)}


@app.post("/api/login")
async def api_login(
    payload: LoginPayload,
    request: Request,
    session_token: Optional[str] = Cookie(None),
):
    global ACTIVE_TOKEN
    # Не создаём «одноразовый» токен: если cookies не сохраняются (iframe,
    # webview, приватный режим), такой токен был бы недостижим и все
    # последующие запросы получали бы 401.
    token = resolve_token(session_token, request)
    ACTIVE_TOKEN = token
    CURRENT_SESSION.set(token)

    creds = {"login": payload.login.strip(), "code": payload.code.strip()}
    solver = YandexUchebnik(None, None, creds)
    hub.add(
        token,
        "INFO",
        "webui",
        "Авторизация: логин=%s, код школы=%s" % (creds["login"], creds["code"]),
    )

    try:
        (st, name), msgs = await call_solver(token, solver, "get_name")
    except Exception as exc:
        tb = log_traceback(token, exc)
        return error_response(
            500, "Ошибка авторизации: %s" % exc, token, traceback_text=tb
        )

    if st != Status.OK:
        message = "Ошибка авторизации: %s" % st.name
        yandex_msg = str(getattr(solver, "last_msg", "") or "")
        hub.add(token, "ERROR", "yandex", "%s" % message)
        if yandex_msg:
            hub.add(token, "ERROR", "yandex", "Ответ Yandex Uchebnik: %s" % yandex_msg)
        return error_response(
            401,
            message,
            token,
            msg=yandex_msg,
            extra={"status": st.name, "yandex_messages": msgs},
        )

    state = load_state(token)
    state["creds"] = creds
    state["user_name"] = name
    save_state(token, state)
    SOLVER_CACHE[token] = solver
    hub.add(token, "INFO", "webui", "> Авторизован: %s" % name)
    # token возвращаем и телом ответа: фронтенд сохранит его и будет слать
    # заголовком X-Session-Token, если cookies не работают
    return ok_response({"status": "ok", "user_name": name, "token": token}, token)


@app.post("/api/logout")
async def api_logout(
    request: Request,
    response: Response,
    session_token: Optional[str] = Cookie(None),
):
    global ACTIVE_TOKEN
    token = resolve_token(session_token, request)
    SOLVER_CACHE.pop(token, None)
    path = get_session_file(token)
    if os.path.exists(path):
        os.remove(path)
    hub.clear(token)
    if ACTIVE_TOKEN == token:
        ACTIVE_TOKEN = GLOBAL_SESSION
    response.delete_cookie("session_token")
    return {"status": "ok"}


@app.get("/api/courses")
async def api_get_courses(
    request: Request, session_token: Optional[str] = Cookie(None)
):
    token = resolve_token(session_token, request)
    CURRENT_SESSION.set(token)
    state = load_state(token)
    solver = get_solver(token, state)
    if not solver:
        return error_response(401, "Сессия не найдена", token)

    try:
        (st, courses, msg), _msgs = await call_solver(token, solver, "get_courses")
    except Exception as exc:
        tb = log_traceback(token, exc)
        return error_response(
            500, "Ошибка получения курсов: %s" % exc, token, traceback_text=tb
        )

    if st != Status.OK:
        hub.add(token, "ERROR", "yandex", "Не удалось получить курсы: %s" % msg)
        return error_response(
            500,
            "Не удалось получить курсы: %s" % msg,
            token,
            msg=str(msg),
            extra={"status": st.name},
        )

    state["courses"] = courses
    save_state(token, state)
    return ok_response({"courses": courses}, token)


@app.post("/api/select-course")
async def api_select_course(
    payload: CoursePayload,
    request: Request,
    session_token: Optional[str] = Cookie(None),
):
    token = resolve_token(session_token, request)
    CURRENT_SESSION.set(token)
    state = load_state(token)
    state["cid"] = payload.cid
    state["aid"] = None
    state["problems"] = []
    state["problem_statuses"] = {}
    save_state(token, state)

    solver = get_solver(token, state)
    try:
        (st, assignments, msg), _msgs = await call_solver(
            token, solver, "get_lessons", payload.cid
        )
    except Exception as exc:
        tb = log_traceback(token, exc)
        return error_response(
            500, "Ошибка получения уроков: %s" % exc, token, traceback_text=tb
        )

    if st != Status.OK:
        hub.add(token, "ERROR", "yandex", "Не удалось получить уроки: %s" % msg)
        return error_response(
            500,
            "Не удалось получить уроки: %s" % msg,
            token,
            msg=str(msg),
            extra={"status": st.name},
        )

    state["assignments"] = assignments
    save_state(token, state)
    return ok_response({"status": "ok", "assignments": assignments}, token)


@app.post("/api/select-assignment")
async def api_select_assignment(
    payload: AssignmentPayload,
    request: Request,
    session_token: Optional[str] = Cookie(None),
):
    token = resolve_token(session_token, request)
    CURRENT_SESSION.set(token)
    state = load_state(token)
    state["aid"] = payload.aid
    solver = get_solver(token, state)
    if solver is not None:
        solver.aid = payload.aid
        solver.data = None

    try:
        (st, problems), _msgs = await call_solver(token, solver, "get_problems")
    except Exception as exc:
        tb = log_traceback(token, exc)
        return error_response(
            500, "Ошибка загрузки задач: %s" % exc, token, traceback_text=tb
        )

    if st != Status.OK:
        message = "Ошибка загрузки задач: %s" % st.name
        yandex_msg = str(getattr(solver, "last_msg", "") or "")
        hub.add(token, "ERROR", "yandex", message)
        if yandex_msg:
            hub.add(token, "ERROR", "yandex", "Ответ Yandex Uchebnik: %s" % yandex_msg)
        return error_response(
            500, message, token, msg=yandex_msg, extra={"status": st.name}
        )

    state["problems"] = problems
    state["problem_statuses"] = {str(i): "idle" for i in range(1, len(problems) + 1)}
    state["current_idx"] = 1
    save_state(token, state)
    return ok_response(
        {
            "status": "ok",
            "problems_count": len(problems),
            "problem_statuses": state["problem_statuses"],
        },
        token,
    )


@app.get("/api/problem/{idx}")
async def api_get_problem(
    idx: int, request: Request, session_token: Optional[str] = Cookie(None)
):
    token = resolve_token(session_token, request)
    CURRENT_SESSION.set(token)
    state = load_state(token)
    solver = get_solver(token, state)
    if not solver or not state.get("aid"):
        return error_response(400, "Урок не выбран", token)

    try:
        (st_disp, p_type, raw_disp), _msgs = await call_solver(
            token, solver, "handle_problem_display_solution", idx
        )
    except Exception as exc:
        tb = log_traceback(token, exc)
        return error_response(
            500, "Ошибка загрузки задачи #%s: %s" % (idx, exc), token, traceback_text=tb
        )

    if st_disp != Status.OK:
        message = "Ошибка загрузки задачи #%s: %s" % (idx, st_disp.name)
        yandex_msg = str(raw_disp or getattr(solver, "last_msg", "") or "")
        hub.add(token, "ERROR", "yandex", message)
        if yandex_msg:
            hub.add(token, "ERROR", "yandex", "Ответ Yandex Uchebnik: %s" % yandex_msg)
        return error_response(
            500, message, token, msg=yandex_msg, extra={"status": st_disp.name}
        )

    content = raw_disp
    if content.startswith("OK\n"):
        content = content[3:]
    if p_type == "practice":
        content = format_marker_display(content)
    return ok_response({"idx": idx, "type": p_type, "content": content}, token)


@app.post("/api/solve-one")
async def api_solve_one(
    payload: SolveOnePayload,
    request: Request,
    session_token: Optional[str] = Cookie(None),
):
    token = resolve_token(session_token, request)
    CURRENT_SESSION.set(token)
    state = load_state(token)
    solver = get_solver(token, state)
    if not solver:
        return error_response(401, "Сессия не найдена", token)

    idx = payload.idx
    hub.add(
        token,
        "INFO",
        "webui",
        "▶ Задача #%s: получение решения (fake_timedelta=%ss)"
        % (idx, payload.fake_timedelta),
    )
    seq_start = hub.last_seq(token)

    try:
        (st_disp, p_type, disp), _msgs = await call_solver(
            token, solver, "handle_problem_display_solution", idx
        )
    except Exception as exc:
        tb = log_traceback(token, exc)
        return error_response(
            500, "Ошибка получения задачи #%s: %s" % (idx, exc), token, traceback_text=tb
        )

    if st_disp != Status.OK:
        message = "Не удалось получить задачу #%s: %s" % (idx, st_disp.name)
        yandex_msg = str(disp or getattr(solver, "last_msg", "") or "")
        hub.add(token, "ERROR", "yandex", message)
        if yandex_msg:
            hub.add(token, "ERROR", "yandex", "Ответ Yandex Uchebnik: %s" % yandex_msg)
        return error_response(
            500, message, token, msg=yandex_msg, extra={"status": st_disp.name}
        )

    try:
        if p_type == "theory":
            st_res, _msgs = await call_solver(
                token, solver, "handle_problem_solution", idx
            )
        else:
            st_res, _msgs = await call_solver(
                token,
                solver,
                "handle_problem_solution",
                idx,
                fake_timedelta=payload.fake_timedelta,
            )
    except Exception as exc:
        tb = log_traceback(token, exc)
        return error_response(
            500, "Ошибка отправки задачи #%s: %s" % (idx, exc), token, traceback_text=tb
        )

    st_code = st_res[0] if isinstance(st_res, tuple) else st_res
    raw_msg = st_res[2] if isinstance(st_res, tuple) and len(st_res) > 2 else ""

    statuses = state.get("problem_statuses", {})
    if st_code == Status.OK:
        statuses[str(idx)] = "ok"
    elif st_code in (
        Status.WRONG_PROBLEM_TYPE,
        Status.SOLUTION_FAILURE_UNKNOWN_PROBLEM_TYPE,
    ):
        statuses[str(idx)] = "unsupported"
    else:
        statuses[str(idx)] = "fail"

    solution_text = (disp or "").strip()
    if solution_text.startswith("OK\n"):
        solution_text = solution_text[3:]

    log_blocks = [
        "============================================================",
        "Задача #%s [Тип: %s] | Fake TimeDelta: %ss"
        % (idx, p_type, payload.fake_timedelta),
        "--- ГОТОВОЕ РЕШЕНИЕ / КОД / ОТВЕТ ---",
        solution_text if solution_text else "[Пусто]",
        "--- РЕЗУЛЬТАТ ОТПРАВКИ ---",
        "Статус решения : %s" % st_code.name,
        "Ответ сервера  : %s" % (raw_msg.strip() if raw_msg else "Успешно"),
        "============================================================",
    ]
    full_log = "\n".join(log_blocks)

    # всё, что напечатали модули main.* во время операции (с возможным traceback)
    captured = hub.entries_since(token, seq_start)
    captured_text = "\n".join(format_entry(e) for e in captured)

    hub.add(
        token,
        "INFO" if st_code == Status.OK else "ERROR",
        "solver",
        full_log,
    )

    state["logs"] = hub.format_lines(token)
    state["problem_statuses"] = statuses
    save_state(token, state)

    return ok_response(
        {
            "status": statuses[str(idx)],
            "type": p_type,
            "st_name": st_code.name,
            # msg — что ответил сервер Yandex Uchebnik на отправку решения
            "msg": str(raw_msg or ""),
            "log": full_log,
            "captured": captured_text,
            "captured_entries": captured,
        },
        token,
    )


@app.post("/api/append-log")
async def api_append_log(
    payload: LogAppendPayload,
    request: Request,
    session_token: Optional[str] = Cookie(None),
):
    token = resolve_token(session_token, request)
    CURRENT_SESSION.set(token)
    hub.add(token, "INFO", "webui", payload.log)
    return {"status": "ok"}


@app.post("/api/update-status")
async def api_update_status(
    data: dict, request: Request, session_token: Optional[str] = Cookie(None)
):
    token = resolve_token(session_token, request)
    CURRENT_SESSION.set(token)
    st = load_state(token)
    idx = str(data.get("idx"))
    status = data.get("status")
    if idx and status:
        st["problem_statuses"][idx] = status
        save_state(token, st)
    return {"status": "ok"}


@app.post("/api/clear-logs")
async def api_clear_logs(
    request: Request, session_token: Optional[str] = Cookie(None)
):
    token = resolve_token(session_token, request)
    CURRENT_SESSION.set(token)
    hub.clear(token)
    st = load_state(token)
    st["logs"] = []
    save_state(token, st)
    return {"status": "ok"}


def main():
    print("Запуск авто-решателя: http://0.0.0.0:8000")
    print("Каталог сессий: %s" % SESSIONS_DIR)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info", access_log=False)


if __name__ == "__main__":
    main()
