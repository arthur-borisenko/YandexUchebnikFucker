import inspect
from typing import Dict, List, Type

from main.solver.base import BaseProblemSolver
from main.solver.coding import CodingProblemSolver
from main.solver.marker import MarkerProblemSolver
from main.solver.theory import TheoryProblemSolver
from main.solver.web import WebProblemSolver
SOLVERS = [CodingProblemSolver, MarkerProblemSolver, TheoryProblemSolver, WebProblemSolver]

def get_problem_solvers() -> Dict[str, List[Type[BaseProblemSolver]]]:
    solvers: Dict[str, List[Type[BaseProblemSolver]]] = {}
    for cls in BaseProblemSolver.__subclasses__():
        if not inspect.isabstract(cls):
            supported_types = getattr(cls, "SUPPORTED_PROBLEM_TYPES", [])
            for problem_type in supported_types:
                # noinspection bad-argument-type
                solvers.setdefault(problem_type, []).append(cls)

    return solvers