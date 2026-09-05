"""A benchmark must refuse timing if any of its advertised stages gives wrong values."""
import copy

import pytest

from demo import bench


@pytest.mark.parametrize("function", ["_frostwork_flat", "_frostwork_all", "_frostwork_item"])
def test_benchmark_refuses_timing_on_mismatch(monkeypatch, function):
    record = bench._corpus(None, 1)[0]
    monkeypatch.setattr(bench, "_corpus", lambda *args: [record])
    real = getattr(bench, function)
    if function == "_frostwork_item":
        async def broken(record):
            result = await real(record)
            del result["name"]
            return result
    else:
        def broken(record):
            result = copy.deepcopy(real(record))
            result["name"] = []
            return result
    monkeypatch.setattr(bench, function, broken)
    monkeypatch.setattr(bench, "_measure", lambda *args: pytest.fail("timing started despite wrong values"))
    with pytest.raises(ValueError, match="Parity failed"):
        bench.main(["-n", "1", "--rounds", "1"])


def test_benchmark_executes_all_stages(capsys):
    bench.main(["-n", "2", "--rounds", "2"])
    output = capsys.readouterr().out
    assert "Exact parity passed" in output
    assert "Whole-schema raw columns" in output
    assert "Complete Product" in output


@pytest.mark.parametrize("args", [["-n", "0"], ["--rounds", "0"], ["-n", "-1"]])
def test_benchmark_rejects_empty_workloads(args):
    with pytest.raises(SystemExit) as exc:
        bench.main(args)
    assert exc.value.code == 2
