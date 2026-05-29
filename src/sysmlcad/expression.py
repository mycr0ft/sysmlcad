"""Symbolic expression tree for parametric CAD models.

Allows parameters to reference each other symbolically:
    length = Parameter("length", 100)
    width = length * 2  # BinaryOp(ParameterRef("length"), Literal(2), "mul")
"""

from __future__ import annotations

import math
from typing import Any, Union as TypingUnion

_NUMERIC_TYPES = (int, float)


def _to_expression(value: Any) -> "Expression":
    if isinstance(value, Expression):
        return value
    if isinstance(value, Parameter):
        return ParameterRef(value.name)
    return Literal(value)


class Expression:
    """Base class for all expression nodes."""

    def evaluate(self, context: dict[str, Any]) -> Any:
        raise NotImplementedError

    def _to_expr(self, other: Any) -> "Expression":
        return _to_expression(other)

    def __add__(self, other): return BinaryOp(self, self._to_expr(other), "add")
    def __radd__(self, other): return BinaryOp(self._to_expr(other), self, "add")
    def __sub__(self, other): return BinaryOp(self, self._to_expr(other), "sub")
    def __rsub__(self, other): return BinaryOp(self._to_expr(other), self, "sub")
    def __mul__(self, other): return BinaryOp(self, self._to_expr(other), "mul")
    def __rmul__(self, other): return BinaryOp(self._to_expr(other), self, "mul")
    def __truediv__(self, other): return BinaryOp(self, self._to_expr(other), "truediv")
    def __rtruediv__(self, other): return BinaryOp(self._to_expr(other), self, "truediv")
    def __pow__(self, other): return BinaryOp(self, self._to_expr(other), "pow")
    def __rpow__(self, other): return BinaryOp(self._to_expr(other), self, "pow")
    def __neg__(self): return UnaryOp(self, "neg")
    def __pos__(self): return UnaryOp(self, "pos")
    def __abs__(self): return FunctionCall("abs", self)

    def __eq__(self, other):
        if isinstance(other, Expression):
            return self.__class__ == other.__class__ and self.__dict__ == other.__dict__
        return NotImplemented

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    def __hash__(self):
        return hash((self.__class__.__name__, str(self.__dict__)))


class Literal(Expression):
    """A literal value: number, pint.Quantity, string, etc."""

    def __init__(self, value: Any):
        self.value = value

    def evaluate(self, context: dict[str, Any]) -> Any:
        return self.value

    def __repr__(self):
        return f"Literal({self.value!r})"


class ParameterRef(Expression):
    """Reference to a named parameter."""

    def __init__(self, name: str):
        self.name = name

    def evaluate(self, context: dict[str, Any]) -> Any:
        if self.name in context:
            return context[self.name]
        raise ValueError(f"Parameter '{self.name}' not found in evaluation context")

    def __repr__(self):
        return f"ParameterRef({self.name!r})"


class Parameter:
    """A named parameter declaration with a default value.

    Can be used in arithmetic expressions like a scalar:
        length = Parameter("length", 100)
        width = length * 2  # → BinaryOp(ParameterRef("length"), Literal(2), "mul")
    """

    def __init__(self, name: str, default: Any = None):
        self.name = name
        self.default = default

    def evaluate(self, context: dict[str, Any] | None = None) -> Any:
        if context is not None and self.name in context:
            return context[self.name]
        if isinstance(self.default, Expression):
            return self.default.evaluate(context or {})
        return self.default

    def _to_expr(self, other):
        return _to_expression(other)

    def __add__(self, other): return BinaryOp(ParameterRef(self.name), self._to_expr(other), "add")
    def __radd__(self, other): return BinaryOp(self._to_expr(other), ParameterRef(self.name), "add")
    def __sub__(self, other): return BinaryOp(ParameterRef(self.name), self._to_expr(other), "sub")
    def __rsub__(self, other): return BinaryOp(self._to_expr(other), ParameterRef(self.name), "sub")
    def __mul__(self, other): return BinaryOp(ParameterRef(self.name), self._to_expr(other), "mul")
    def __rmul__(self, other): return BinaryOp(self._to_expr(other), ParameterRef(self.name), "mul")
    def __truediv__(self, other): return BinaryOp(ParameterRef(self.name), self._to_expr(other), "truediv")
    def __rtruediv__(self, other): return BinaryOp(self._to_expr(other), ParameterRef(self.name), "truediv")
    def __pow__(self, other): return BinaryOp(ParameterRef(self.name), self._to_expr(other), "pow")
    def __neg__(self): return UnaryOp(ParameterRef(self.name), "neg")
    def __pos__(self): return UnaryOp(ParameterRef(self.name), "pos")

    def __repr__(self):
        return f"Parameter({self.name!r}, {self.default!r})"


class BinaryOp(Expression):
    """Binary operation between two expressions."""

    OPERATORS = {
        "add": lambda a, b: a + b,
        "sub": lambda a, b: a - b,
        "mul": lambda a, b: a * b,
        "truediv": lambda a, b: a / b,
        "pow": lambda a, b: a ** b,
    }

    def __init__(self, left: Expression, right: Expression, op: str):
        self.left = left
        self.right = right
        if op not in self.OPERATORS:
            raise ValueError(f"Unknown operator: {op}")
        self.op = op

    def evaluate(self, context: dict[str, Any]) -> Any:
        lv = self.left.evaluate(context)
        rv = self.right.evaluate(context)
        return self.OPERATORS[self.op](lv, rv)

    def __repr__(self):
        return f"BinaryOp({self.left!r}, {self.op!r}, {self.right!r})"


class UnaryOp(Expression):
    """Unary operation on an expression."""

    OPERATORS = {
        "neg": lambda a: -a,
        "pos": lambda a: +a,
    }

    def __init__(self, operand: Expression, op: str):
        self.operand = operand
        if op not in self.OPERATORS:
            raise ValueError(f"Unknown unary operator: {op}")
        self.op = op

    def evaluate(self, context: dict[str, Any]) -> Any:
        return self.OPERATORS[self.op](self.operand.evaluate(context))

    def __repr__(self):
        return f"UnaryOp({self.op!r}, {self.operand!r})"


class FunctionCall(Expression):
    """Function call: sin, cos, sqrt, abs, min, max, etc."""

    FUNCTIONS = {
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "sqrt": math.sqrt,
        "abs": abs,
        "floor": math.floor,
        "ceil": math.ceil,
        "round": round,
        "min": min,
        "max": max,
        "pow": pow,
        "log": math.log,
        "exp": math.exp,
        "radians": math.radians,
        "degrees": math.degrees,
        "atan2": math.atan2,
    }

    def __init__(self, name: str, *args: Expression):
        self.name = name
        self.args = [_to_expression(a) for a in args]
        if name not in self.FUNCTIONS:
            raise ValueError(f"Unknown function: {name}")

    def evaluate(self, context: dict[str, Any]) -> Any:
        evaled_args = [a.evaluate(context) for a in self.args]
        return self.FUNCTIONS[self.name](*evaled_args)

    def __repr__(self):
        return f"FunctionCall({self.name!r}, {self.args!r})"
