# 作者：LHF。
# 注释维护时间：2026-10-23。
# 文件作用：计算器参数、工具定义与受限表达式计算。

import ast
import operator
from decimal import Decimal, DecimalException, localcontext

from pydantic import Field

from app.schemas import StrictModel
from app.storage import Database
from app.tool.base import BaseTool, ToolError


class CalculatorArgs(StrictModel):
    expression: str = Field(min_length=1, max_length=256, description="括号、小数、+ - * / %；不支持代码")


class CalculatorTool(BaseTool[CalculatorArgs]):
    name = "calculator"
    description = "计算受限数学表达式，支持括号、小数、+ - * / %。"
    arguments = CalculatorArgs
    execution_mode = "parallel"

    async def execute(self, args: CalculatorArgs, db: Database, user_id: str, operation_id: str):
        # 作用：使用 AST 白名单和 Decimal 计算已校验的数学表达式。
        return _calculate(args.expression)


def _calculate(expression: str):
    # 作用：仅遍历允许的 AST 节点，不使用 eval；函数调用、属性访问等都会被拒绝。
    operations = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Mod: operator.mod,
    }
    try:
        tree = ast.parse(expression, mode="eval")
        if len(list(ast.walk(tree))) > 80:
            raise ToolError("expression_too_large", "表达式过于复杂")

        def evaluate(node):
            # 作用：递归计算允许的 AST 节点，并拒绝代码执行及超范围数值。
            if isinstance(node, ast.Expression):
                return evaluate(node.body)
            if isinstance(node, ast.Constant) and type(node.value) in (int, float):
                # 从原表达式读取数字构造 Decimal，避免先转浮点引入精度误差。
                value = Decimal(ast.get_source_segment(expression, node))
            elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
                value = evaluate(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
            elif isinstance(node, ast.BinOp) and type(node.op) in operations:
                value = operations[type(node.op)](evaluate(node.left), evaluate(node.right))
            else:
                raise ToolError("invalid_expression", "只支持数字、括号和 + - * / %")
            if not value.is_finite() or abs(value) > Decimal("1e100"):
                raise ToolError("numeric_limit", "计算结果超出允许范围")
            return value

        with localcontext() as context:
            context.prec = 28
            result = evaluate(tree)
        return {"expression": expression, "result": format(result.normalize(), "f"), "precision": 28}
    except (SyntaxError, DecimalException, ValueError, RecursionError) as error:
        raise ToolError("invalid_expression", "表达式非法、除零或超出计算范围") from error
