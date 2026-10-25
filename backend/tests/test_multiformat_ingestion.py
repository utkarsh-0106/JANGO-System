"""Tests for text extraction across the supported document formats."""
from pathlib import Path

from backend.app.services.ingestion import _load_text


def write_file(tmp_path: Path, name: str, content: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(content)
    return path


def combined(units):
    return "\n".join(text for text, _metadata in units)


def test_text_and_markdown_extraction(tmp_path):
    for name in ("notes.txt", "notes.md", "app.log"):
        path = write_file(tmp_path, name, b"JANGO document search works")
        assert "JANGO document search works" in combined(_load_text(path, path.suffix))


def test_csv_extraction_keeps_header_and_row_context(tmp_path):
    path = write_file(tmp_path, "metrics.csv", b"name,score\nAlpha,91\nBeta,87\n")
    result = combined(_load_text(path, ".csv"))
    assert "Columns" not in result or "name" in result
    assert "Row 2: name: Alpha | score: 91" in result
    assert "Row 3: name: Beta | score: 87" in result


def test_json_yaml_xml_and_html_extraction(tmp_path):
    cases = [
        ("data.json", b'{"project":"JANGO","status":"ready"}', ".json", "JANGO"),
        ("data.yaml", b'project: JANGO\nstatus: ready\n', ".yaml", "JANGO"),
        ("data.xml", b'<project><name>JANGO</name><status>ready</status></project>', ".xml", "JANGO"),
        ("data.html", b'<html><script>secret()</script><body><h1>JANGO</h1><p>Ready</p></body></html>', ".html", "Ready"),
    ]
    for name, content, extension, expected in cases:
        path = write_file(tmp_path, name, content)
        result = combined(_load_text(path, extension))
        assert expected in result
    html_path = tmp_path / "data.html"
    assert "secret()" not in combined(_load_text(html_path, ".html"))


def test_docx_extracts_paragraphs_and_tables(tmp_path):
    from docx import Document as WordDocument

    path = tmp_path / "report.docx"
    doc = WordDocument()
    doc.add_paragraph("JANGO quarterly report")
    table = doc.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Metric"
    table.cell(0, 1).text = "Value"
    doc.save(path)

    result = combined(_load_text(path, ".docx"))
    assert "JANGO quarterly report" in result
    assert "Metric | Value" in result


def test_xlsx_extracts_sheet_names_and_rows(tmp_path):
    from openpyxl import Workbook

    path = tmp_path / "metrics.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "KPIs"
    sheet.append(["metric", "value"])
    sheet.append(["retention", 92])
    workbook.save(path)

    result = combined(_load_text(path, ".xlsx"))
    assert "Worksheet: KPIs" in result
    assert "metric: retention | value: 92" in result


def test_pptx_extracts_slide_text_and_tables(tmp_path):
    from pptx import Presentation
    from pptx.util import Inches

    path = tmp_path / "briefing.pptx"
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[5])
    slide.shapes.title.text = "JANGO architecture"
    table_shape = slide.shapes.add_table(2, 2, Inches(1), Inches(2), Inches(5), Inches(1))
    table_shape.table.cell(0, 0).text = "Service"
    table_shape.table.cell(0, 1).text = "Status"
    table_shape.table.cell(1, 0).text = "API"
    table_shape.table.cell(1, 1).text = "Ready"
    presentation.save(path)

    units = _load_text(path, ".pptx")
    assert units[0][1]["slide_number"] == 1
    result = combined(units)
    assert "JANGO architecture" in result
    assert "Service | Status" in result
