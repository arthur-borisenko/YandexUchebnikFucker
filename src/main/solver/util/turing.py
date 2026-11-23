"""Bounded discovery and safe answer mapping for public Turing lesson variants.

No authenticated actions are performed here. A source must be uniquely identified by
content/resources; a position in a public template is never sufficient evidence.
"""
from __future__ import annotations

import html
import logging
import re
import unicodedata
from difflib import SequenceMatcher
from functools import lru_cache

LOG = logging.getLogger(__name__)


class TuringResolutionError(Exception):
    """No unique, validated answer could be resolved; the caller must NOT submit."""


class LessonRepository:
    def __init__(self, session, max_requests: int = 10):
        self.session = session
        self.max_requests = max_requests
        self.request_count = 0
        self.cache: dict[int, dict] = {}

    def fetch(self, lesson_id: int) -> dict:
        lesson_id = int(lesson_id)
        if lesson_id in self.cache:
            return self.cache[lesson_id]
        if self.request_count >= self.max_requests:
            raise TuringResolutionError("Лимит GET-запросов Turing API исчерпан")
        self.request_count += 1
        url = f"https://education.yandex.ru/turing-api/lessons/{lesson_id}"
        try:
            resp = self.session.get(url, headers={"Accept": "application/json"}, timeout=15)
            if resp.status_code // 100 != 2:
                raise TuringResolutionError(f"Turing API: HTTP {resp.status_code} для урока {lesson_id}")
            data = resp.json()
            if not isinstance(data, dict) or not isinstance(data.get("problems"), list):
                raise TuringResolutionError(f"Неверный формат Turing API для урока {lesson_id}")
        except TuringResolutionError:
            raise
        except Exception as exc:
            raise TuringResolutionError(f"Не удалось получить урок {lesson_id}: {type(exc).__name__}") from exc
        self.cache[lesson_id] = data
        return data


class LessonFamilyDiscovery:
    """Probe neighboring lesson IDs; stop at the first foreign lesson on each side."""

    def __init__(self, repository: LessonRepository):
        self.repository = repository
        self._family: list[dict] | None = None

    @staticmethod
    def _norm(value) -> str:
        value = unicodedata.normalize("NFKC", html.unescape(str(value or "")))
        value = "".join(c for c in value if unicodedata.category(c) != "Cf")
        return re.sub(r"\s+", " ", value).strip().casefold()

    @classmethod
    def _stem(cls, value) -> str:
        return re.sub(r"\s*\.?\s*вариант\s*\d+\s*$", "", cls._norm(value)).strip()

    @classmethod
    def _related(cls, a: dict, b: dict) -> bool:
        pa, pb = a.get("problems", []), b.get("problems", [])
        return (a.get("owner") == b.get("owner") and a.get("subject") is not None
                and a.get("subject") == b.get("subject") and len(pa) == len(pb) and len(pa) > 2
                and cls._stem(a.get("name")) == cls._stem(b.get("name"))
                and pa[0].get("problem", {}).get("id") == pb[0].get("problem", {}).get("id")
                and pa[-1].get("problem", {}).get("id") == pb[-1].get("problem", {}).get("id"))

    def discover(self, active_lesson_id: int, slug: str | None) -> list[dict]:
        if self._family is not None:
            return self._family
        active = self.repository.fetch(active_lesson_id)
        family = {int(active["id"]): active}
        match = re.fullmatch(r"lesson-meta-(\d+)", str(slug or ""))
        if not match:
            self._family = list(family.values())
            return self._family
        anchor_id = int(match.group(1))
        try:
            anchor = self.repository.fetch(anchor_id)
        except TuringResolutionError as exc:
            LOG.warning("Не удалось получить исходный урок: %s", exc)
            self._family = list(family.values())
            return self._family
        if not self._related(active, anchor):
            LOG.warning("Исходный урок из meta.slug не похож на активный; поиск вариантов остановлен")
            self._family = list(family.values())
            return self._family
        family[anchor_id] = anchor
        for direction in (1, -1):
            step = 1
            while self.repository.request_count < self.repository.max_requests:
                candidate_id = anchor_id + direction * step
                try:
                    candidate = self.repository.fetch(candidate_id)
                except TuringResolutionError:
                    break
                if not self._related(anchor, candidate):
                    break
                family[candidate_id] = candidate
                step += 1
        self._family = list(family.values())
        return self._family


class ProblemMatcher:
    """Find an individual problem by marker structure and content, never by index alone."""

    @staticmethod
    def _markers(problem: dict) -> list[dict]:
        return [e["content"] for e in problem.get("markup", {}).get("layout", [])
                if e.get("kind") == "marker"]

    @staticmethod
    def _rid(obj: dict | None):
        return (obj or {}).get("resource_id", (obj or {}).get("resourceId"))

    @classmethod
    def _resources(cls, problem: dict) -> tuple:
        ids = []
        for marker in cls._markers(problem):
            options = marker.get("options", {})
            for key in ("main_image", "mainImage"):
                if key in options:
                    ids.append(cls._rid(options[key]))
            for item in options.get("choices", []):
                if isinstance(item, dict):
                    rid = cls._rid(item)
                    if rid is not None:
                        ids.append(rid)
            for key in ("resource_id", "resourceId", "image_file", "imageFile"):
                if options.get(key) is not None:
                    ids.append(options[key])
        # Text can contain {resource:N} (e.g. a comic instead of a marker image).
        for element in problem.get("markup", {}).get("layout", []):
            ids.extend(int(n) for n in re.findall(r"\{resource:(\d+)}", str(element.get("content", {}).get("text", ""))))
        return tuple(sorted(str(i) for i in ids if i is not None))

    @classmethod
    def _text(cls, problem: dict) -> str:
        chunks = []
        for element in problem.get("markup", {}).get("layout", []):
            content = element.get("content", {})
            if element.get("kind") == "text":
                chunks.append(content.get("text", ""))
            elif element.get("kind") == "marker":
                chunks.append(content.get("options", {}).get("text", ""))
        return LessonFamilyDiscovery._norm(" ".join(chunks))

    @classmethod
    def _compatible(cls, student: dict, reference: dict) -> bool:
        sm, rm = cls._markers(student), cls._markers(reference)
        if [(str(m.get("id")), m.get("type")) for m in sm] != [
            (str(m.get("id")), m.get("type")) for m in rm]:
            return False
        sr, rr = cls._resources(student), cls._resources(reference)
        # A concrete marker's resources are strong evidence. Shared background art is ignored.
        return not (sr and rr and sr != rr)

    def match(self, student: dict, family: list[dict], position: int) -> dict:
        candidates = {}
        for lesson in family:
            for index, item in enumerate(lesson.get("problems", []), 1):
                ref = item.get("problem") or {}
                if not self._compatible(student, ref):
                    continue
                # The public active template and the original lesson often contain the same problem.
                candidates.setdefault((str(ref.get("id")), self._resources(ref)), (ref, index))
        if not candidates:
            raise TuringResolutionError("Нет задачи с совместимыми маркерами и ресурсами")
        sr = self._resources(student)
        sp = str(student.get("id"))
        text = self._text(student)
        scored = []
        for (ref_id, rr), (ref, index) in candidates.items():
            ref_text = self._text(ref)
            similarity = SequenceMatcher(None, text, ref_text).ratio() if text and ref_text else 0
            # Exclude far-away positions by default, but do not accept the matching position alone.
            if index != position and ref_id != sp and not (sr and rr and sr == rr):
                continue
            if ref_id == sp and similarity < 0.60 and not (sr and sr == rr):
                continue
            if not sr and ref_id != sp and similarity < 0.80:
                continue
            score = similarity + (3 if ref_id == sp else 0) + (2 if sr and rr and sr == rr else 0)
            scored.append((score, similarity, ref_id, ref))
        scored.sort(key=lambda x: x[0], reverse=True)
        if not scored or (len(scored) > 1 and scored[0][0] - scored[1][0] < 0.08):
            raise TuringResolutionError("Задача не найдена однозначно по содержимому")
        LOG.debug("Сопоставлена задача %s с источником %s (similarity=%.3f)",
                  sp, scored[0][2], scored[0][1])
        return scored[0][3]


class AnswerRemapper:
    """Convert reference answers to the assigned problem's marker options."""

    @staticmethod
    def _key(value):
        # Unicode minus and typographic hyphens are presentation differences here;
        # do NOT drop the operator ("-" and "|" must remain different options).
        return LessonFamilyDiscovery._norm(value).translate(str.maketrans({
            "−": "-", "‐": "-", "‑": "-",
        }))

    @staticmethod
    def _operators(text: str) -> tuple[str, ...]:
        # Do not confuse search operators while accepting changed word endings.
        # A hyphen inside a word (веб-сервис) is not a search subtraction operator.
        return tuple(re.findall(r"[&|+]|(?<!\w)-", text))

    def _choice_map(self, source: list, target: list) -> dict[int, int]:
        """Find a single one-to-one mapping of the WHOLE option list, not one word.

        Exact matches are anchors; modified endings can use an unambiguous global
        assignment. Reject unrelated/ambiguous changes rather than guessing by index.
        """
        if (not isinstance(source, list) or not isinstance(target, list)
                or not source or len(source) != len(target)
                or any(not isinstance(s, str) for s in source + target)):
            raise TuringResolutionError("Несовместимые списки вариантов")
        a, b = [self._key(s) for s in source], [self._key(s) for s in target]
        if a == b:
            return {i: i for i in range(len(a))}
        if len(set(a)) != len(a) or len(set(b)) != len(b):
            raise TuringResolutionError("Повторяющиеся варианты после перестановки неоднозначны")
        mapping = {i: b.index(text) for i, text in enumerate(a) if text in b}
        remaining_a = [i for i in range(len(a)) if i not in mapping]
        used = set(mapping.values())
        remaining_b = [i for i in range(len(b)) if i not in used]
        if len(remaining_a) != len(remaining_b):
            raise TuringResolutionError("Не удалось сопоставить варианты взаимно-однозначно")
        if not remaining_a:
            return mapping
        if len(remaining_a) > 10:
            raise TuringResolutionError("Слишком много изменённых вариантов для безопасной сверки")
        scores = [[SequenceMatcher(None, a[i], b[j]).ratio()
                   if self._operators(a[i]) == self._operators(b[j]) else 0.0
                   for j in remaining_b] for i in remaining_a]
        n = len(remaining_a)

        @lru_cache(None)
        def best_two(row, used_mask):
            if row == n:
                return ((0.0, ()),)
            possibilities = []
            for col in range(n):
                if used_mask & (1 << col) or scores[row][col] < 0.72:
                    continue
                for suffix_score, suffix_path in best_two(row + 1, used_mask | (1 << col)):
                    possibilities.append((scores[row][col] + suffix_score, (col,) + suffix_path))
            possibilities.sort(key=lambda candidate: candidate[0], reverse=True)
            return tuple(possibilities[:2])

        solutions = best_two(0, 0)
        if not solutions or (len(solutions) > 1 and solutions[0][0] - solutions[1][0] < 0.08):
            raise TuringResolutionError("Нет однозначного соответствия списков вариантов")
        for row, col in enumerate(solutions[0][1]):
            mapping[remaining_a[row]] = remaining_b[col]
        LOG.debug("Сопоставлены варианты целиком: %s", mapping)
        return mapping

    def _choice_index(self, value, source: list, target: list) -> int:
        if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value < len(source):
            raise TuringResolutionError("Некорректный индекс варианта в эталоне")
        return self._choice_map(source, target)[value]

    def _inline(self, ans: dict, src: dict, dst: dict) -> dict:
        if not isinstance(ans, dict):
            raise TuringResolutionError("Неверный формат inline-ответа")
        result = {}
        for field_id, value in ans.items():
            rf, sf = src.get("inputs", {}).get(str(field_id)), dst.get("inputs", {}).get(str(field_id))
            if not rf or not sf or rf.get("type") != sf.get("type"):
                raise TuringResolutionError(f"Отсутствует inline-поле {field_id}")
            if rf["type"] == "choice":
                result[str(field_id)] = self._choice_index(value,
                    rf.get("options", {}).get("choices", []), sf.get("options", {}).get("choices", []))
            else:
                result[str(field_id)] = value
        return result

    def _macaroni(self, ans: list, src: dict, dst: dict) -> list:
        if not isinstance(ans, list) or not ans:
            raise TuringResolutionError("Неверный формат macaroni-ответа")
        alternatives = []
        for pairs in ans:
            if not isinstance(pairs, list):
                raise TuringResolutionError("Неверная структура пар macaroni")
            remapped = []
            for pair in pairs:
                if not isinstance(pair, list) or len(pair) != 2:
                    raise TuringResolutionError("Неверная пара macaroni")
                remapped.append([self._choice_index(pair[side],
                    src.get(side_name, {}).get("choices", []), dst.get(side_name, {}).get("choices", []))
                    for side, side_name in enumerate(("left", "right"))])
            alternatives.append(remapped)
        return alternatives

    def _dragimage(self, ans: dict, src: dict, dst: dict) -> dict:
        if not isinstance(ans, dict):
            raise TuringResolutionError("Неверный формат dragimage-ответа")
        src_fields = {str(f["id"]) for f in src.get("fields", [])}
        dst_fields = {str(f["id"]) for f in dst.get("fields", [])}
        if src_fields != dst_fields or set(map(str, ans)) != src_fields:
            raise TuringResolutionError("Не совпадают поля dragimage")
        src_choices, dst_choices = src.get("choices", []), dst.get("choices", [])
        if not src_choices or not dst_choices:
            raise TuringResolutionError("Отсутствуют варианты dragimage")
        # `answers` refers to choice.id, NOT choice.value. In slots 12/21 the latter
        # repeats (1/10/100), whereas the answers contain six distinct choice IDs.
        dst_by_resource = {ProblemMatcher._rid(c): c.get("id") for c in dst_choices}
        src_by_id = {c.get("id"): ProblemMatcher._rid(c) for c in src_choices}
        if (None in dst_by_resource or len(dst_by_resource) != len(dst_choices)
                or None in src_by_id or len(src_by_id) != len(src_choices)
                or set(src_by_id.values()) != set(dst_by_resource)):
            raise TuringResolutionError("Неоднозначные ресурсы или ID вариантов dragimage")
        try:
            return {str(fid): dst_by_resource[src_by_id[choice_id]]
                    for fid, choice_id in ans.items()}
        except KeyError as exc:
            raise TuringResolutionError("ID варианта dragimage отсутствует в задаче") from exc

    def remap(self, student: dict, reference: dict) -> dict:
        ref_answers = reference.get("markup", {}).get("answers", {})
        if not isinstance(ref_answers, dict) or not ref_answers:
            raise TuringResolutionError("Эталон не содержит ответов")
        student_markers = {str(m["id"]): m for m in ProblemMatcher._markers(student)}
        ref_markers = {str(m["id"]): m for m in ProblemMatcher._markers(reference)}
        if set(student_markers) != set(ref_markers) or set(student_markers) != set(ref_answers):
            raise TuringResolutionError("Неполный набор ответов для маркеров")
        mapped = {}
        for mid, marker in student_markers.items():
            kind = marker["type"]
            src = ref_markers[mid].get("options", {})
            dst = marker.get("options", {})
            value = ref_answers[mid]
            if kind == "choice":
                if not isinstance(value, list):
                    raise TuringResolutionError("Неверный формат choice-ответа")
                mapped[mid] = [self._choice_index(i, src.get("choices", []), dst.get("choices", [])) for i in value]
            elif kind == "inline":
                mapped[mid] = self._inline(value, src, dst)
            elif kind == "macaroni":
                mapped[mid] = self._macaroni(value, src, dst)
            elif kind == "dragimage":
                mapped[mid] = self._dragimage(value, src, dst)
            elif kind in {"chooseimage", "coloring", "highlight"}:
                if ProblemMatcher._resources(student) != ProblemMatcher._resources(reference):
                    raise TuringResolutionError(f"Изменены ресурсы маркера {kind}")
                mapped[mid] = value
            else:
                raise TuringResolutionError(f"Маркер {kind} не поддерживается")
        return mapped


class TuringAnswerResolver:
    def __init__(self, session, max_requests: int = 10):
        self.repository = LessonRepository(session, max_requests)
        self.discovery = LessonFamilyDiscovery(self.repository)
        self.matcher = ProblemMatcher()
        self.remapper = AnswerRemapper()

    def resolve(self, student: dict, position: int, active_lesson_id: int, slug: str | None) -> dict:
        family = self.discovery.discover(active_lesson_id, slug)
        reference = self.matcher.match(student, family, position)
        return self.remapper.remap(student, reference)
