from pathlib import Path

import pytest

from r2ai import reproduce


def test_targets_and_groups():
    assert set(reproduce.TARGETS) == {"ch-rrf", "d250-doconly", "120a", "120a-en3", "120a-en10", "120a-nop1"}
    assert {t.group for t in reproduce.TARGETS.values()} == set(reproduce.GROUP_ORDER) == set(reproduce.REQUIRED)
    assert all(len(t.sha256) == 64 for t in reproduce.TARGETS.values())
    assert set(reproduce.SUBMISSIONS) == set(reproduce.TARGETS) - {"120a-nop1"}


def test_group_commands(tmp_path):
    root, work = tmp_path / "root", tmp_path / "root/out/runs/s49-120a/work-x"
    t = reproduce.TARGETS
    pub = reproduce.group_command("public", root, [t["d250-doconly"]], work)
    assert pub[0].endswith("scripts/reproduce_public.sh") and len(pub) == 2          # no P1 texts: CH-rrf not built
    assert reproduce.group_command("public", root, [t["ch-rrf"]], work)[-1].endswith("p1_chunks_chrrf.parquet")
    assert reproduce.group_command("120a", root, [t["120a-nop1"]], work)[-1] == "none"
    assert reproduce.group_command("120a", root, [t["120a-en10"]], work)[-1].endswith("inputs/p1_chunks.parquet")


def test_cli_list_and_errors(tmp_path, capsys):
    assert reproduce.main(["--list"]) == 0
    out = capsys.readouterr().out
    assert "ch-rrf        public  submission" in out and "120a-nop1     120a    check" in out
    with pytest.raises(SystemExit):
        reproduce.main(["no-such-target"])
    with pytest.raises(SystemExit, match="out/runs not found"):
        reproduce.main(["--root", str(tmp_path), "ch-rrf"])


def test_missing_inputs_fail_without_running(tmp_path, monkeypatch):
    (tmp_path / "out/runs").mkdir(parents=True)
    monkeypatch.setattr(reproduce, "run_group", lambda *a: pytest.fail("must not run a script with missing inputs"))
    assert reproduce.main(["--root", str(tmp_path), "ch-rrf"]) == 1
    report = next(Path(tmp_path, "out/runs/reproduce").glob("report-*.json")).read_text(encoding="utf-8")
    assert '"status": "FAIL"' in report and "submissions/3_CHrrf.zip" in report


def test_all_is_the_five_submissions(tmp_path, capsys):
    (tmp_path / "out/runs").mkdir(parents=True)
    reproduce.main(["--root", str(tmp_path), "--all", "--dry-run"])
    out = capsys.readouterr().out
    assert "[120a] missing inputs" in out and "[public] missing inputs" in out
    assert "120a-nop1" not in out.split("target")[-1]
