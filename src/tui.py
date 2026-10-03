import re
import sys

from main.uchebnik import YandexUchebnik
from main.util import Status


def inputyesno(prompt):
    yes = {"y", "yes", "д", "да"}
    no = {"n", "no", "н", "нет"}
    a = input(f"{prompt} [Y/N]: ").lower()
    while a not in yes and a not in no:
        a = input(f"{prompt} [Y/N]: ").lower()
    return a in yes


def inputint(prompt, mi=None, ma=None):
    if mi is None or ma is None:
        a = input(f"{prompt} (number): ").lower()
        while not a.isdigit():
            a = input(f"{prompt} (number): ").lower()
    else:
        if mi > ma:
            raise ValueError("maximal value must be larger than minimal value")
        a = input(f"{prompt} ({mi}-{ma}): ")
        while not (a.isdigit() and int(a) >= mi and int(a) <= ma):
            a = input(f"{prompt} ({mi}-{ma}): ")
        return int(a)


def print_table(s):
    if "|" not in s:
        print(s)
        return
    rows = []
    for line in s.strip().split("\n"):
        if "|" in line:
            parts = [p.strip(" `") for p in line.split("|") if p.strip()]
            if parts:
                rows.append(parts)
    if not rows:
        print(s)
        return

    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    sep = "┼".join("─" * (w + 2) for w in widths)
    print("┌" + "┬".join("─" * (w + 2) for w in widths) + "┐")
    for i, row in enumerate(rows):
        print(
            "│ " + " │ ".join(val.ljust(widths[j]) for j, val in enumerate(row)) + " │"
        )
        if i < len(rows) - 1:
            print("├" + sep + "┤")
    print("└" + "┴".join("─" * (w + 2) for w in widths) + "┘")


def print_marker_solution(
    s: YandexUchebnik, problem_idx: int, text: str, send_by_default=False
):
    SEP = "\t\n\r"
    tx = text.split(SEP)
    print(tx[0])
    an = tx[1:]
    for aa in an:
        print_table(aa)
    if send_by_default or inputyesno(f"Send solution for {problem_idx}"):
        fake_timedelta = (
            -1 if send_by_default else inputint("Fake timedelta", 0, 100000)
        )
        a = s.handle_problem_solution(problem_idx, fake_timedelta)
        st, p_type, msg = a
        print(
            f"Solution status: {st}, Response: {msg}",
            file=sys.stdout if st == Status.OK else sys.stderr,
        )
        if st == Status.SOLUTION_FAILURE_ALREADY_SOLVED_OR_NO_ATTEMPTS:
            print(
                "Failed to send solution. Problem may be already solved or all attempts exhausted.",
                file=sys.stderr,
            )


def print_coding_solution(
    s: YandexUchebnik, problem_idx: int, disp, send_by_default=False
):
    print(f"\n--- AUTHOR SOLUTION ---\n{disp}\n--- END ---")
    if send_by_default or inputyesno(f"Send solution for {problem_idx}"):
        fake_timedelta = (
            -1 if send_by_default else inputint("Fake timedelta", 0, 100000)
        )
        st, p_type, msg = s.handle_problem_solution(problem_idx, fake_timedelta)
        print(
            f"Solution status: {st}, Response: {msg}",
            file=sys.stdout if st == Status.OK else sys.stderr,
        )
        if st == Status.SOLUTION_FAILURE_ALREADY_SOLVED_OR_NO_ATTEMPTS:
            print(
                "Failed to send solution. Problem may be already solved or all attempts exhausted.",
                file=sys.stderr,
            )


def print_problem(s: YandexUchebnik, problem_idx: int, send_by_default=False):
    st, p_type, disp = s.handle_problem_display_solution(problem_idx)
    print(f"\n{'=' * 20} Problem {problem_idx} ({p_type}) {'=' * 20}")
    if st != Status.OK:
        print(f"Error: {st.name}")
    elif p_type == "theory":
        print(disp)
        print("Marking as complete....")
        s.handle_problem_solution(problem_idx)
    elif p_type == "practice":
        print_marker_solution(s, problem_idx, disp, send_by_default)
    elif p_type == "coding":
        print_coding_solution(s, problem_idx, send_by_default)
    else:
        print(disp)
        if send_by_default or inputyesno(f"Send solution for {problem_idx}"):
            fake_timedelta = (
                -1 if send_by_default else inputint("Fake timedelta", 0, 100000)
            )
            st, pt, msg = s.handle_problem_solution(problem_idx, fake_timedelta)
            print(st, msg, file=sys.stdout if st == Status.OK else sys.stderr)


def load_ids_fallback(cid):
    a = "foo"
    while not "education.yandex.ru" in a and not a.isdigit():
        a = input(
            f"Enter {'course' if cid is not None else 'assignment'} ID or task link: "
        )
        if not "education.yandex.ru" in a and not a.isdigit():
            print("Must be yandex uchebnik link or integer")
    if cid is None:
        cid = a
        aid = inputint("Assignment id:")
    else:
        aid = a
    if "education.yandex.ru" in a:
        cid = re.search(r"courses/(\d+)", a).group(1)
        aid = re.search(r"assignments/(\d+)", a).group(1)
    return Status.OK, cid, aid


def ask_course_and_assignment(solver: YandexUchebnik):
    st, courses, msg = solver.get_courses()
    print(msg)
    if st != Status.OK:
        return st, None, None
    print(f"Select course:")
    for i, c in enumerate(courses):
        print(f"{i + 1}:", "; ".join(map(lambda x: "=".join(map(str, x)), c.items())))
    n = -1
    valid = False
    while not valid:
        n = int(input(f"Enter course number(1-{len(courses)}): "))
        if n > len(courses):
            print(f"Course number out of range({n} > {len(courses)}).")
        elif n < 1:
            print("Course number out of range(must be at least 1).")
        else:
            valid = True
    cid = courses[n - 1]["id"]
    st, assignments, msg = solver.get_lessons(cid)
    print(msg)
    if st != Status.OK:
        return st, cid, None
    print(f"Select assignment:")
    for i, a in enumerate(assignments):
        print(f"{i + 1}:", "; ".join(map(lambda x: "=".join(map(str, x)), a.items())))
    n = -1
    valid = False
    while not valid:
        n = int(input(f"Enter assignment number(1-{len(assignments)}): "))
        if n > len(assignments):
            print(f"Assignment number out of range({n} > {len(assignments)}).")
        elif n < 1:
            print("Assignment number out of range(must be at least 1).")
        else:
            valid = True
    return st, cid, assignments[n - 1]["id"]


def main():
    creds = None
    creds = {"login": input("Login: "), "code": input("School Code: ")}
    solver = YandexUchebnik(None, None, creds)
    st, name = solver.get_name()
    if st != Status.OK:
        print("Auth failed.")
        return
    print(f"User: {name}")
    st, cid, aid = ask_course_and_assignment(solver)
    if st != Status.OK:
        print(f"Error: {st.name}")
        print("Falling back to manual selection.")
        st, cid, aid = load_ids_fallback(cid)
    solver.cid = cid
    solver.aid = aid
    cmd = input("Problem number or '*' for all: ")
    if cmd == "*":
        st, problems = solver.get_problems()
        send_by_default = input(
            "Send problems by default? (y/n): "
        ).lower().strip() in {"y", "yes", "д", "да"}
        for i in range(1, len(problems) + 1):
            print_problem(solver, i, send_by_default)
    else:
        print_problem(solver, int(cmd))
    print("Done.")


if __name__ == "__main__":
    main()
