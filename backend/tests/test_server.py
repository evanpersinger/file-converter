"""Tests for server.py, the FastAPI backend behind the web UI.

Every conversion the app performs routes through this file, and it is where the
user-controlled parts of a request meet the filesystem. Three groups here: invariants
the REGISTRY has to hold for the UI to be built correctly, the request paths that
should be rejected, and the ones that should work end to end.
"""

import io
import zipfile
from collections.abc import Iterator
from pathlib import Path

import fitz
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import server


@pytest.fixture
def jobs_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the per-request scratch directory at a tmp_path.

    server.py deliberately keeps it inside the repo rather than the system temp dir,
    so without this every test would leave directories in the real .webui_jobs/.
    """
    root = tmp_path / "jobs"
    root.mkdir()
    monkeypatch.setattr(server, "JOBS_ROOT", root)
    return root


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(server.app) as test_client:
        yield test_client


# Registry invariants


def test_target_ids_are_unique() -> None:
    """BY_TARGET_ID is a dict built from these, so a duplicate would silently shadow a
    conversion and make it unreachable from the UI."""
    ids = [c.target_id for c in server.REGISTRY]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("conv", server.REGISTRY, ids=lambda c: c.target_id)
def test_source_extensions_are_lowercase_and_dotted(conv: server.Conversion) -> None:
    """The convert handler lowercases the uploaded extension before comparing against
    these, so an uppercase entry could never match anything.

    target_ext is deliberately not held to this: it only names the output file, and
    R Markdown is conventionally .Rmd. Everything that consumes it lowercases first,
    including the frontend's extensionOf.
    """
    for ext in conv.source_exts:
        assert ext.startswith(".")
        assert ext == ext.lower()
    assert conv.target_ext.startswith(".")


def test_a_produced_rmd_is_accepted_back_as_a_source() -> None:
    """r->rmd names its output .Rmd, the conventional R Markdown spelling, while
    rmd->pdf accepts .rmd. The two only line up because the convert handler lowercases
    the uploaded extension first, so this pins the one place that mismatch matters."""
    produced = server.BY_TARGET_ID["r->rmd"].target_ext
    assert produced.lower() in server.BY_TARGET_ID["rmd->pdf"].source_exts


@pytest.mark.parametrize("conv", server.REGISTRY, ids=lambda c: c.target_id)
def test_every_requirement_has_a_label(conv: server.Conversion) -> None:
    """/api/formats does DEP_LABELS[missing[0]] with no fallback, so a requires entry
    with no label raises a KeyError on a page load rather than at import."""
    for requirement in conv.requires:
        assert requirement in server.DEP_LABELS


def test_by_target_id_covers_the_whole_registry() -> None:
    assert set(server.BY_TARGET_ID) == {c.target_id for c in server.REGISTRY}


def test_all_formats_matches_the_distinct_target_extensions() -> None:
    """The UI builds one button per entry here, so a target extension missing from it
    is a conversion with no way to reach it."""
    assert {f["ext"] for f in server.ALL_FORMATS} == {c.target_ext for c in server.REGISTRY}


# Endpoints


def test_health(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"ok": True}


def test_formats_returns_the_three_maps(client: TestClient) -> None:
    body = client.get("/api/formats").json()

    assert set(body) == {"allFormats", "byExtension", "unavailable"}
    assert {"ext": ".xlsx", "name": "XLSX"} in body["allFormats"]
    # csv converts to something with no external dependency, so it is always offered.
    assert ".csv" in body["byExtension"]


def test_every_offered_conversion_names_a_real_target(client: TestClient) -> None:
    body = client.get("/api/formats").json()
    offered = {e["id"] for entries in body["byExtension"].values() for e in entries}
    blocked = {e["id"] for entries in body["unavailable"].values() for e in entries}

    assert offered <= set(server.BY_TARGET_ID)
    assert blocked <= set(server.BY_TARGET_ID)


# Rejected requests


def test_an_unknown_target_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/convert",
        data={"target": "csv->nonsense"},
        files={"file": ("a.csv", b"a\n1\n")},
    )
    assert response.status_code == 400
    assert "Unknown conversion" in response.json()["error"]


def test_a_source_extension_the_conversion_does_not_accept_is_rejected(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/convert",
        data={"target": "csv->xlsx"},
        files={"file": ("a.pdf", b"%PDF-1.4\n")},
    )
    assert response.status_code == 400
    body = response.json()
    assert ".pdf" in body["error"]
    assert ".csv" in body["hint"]


def test_a_local_conversion_without_a_model_is_rejected(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(server.llm_pdf_md, "list_ollama_models", lambda: ["qwen3.5:4b"])

    response = client.post(
        "/api/convert",
        data={"target": "pdf->md-local"},
        files={"file": ("a.pdf", b"%PDF-1.4\n")},
    )
    assert response.status_code == 400
    assert "Pick a model" in response.json()["error"]


def test_a_local_model_that_is_not_downloaded_is_rejected_with_the_pull_command(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(server.llm_pdf_md, "list_ollama_models", lambda: ["qwen3.5:4b"])

    response = client.post(
        "/api/convert",
        data={"target": "pdf->md-local", "model": "qwen3.5:9b"},
        files={"file": ("a.pdf", b"%PDF-1.4\n")},
    )
    assert response.status_code == 400
    body = response.json()
    assert "not downloaded" in body["error"]
    assert "ollama pull qwen3.5:9b" in body["hint"]


def test_a_local_conversion_uses_the_model_the_user_chose(
    client: TestClient, jobs_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The model in the request form has to be the one that actually reaches Ollama,
    not just the one that passed the installed check."""
    monkeypatch.setattr(server.llm_pdf_md, "list_ollama_models", lambda: ["qwen3.5:9b"])
    calls: list[str] = []
    monkeypatch.setattr(
        server.llm_pdf_md,
        "_convert_page_ollama",
        lambda image_b64, model: calls.append(model) or "text",
    )

    pdf_path = tmp_path / "doc.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(pdf_path)
    doc.close()

    response = client.post(
        "/api/convert",
        data={"target": "pdf->md-local", "model": "qwen3.5:9b"},
        files={"file": ("doc.pdf", pdf_path.read_bytes())},
    )

    assert response.status_code == 200
    assert calls == ["qwen3.5:9b"]


def test_a_local_conversion_returns_partial_output_when_cancelled(
    client: TestClient, jobs_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cancelling mid-conversion should still hand back whatever pages finished before
    the flag was set, not fail the request or lose that work."""
    monkeypatch.setattr(server.llm_pdf_md, "list_ollama_models", lambda: ["qwen3.5:9b"])
    job_id = "cancel-mid-job"
    calls: list[str] = []

    def fake_convert_page(image_b64: str, model: str) -> str:
        calls.append(model)
        server._JOB_CANCEL[job_id].set()  # same event /api/convert/{job_id}/cancel sets
        return f"page {len(calls)}"

    monkeypatch.setattr(server.llm_pdf_md, "_convert_page_ollama", fake_convert_page)

    pdf_path = tmp_path / "doc.pdf"
    doc = fitz.open()
    for _ in range(3):
        doc.new_page()
    doc.save(pdf_path)
    doc.close()

    response = client.post(
        "/api/convert",
        data={"target": "pdf->md-local", "model": "qwen3.5:9b", "job_id": job_id},
        files={"file": ("doc.pdf", pdf_path.read_bytes())},
    )

    assert response.status_code == 200
    assert response.content == b"page 1"
    assert len(calls) == 1


def test_local_models_flags_which_curated_models_are_downloaded(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(server.llm_pdf_md, "OLLAMA_MODELS", ["curated:1b", "curated:2b"])
    monkeypatch.setattr(
        server.llm_pdf_md, "list_ollama_models", lambda: ["curated:2b", "other:3b"]
    )

    models = client.get("/api/local-models").json()["models"]

    assert models == [
        {"name": "curated:1b", "installed": False},
        {"name": "curated:2b", "installed": True},
        {"name": "other:3b", "installed": True},
    ]


@pytest.mark.parametrize("target_id", ["pdf->md-ai", "pdf->md-claude", "pdf->md-local"])
def test_llm_conversions_are_grouped_so_convert_to_does_not_list_them(target_id: str) -> None:
    assert server.BY_TARGET_ID[target_id].group


def test_local_models_are_sorted_weakest_to_strongest(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(server.llm_pdf_md, "OLLAMA_MODELS", ["big:9b", "small:4b"])
    monkeypatch.setattr(
        server.llm_pdf_md,
        "list_ollama_models",
        lambda: ["big:9b", "huge:12b", "unsized:latest", "tiny:1.8b"],
    )

    names = [m["name"] for m in client.get("/api/local-models").json()["models"]]

    assert names == ["tiny:1.8b", "small:4b", "big:9b", "huge:12b", "unsized:latest"]


def test_the_latest_percent_is_the_last_progress_line_printed() -> None:
    output = "Converting a.pdf to md\nConverting page 1/4 (0%)\rConverting page 3/4 (50%)"

    assert server._latest_percent(output) == 50
    assert server._latest_percent("Converting a.pdf to md\n") is None


def test_progress_for_a_job_that_is_not_running_is_null(client: TestClient) -> None:
    assert client.get("/api/progress/no-such-job").json() == {"percent": None}


def test_progress_reads_the_output_of_a_running_job(client: TestClient) -> None:
    output = io.StringIO("Converting page 2/4 (25%)")

    with server.tracked("job-1", output):
        assert client.get("/api/progress/job-1").json() == {"percent": 25}

    assert client.get("/api/progress/job-1").json() == {"percent": None}


def test_cancelling_an_unknown_job_is_a_404(client: TestClient) -> None:
    response = client.post("/api/convert/no-such-job/cancel")
    assert response.status_code == 404


def test_cancelling_a_running_job_sets_its_flag(client: TestClient) -> None:
    with server.tracked("job-1", io.StringIO()) as cancel_event:
        assert not cancel_event.is_set()

        response = client.post("/api/convert/job-1/cancel")

        assert response.status_code == 200
        assert cancel_event.is_set()


def test_the_local_converters_progress_output_is_readable_as_a_percentage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Pins the print in llm_pdf_md to the pattern /api/progress parses."""
    pdf = tmp_path / "two.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.new_page()
    doc.save(pdf)
    doc.close()
    monkeypatch.setattr(server.llm_pdf_md, "_convert_page_ollama", lambda image_b64, model: "text")

    server.llm_pdf_md._convert_pdf_local(pdf, "any:1b")

    assert server._latest_percent(capsys.readouterr().out) == 100


def test_an_empty_upload_is_rejected(client: TestClient, jobs_root: Path) -> None:
    response = client.post(
        "/api/convert",
        data={"target": "csv->xlsx"},
        files={"file": ("a.csv", b"")},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["error"]


def test_an_upload_with_an_empty_filename_never_reaches_the_handler(
    client: TestClient,
) -> None:
    """FastAPI's own validation rejects this one before any of server.py runs."""
    response = client.post(
        "/api/convert",
        data={"target": "csv->xlsx"},
        files={"file": ("", b"a\n1\n")},
    )
    assert response.status_code == 422


@pytest.mark.parametrize("filename", ["/", "."])
def test_a_filename_that_is_only_path_is_rejected(
    client: TestClient, filename: str
) -> None:
    """These do reach the handler, and Path(name).name reduces both to nothing. This
    is the guard that catches what FastAPI's validation lets through."""
    response = client.post(
        "/api/convert",
        data={"target": "csv->xlsx"},
        files={"file": (filename, b"a\n1\n")},
    )
    assert response.status_code == 400
    assert "No filename" in response.json()["error"]


# Conversions that should work


def test_a_conversion_returns_the_converted_file(
    client: TestClient, jobs_root: Path
) -> None:
    response = client.post(
        "/api/convert",
        data={"target": "csv->xlsx"},
        files={"file": ("data.csv", b"code,price\n007,15\n")},
    )

    assert response.status_code == 200
    assert 'filename="data.xlsx"' in response.headers["content-disposition"]

    df = pd.read_excel(io.BytesIO(response.content), dtype=str)
    assert df.to_dict("list") == {"code": ["007"], "price": ["15"]}


def test_an_uppercase_extension_is_accepted(client: TestClient, jobs_root: Path) -> None:
    """The handler lowercases the extension on the way in, because the batch converters
    glob lowercase-only patterns."""
    response = client.post(
        "/api/convert",
        data={"target": "csv->xlsx"},
        files={"file": ("DATA.CSV", b"a\n1\n")},
    )

    assert response.status_code == 200
    assert 'filename="DATA.xlsx"' in response.headers["content-disposition"]


def test_directory_components_are_stripped_from_the_filename(
    client: TestClient, jobs_root: Path
) -> None:
    """The upload name is user-controlled and reaches the filesystem, so anything that
    looks like a path has to be reduced to a bare name."""
    response = client.post(
        "/api/convert",
        data={"target": "csv->xlsx"},
        files={"file": ("../../escaped.csv", b"a\n1\n")},
    )

    assert response.status_code == 200
    assert 'filename="escaped.xlsx"' in response.headers["content-disposition"]
    assert ".." not in response.headers["content-disposition"]


def test_several_output_files_come_back_as_a_zip(
    client: TestClient, jobs_root: Path
) -> None:
    """A multi-sheet workbook now produces one CSV per sheet, and the handler packs a
    multi-file result into a zip rather than picking one arbitrarily."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer) as writer:
        pd.DataFrame({"a": [1]}).to_excel(writer, sheet_name="First", index=False)
        pd.DataFrame({"b": [2]}).to_excel(writer, sheet_name="Second", index=False)

    response = client.post(
        "/api/convert",
        data={"target": "xlsx->csv"},
        files={"file": ("book.xlsx", buffer.getvalue())},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert 'filename="book.zip"' in response.headers["content-disposition"]

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert sorted(archive.namelist()) == ["book_First.csv", "book_Second.csv"]


def test_a_single_output_file_is_returned_as_itself(
    client: TestClient, jobs_root: Path
) -> None:
    buffer = io.BytesIO()
    pd.DataFrame({"a": [1]}).to_excel(buffer, index=False)

    response = client.post(
        "/api/convert",
        data={"target": "xlsx->csv"},
        files={"file": ("book.xlsx", buffer.getvalue())},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.content.decode() == "a\n1\n"


# Isolation


def test_the_scratch_workspace_is_removed_after_a_request(
    client: TestClient, jobs_root: Path
) -> None:
    client.post(
        "/api/convert",
        data={"target": "csv->xlsx"},
        files={"file": ("data.csv", b"a\n1\n")},
    )
    assert list(jobs_root.iterdir()) == []


def test_the_scratch_workspace_is_removed_after_a_failure(
    client: TestClient, jobs_root: Path
) -> None:
    """job_workspace cleans up in a finally, so a conversion that raises must not leave
    the upload sitting on disk."""
    response = client.post(
        "/api/convert",
        data={"target": "xlsx->csv"},
        files={"file": ("book.xlsx", b"this is not a workbook")},
    )

    assert response.status_code == 400
    assert list(jobs_root.iterdir()) == []


def test_a_conversion_does_not_touch_the_real_input_folder(
    client: TestClient, jobs_root: Path
) -> None:
    """The whole point of the sandbox: the batch converters process everything in
    their input folder, so a request must never point them at backend/input."""
    before = sorted(p.name for p in (server.BACKEND / "input").iterdir())

    client.post(
        "/api/convert",
        data={"target": "csv->xlsx"},
        files={"file": ("data.csv", b"a\n1\n")},
    )

    assert sorted(p.name for p in (server.BACKEND / "input").iterdir()) == before
