from __future__ import annotations

import importlib
import inspect
import traceback
from dataclasses import dataclass, field
from time import perf_counter_ns
from typing import Any, Callable, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence


def _microseconds_from_ns(duration_ns: int) -> float:
    return duration_ns / 1000.0


def _safe_repr(value: Any, limit: int = 240) -> str:
    text = repr(value)
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


@dataclass
class InvocationTrace:
    case_name: str
    latency_us: float
    success: bool
    output: Any = None
    error: Optional[str] = None
    started_ns: int = 0
    ended_ns: int = 0

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "case_name": self.case_name,
            "latency_us": self.latency_us,
            "success": self.success,
            "started_ns": self.started_ns,
            "ended_ns": self.ended_ns,
        }
        if self.success:
            payload["output"] = self.output
        else:
            payload["error"] = self.error
        return payload


@dataclass
class PerformanceTrace:
    module: str
    callable_name: str
    compile_success: bool
    invocation_count: int
    total_latency_us: float
    average_latency_us: float
    min_latency_us: float
    max_latency_us: float
    successful_invocations: int
    failed_invocations: int
    traces: List[InvocationTrace] = field(default_factory=list)
    compile_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module": self.module,
            "callable_name": self.callable_name,
            "compile_success": self.compile_success,
            "compile_error": self.compile_error,
            "invocation_count": self.invocation_count,
            "successful_invocations": self.successful_invocations,
            "failed_invocations": self.failed_invocations,
            "total_latency_us": self.total_latency_us,
            "average_latency_us": self.average_latency_us,
            "min_latency_us": self.min_latency_us,
            "max_latency_us": self.max_latency_us,
            "traces": [trace.to_dict() for trace in self.traces],
        }


_ALLOWED_MODULE_PREFIXES = ("build_sandbox.", "sandbox_runner")


def _resolve_callable(module_name: str, callable_name: Optional[str]) -> tuple[Any, Callable[..., Any], str]:
    if not any(module_name == prefix or module_name.startswith(prefix + ".")
               for prefix in _ALLOWED_MODULE_PREFIXES):
        raise ImportError(
            f"Module '{module_name}' is outside the allowed sandbox scope. "
            f"Only modules under {_ALLOWED_MODULE_PREFIXES} may be loaded."
        )
    module = importlib.import_module(module_name)
    if callable_name:
        target = getattr(module, callable_name)
        return module, target, callable_name

    if hasattr(module, "main") and callable(getattr(module, "main")):
        return module, getattr(module, "main"), "main"

    callables = []
    for name, value in vars(module).items():
        if name.startswith("_"):
            continue
        if inspect.isfunction(value):
            callables.append((name, value))
    if len(callables) == 1:
        name, value = callables[0]
        return module, value, name
    raise AttributeError(f"Unable to resolve callable for module '{module_name}'")


def _invoke_target(target: Callable[..., Any], params: Mapping[str, Any]) -> Any:
    if inspect.iscoroutinefunction(target):
        import asyncio

        return asyncio.run(target(**params))
    return target(**params)


def run_module(
    module_name: str,
    sample_params: Sequence[Mapping[str, Any]],
    callable_name: Optional[str] = None,
    case_names: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    compile_started_ns = perf_counter_ns()
    try:
        _, target, resolved_name = _resolve_callable(module_name, callable_name)
        compile_success = True
        compile_error = None
    except Exception:
        compile_success = False
        compile_error = traceback.format_exc()
        resolved_name = callable_name or "<unresolved>"
        compile_ended_ns = perf_counter_ns()
        trace = PerformanceTrace(
            module=module_name,
            callable_name=resolved_name,
            compile_success=False,
            compile_error=compile_error,
            invocation_count=0,
            successful_invocations=0,
            failed_invocations=0,
            total_latency_us=_microseconds_from_ns(compile_ended_ns - compile_started_ns),
            average_latency_us=0.0,
            min_latency_us=0.0,
            max_latency_us=0.0,
            traces=[],
        )
        return trace.to_dict()

    invocation_traces: List[InvocationTrace] = []
    for index, params in enumerate(sample_params):
        case_name = case_names[index] if case_names and index < len(case_names) else f"case_{index}"
        started_ns = perf_counter_ns()
        try:
            output = _invoke_target(target, params)
            ended_ns = perf_counter_ns()
            invocation_traces.append(
                InvocationTrace(
                    case_name=case_name,
                    latency_us=_microseconds_from_ns(ended_ns - started_ns),
                    success=True,
                    output=_safe_repr(output),
                    started_ns=started_ns,
                    ended_ns=ended_ns,
                )
            )
        except Exception:
            ended_ns = perf_counter_ns()
            invocation_traces.append(
                InvocationTrace(
                    case_name=case_name,
                    latency_us=_microseconds_from_ns(ended_ns - started_ns),
                    success=False,
                    error=traceback.format_exc(),
                    started_ns=started_ns,
                    ended_ns=ended_ns,
                )
            )

    latencies = [trace.latency_us for trace in invocation_traces]
    total_latency_us = sum(latencies)
    successful_invocations = sum(1 for trace in invocation_traces if trace.success)
    failed_invocations = len(invocation_traces) - successful_invocations
    performance_trace = PerformanceTrace(
        module=module_name,
        callable_name=resolved_name,
        compile_success=compile_success,
        compile_error=compile_error,
        invocation_count=len(invocation_traces),
        successful_invocations=successful_invocations,
        failed_invocations=failed_invocations,
        total_latency_us=total_latency_us,
        average_latency_us=(total_latency_us / len(invocation_traces)) if invocation_traces else 0.0,
        min_latency_us=min(latencies) if latencies else 0.0,
        max_latency_us=max(latencies) if latencies else 0.0,
        traces=invocation_traces,
    )
    return performance_trace.to_dict()


def run_modules(specs: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for spec in specs:
        results.append(
            run_module(
                module_name=str(spec["module"]),
                sample_params=list(spec.get("sample_params", [])),
                callable_name=spec.get("callable_name"),
                case_names=spec.get("case_names"),
            )
        )
    return results


if __name__ == "__main__":
    demo_specs = [
        {
            "module": "sandbox_runner",
            "callable_name": "run_modules",
            "sample_params": [
                {
                    "specs": [
                        {
                            "module": "sandbox_runner",
                            "callable_name": "_microseconds_from_ns",
                            "sample_params": [{"duration_ns": 1000}, {"duration_ns": 2500}],
                        }
                    ]
                }
            ],
            "case_names": ["self_test"],
        }
    ]
    import json

    print(json.dumps(run_modules(demo_specs), indent=2))