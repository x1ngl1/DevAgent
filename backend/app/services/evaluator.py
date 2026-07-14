"""Evaluator - 覆盖率解析 + 圈复杂度计算 + 测试结果评估"""

import re
import ast
import logging
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


def parse_coverage_report(xml_path: str) -> Dict[str, Any]:
    """从 coverage.xml 解析覆盖率数据

    Args:
        xml_path: coverage.xml 文件路径

    Returns:
        dict: {
            "line_rate": float,       # 行覆盖率 0.0-1.0
            "branch_rate": float,     # 分支覆盖率 0.0-1.0
            "covered_lines": int,     # 已覆盖行数
            "total_lines": int,       # 总行数
            "covered_branches": int,  # 已覆盖分支数
            "total_branches": int,    # 总分支数
            "missing_lines": list,    # 未覆盖行号列表
            "grade": str,             # 评级
        }
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # 取 <coverage> 标签属性
        line_rate = float(root.get("line-rate", "0"))
        branch_rate = float(root.get("branch-rate", "0"))
        lines_covered = int(root.get("lines-covered", "0"))
        lines_valid = int(root.get("lines-valid", "0"))
        branches_covered = int(root.get("branches-covered", "0"))
        branches_valid = int(root.get("branches-valid", "0"))

        # 收集未覆盖的行
        missing_lines = []
        for pkg in root.iter("package"):
            for cls in pkg.iter("class"):
                for lines_elem in cls.iter("lines"):
                    for line_elem in lines_elem.iter("line"):
                        hits = int(line_elem.get("hits", "0"))
                        if hits == 0:
                            missing_lines.append(int(line_elem.get("number", "0")))

        return {
            "line_rate": line_rate,
            "branch_rate": branch_rate,
            "covered_lines": lines_covered,
            "total_lines": lines_valid,
            "covered_branches": branches_covered,
            "total_branches": branches_valid,
            "missing_lines": sorted(missing_lines),
            "grade": _coverage_grade(line_rate * 100),
        }
    except FileNotFoundError:
        logger.warning(f"Coverage XML not found: {xml_path}")
        return {
            "line_rate": 0.0, "branch_rate": 0.0,
            "covered_lines": 0, "total_lines": 0,
            "covered_branches": 0, "total_branches": 0,
            "missing_lines": [], "grade": "unknown",
        }
    except ET.ParseError as e:
        logger.error(f"Coverage XML parse error: {e}")
        return {
            "line_rate": 0.0, "branch_rate": 0.0,
            "covered_lines": 0, "total_lines": 0,
            "covered_branches": 0, "total_branches": 0,
            "missing_lines": [], "grade": "unknown",
        }


def _coverage_grade(percent: float) -> str:
    """根据覆盖率百分比返回评级"""
    if percent >= 90:
        return "excellent"
    elif percent >= 80:
        return "good"
    elif percent >= 60:
        return "fair"
    elif percent >= 40:
        return "poor"
    else:
        return "insufficient"


def parse_coverage_from_pytest_output(logs: str) -> float:
    """从 pytest 命令行输出中解析覆盖率百分比

    Args:
        logs: pytest --cov 的输出文本

    Returns:
        float: 覆盖率百分比（如 83.0）
    """
    # 匹配 "TOTAL          12      2    83%"
    match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+(?:\.\d+)?)%", logs)
    if match:
        return float(match.group(1))
    # 尝试匹配 "TOTAL          12      2    83%   12      2    83%"
    match = re.search(r"TOTAL.*?(\d+(?:\.\d+)?)%", logs)
    if match:
        return float(match.group(1))
    return 0.0


def calculate_cyclomatic_complexity(code: str) -> Dict[str, int]:
    """使用 AST 分析计算每个函数的圈复杂度

    圈复杂度 M = 1 + (决策点数量)
    决策点包括: if, elif, while, for, and, or, except, with, assert

    Args:
        code: Python 源代码字符串

    Returns:
        dict: {function_name: complexity_score}
    """
    complexity_map = {}

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        logger.warning(f"Failed to parse code for complexity analysis: {e}")
        return {}

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            complexity = 1  # 基础复杂度
            for child in ast.walk(node):
                if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor)):
                    complexity += 1
                elif isinstance(child, ast.BoolOp):
                    # and/or 每个操作数增加一个决策点
                    complexity += len(child.values) - 1
                elif isinstance(child, ast.ExceptHandler):
                    complexity += 1
                elif isinstance(child, ast.With):
                    complexity += 1
                elif isinstance(child, ast.Assert):
                    complexity += 1
            complexity_map[node.name] = complexity

    return complexity_map


def summarize_test_results(
    passed: int, failed: int, skipped: int, error: int,
    coverage: float, complexity_map: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    """汇总测试执行结果

    Args:
        passed: 通过的测试数
        failed: 失败的测试数
        skipped: 跳过的测试数
        error: 错误的测试数
        coverage: 覆盖率百分比
        complexity_map: 圈复杂度映射

    Returns:
        dict: 汇总报告
    """
    total = passed + failed + skipped + error
    pass_rate = (passed / total * 100) if total > 0 else 0.0

    result = {
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "errors": error,
        "pass_rate": pass_rate,
        "coverage": coverage,
        "coverage_grade": _coverage_grade(coverage),
        "summary": "",
    }

    if total == 0:
        result["summary"] = "未执行任何测试"
    elif failed == 0 and error == 0:
        result["summary"] = f"全部通过，通过率 {pass_rate:.0f}%，覆盖率 {coverage:.1f}%"
    else:
        result["summary"] = f"通过 {passed}/{total}，通过率 {pass_rate:.0f}%，覆盖率 {coverage:.1f}%"

    if complexity_map:
        high_complexity = {k: v for k, v in complexity_map.items() if v > 10}
        if high_complexity:
            complex_list = [f"{name}(M={v})" for name, v in sorted(high_complexity.items(), key=lambda x: -x[1])]
            result["high_complexity_functions"] = complex_list
            result["summary"] += f" | 高复杂度函数: {', '.join(complex_list)}"

    return result


def pytest_output_parser(output: str) -> Dict[str, int]:
    """从 pytest 输出中解析测试计数

    Args:
        output: pytest 完整输出

    Returns:
        dict: {"passed": int, "failed": int, "skipped": int, "errors": int}
    """
    result = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}

    # 匹配 "= X passed, Y failed, Z skipped, W error in ...="
    # 或 "= X passed, Y failed in ...="
    summary_pattern = r"={3,}\s*(.*?)\s*={3,}"
    # 先用宽泛匹配找最后一行摘要
    lines = output.strip().split("\n")
    for line in reversed(lines):
        line = line.strip()
        if "passed" in line or "failed" in line:
            # 提取各个计数
            passed_match = re.search(r"(\d+)\s+passed", line)
            failed_match = re.search(r"(\d+)\s+failed", line)
            skipped_match = re.search(r"(\d+)\s+skipped", line)
            error_match = re.search(r"(\d+)\s+error", line)

            if passed_match:
                result["passed"] = int(passed_match.group(1))
            if failed_match:
                result["failed"] = int(failed_match.group(1))
            if skipped_match:
                result["skipped"] = int(skipped_match.group(1))
            if error_match:
                result["errors"] = int(error_match.group(1))

            if passed_match or failed_match:
                break

    return result
