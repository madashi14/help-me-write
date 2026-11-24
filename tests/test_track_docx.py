import copy
import hashlib
import json
import re
import subprocess
import zipfile
from datetime import datetime, timezone

import docx
import pytest
from docx import Document
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml.ns import nsdecls
from docx.oxml.parser import parse_xml
from lxml import etree

from fixtures.builders import write_docx
from helpmewrite import cli, render, track_docx
from helpmewrite.edits import Edit, EditSet
from helpmewrite.extract import iter_body_paragraphs, visible_text
from helpmewrite.track_docx import apply_edits_docx

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}
needs_soffice = pytest.mark.needs_soffice
DATE = datetime(2026, 11, 24, 10, 0, 0, tzinfo=timezone.utc)


def E(paragraph, find, replace=None, comment=None, by="revisore"):
    return Edit(paragraph, None, None, find, replace, comment, "motivo", by)


def S(*edits):
    return EditSet("help-me-write", list(edits))


def xml_docx(path, *paragraphs, hyperlink=False):
    """A .docx whose paragraphs are given as inner w:p XML (w: and r: prefixes)."""
    document = docx.Document()
    rid = ""
    if hyperlink:
        rid = document.part.relate_to("https://example.org/", RT.HYPERLINK, is_external=True)
    for inner in paragraphs:
        p = document.add_paragraph()._p
        wrapper = parse_xml(f"<w:p {nsdecls('w', 'r')}>{inner.replace('RID', rid)}</w:p>")
        for child in list(wrapper):
            p.append(child)
    document.save(str(path))
    return path


def run(text, rpr=""):
    return f'<w:r>{rpr}<w:t xml:space="preserve">{text}</w:t></w:r>'


def paragraphs(path):
    return iter_body_paragraphs(Document(str(path)))


def rejected_text(p, author="help-me-write"):
    """Visible text after rejecting every revision of `author`."""
    p = copy.deepcopy(p)
    for ins in X(p, ".//w:ins[@w:author=$a]", a=author):
        ins.getparent().remove(ins)
    for d in X(p, ".//w:del[@w:author=$a]", a=author):
        for t in d.iter(f"{{{W}}}delText"):
            t.tag = f"{{{W}}}t"
        parent, at = d.getparent(), d.getparent().index(d)
        for child in list(d):
            parent.insert(at, child)
            at += 1
        parent.remove(d)
    return visible_text(p)


def X(el, expr, **variables):
    return etree.XPath(expr, namespaces=NS)(el, **variables)


def xml(p):
    return etree.tostring(p, encoding="unicode")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --- the brief's cases -----------------------------------------------------------------


def test_replace_inside_single_run(tmp_path):
    src = write_docx(tmp_path / "a.docx", ["Il sistema e stato installato."])
    r = apply_edits_docx(src, S(E(0, "e stato", "è stato", None)), tmp_path / "b.docx")
    assert r.applied == [0] and r.failed == []
    p = paragraphs(tmp_path / "b.docx")[0]
    assert visible_text(p) == "Il sistema è stato installato."
    assert 'w:author="help-me-write"' in etree.tostring(p).decode()
    assert rejected_text(p) == "Il sistema e stato installato."
    deleted = X(p, ".//w:del")
    inserted = X(p, ".//w:ins")
    assert len(deleted) == 1 and len(inserted) == 1
    assert "".join(X(deleted[0], ".//w:delText/text()")) == "e stato"
    assert X(deleted[0], ".//w:t") == []
    assert deleted[0].getnext() is inserted[0]


def test_replace_across_runs_keeps_formatting(tmp_path):
    src = xml_docx(tmp_path / "a.docx",
                   run("Il ") + run("framework", "<w:rPr><w:b/></w:rPr>") + run(" React"))
    r = apply_edits_docx(src, S(E(0, "framework React", "framework Vue")), tmp_path / "b.docx")
    assert r.applied == [0] and r.failed == []
    p = paragraphs(tmp_path / "b.docx")[0]
    assert visible_text(p) == "Il framework Vue"
    assert rejected_text(p) == "Il framework React"
    ins_run = X(p, ".//w:ins/w:r")
    assert len(ins_run) == 1 and X(ins_run[0], "./w:rPr/w:b")
    deleted_runs = X(p, ".//w:del/w:r")
    assert [bool(X(dr, "./w:rPr/w:b")) for dr in deleted_runs] == [True, False]
    assert X(p, "./w:r[1]/w:t/text()") == ["Il "]


def test_comment_only(tmp_path):
    src = write_docx(tmp_path / "a.docx", ["Il fatturato è cresciuto del 40% nel 2020."])
    out = tmp_path / "b.docx"
    r = apply_edits_docx(src, S(E(0, "del 40%", None, "Indica la fonte di questo dato")), out)
    assert r.applied == [0] and r.failed == []
    assert len(list(Document(out).comments)) == 1 and "fonte" in next(iter(Document(out).comments)).text
    comment = next(iter(Document(out).comments))
    assert comment.author == "help-me-write" and comment.initials == "HMW"
    p = paragraphs(out)[0]
    assert visible_text(p) == "Il fatturato è cresciuto del 40% nel 2020."
    assert X(p, ".//w:ins | .//w:del") == []
    start = X(p, "./w:commentRangeStart")[0]
    end = X(p, "./w:commentRangeEnd")[0]
    assert X(start.getnext(), "string(./w:t)") == "del 40%"
    assert X(end.getprevious(), "string(./w:t)") == "del 40%"
    assert X(end.getnext(), "./w:commentReference")


def test_not_found_and_ambiguous(tmp_path):
    src = write_docx(tmp_path / "a.docx", ["uno due uno", "tre"])
    r = apply_edits_docx(src, S(E(0, "quattro", "4"), E(0, "uno", "1"), E(1, "tre", "3")),
                         tmp_path / "b.docx")
    assert {f["reason"] for f in r.failed} == {"not found", "ambiguous"}
    assert r.applied == [2]
    assert [f["index"] for f in r.failed] == [0, 1]
    assert visible_text(paragraphs(tmp_path / "b.docx")[0]) == "uno due uno"


TUTOR = ('w:author="Tutor" w:date="2026-10-01T09:00:00Z"')
TUTOR_PARAGRAPH = (
    run("Il progetto ")
    + f'<w:del w:id="7" {TUTOR}><w:r>'
    + '<w:delText xml:space="preserve">molto </w:delText></w:r></w:del>'
    + run("ambizioso ")
    + f'<w:ins w:id="8" {TUTOR}>{run("e innovativo ")}</w:ins>'
    + run("e stato completato.")
)


def _tutor_doc(path):
    xml_docx(path, TUTOR_PARAGRAPH, run("Secondo paragrafo del tutor."))
    document = Document(str(path))
    second = document.paragraphs[1]
    document.add_comment(second.runs, text="Rivedi questa frase", author="Tutor", initials="T")
    document.save(str(path))
    return path


def _tutor_revisions(p):
    return [xml(el) for el in X(p, ".//w:ins[@w:author='Tutor'] | .//w:del[@w:author='Tutor']")]


def test_track_on_doc_with_existing_revisions(tmp_path):
    src = _tutor_doc(tmp_path / "a.docx")
    before = paragraphs(src)[0]
    assert visible_text(before) == "Il progetto ambizioso e innovativo e stato completato."
    out = tmp_path / "b.docx"
    r = apply_edits_docx(src, S(E(0, "e stato", "è stato"),
                                E(1, "paragrafo", None, "Parola poco chiara")), out, date=DATE)
    assert r.applied == [0, 1] and r.failed == []
    p = paragraphs(out)[0]
    assert visible_text(p) == "Il progetto ambizioso e innovativo è stato completato."
    assert _tutor_revisions(p) == _tutor_revisions(before)
    comments = list(Document(out).comments)
    assert sorted(c.author for c in comments) == ["Tutor", "help-me-write"]
    ids = [c.comment_id for c in comments]
    assert len(set(ids)) == 2


def test_edit_spanning_a_tutor_deletion_leaves_it_intact(tmp_path):
    src = _tutor_doc(tmp_path / "a.docx")
    before = paragraphs(src)[0]
    out = tmp_path / "b.docx"
    r = apply_edits_docx(src, S(E(0, "progetto ambizioso", "lavoro ambizioso")), out)
    assert r.applied == [0]
    p = paragraphs(out)[0]
    assert visible_text(p) == "Il lavoro ambizioso e innovativo e stato completato."
    assert rejected_text(p) == visible_text(before)
    assert _tutor_revisions(p) == _tutor_revisions(before)
    assert not X(p, ".//w:del[@w:author='help-me-write']//w:del")


def test_edit_touching_a_tutor_insertion_fails_cleanly(tmp_path):
    src = _tutor_doc(tmp_path / "a.docx")
    r = apply_edits_docx(src, S(E(0, "innovativo", "originale")), tmp_path / "b.docx")
    assert r.applied == [] and r.failed == [{"index": 0, "reason": "existing revision"}]
    assert xml(paragraphs(tmp_path / "b.docx")[0]) == xml(paragraphs(src)[0])


ZOTERO = (
    '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
    '<w:r><w:instrText xml:space="preserve"> ADDIN ZOTERO_ITEM CSL_CITATION '
    '{"citationID":"a1b2"} </w:instrText></w:r>'
    '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
    + run("(Rossi, 2020)")
    + '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
)
HYPERLINK = ('<w:hyperlink r:id="RID"><w:r><w:rPr><w:rStyle w:val="Hyperlink"/></w:rPr>'
             '<w:t>sito ufficiale</w:t></w:r></w:hyperlink>')


def test_track_refuses_hyperlink_and_field(tmp_path):
    src = xml_docx(tmp_path / "a.docx",
                   run("Consulta il ") + HYPERLINK + run(" del progetto."),
                   run("Come mostrato ") + ZOTERO + run(", il metodo funziona."),
                   hyperlink=True)
    before = [xml(p) for p in paragraphs(src)]
    assert visible_text(paragraphs(src)[1]) == "Come mostrato (Rossi, 2020), il metodo funziona."
    out = tmp_path / "b.docx"
    inside = apply_edits_docx(src, S(E(0, "sito ufficiale", "sito"), E(1, "Rossi", "Bianchi"),
                                     E(1, "il metodo", "la procedura")), out)
    assert inside.applied == [2]
    assert inside.failed == [{"index": i, "reason": "hyperlink/field"} for i in range(2)]
    ps = paragraphs(out)
    assert xml(ps[0]) == before[0]
    assert visible_text(ps[1]) == "Come mostrato (Rossi, 2020), la procedura funziona."
    assert "ZOTERO_ITEM" in xml(ps[1])
    across = apply_edits_docx(src, S(E(0, "il sito", None, "Quale sito?"),
                                     E(1, "mostrato (Rossi", "visto (Rossi")), tmp_path / "c.docx")
    assert across.applied == []
    assert across.failed == [{"index": i, "reason": "hyperlink/field"} for i in range(2)]
    assert [xml(p) for p in paragraphs(tmp_path / "c.docx")] == before
    assert len(Document(tmp_path / "c.docx").comments) == 0


def test_content_control_is_refused(tmp_path):
    # e.g. a Mendeley citation: a run-level w:sdt the plugin regenerates
    sdt = ('<w:sdt><w:sdtPr><w:tag w:val="MENDELEY_CITATION_v3_x"/></w:sdtPr><w:sdtContent>'
           + run("(Verdi, 2019)") + "</w:sdtContent></w:sdt>")
    src = xml_docx(tmp_path / "a.docx", run("Come noto ") + sdt + run(", il metodo regge."))
    for find in ("Verdi", "noto (Verdi"):
        r = apply_edits_docx(src, S(E(0, find, "Neri")), tmp_path / "b.docx")
        assert r.failed == [{"index": 0, "reason": "hyperlink/field"}]


def test_field_spanning_paragraphs_and_simple_fields_are_refused(tmp_path):
    begin = ('<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve">'
             ' ADDIN ZOTERO_BIBL {"uncited":[]} CSL_BIBLIOGRAPHY </w:instrText></w:r>'
             '<w:r><w:fldChar w:fldCharType="separate"/></w:r>')
    end = '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
    src = xml_docx(tmp_path / "a.docx",
                   begin + run("Rossi, M. (2020). Primo titolo."),
                   run("Verdi, L. (2019). Secondo titolo."),
                   run("Bianchi, A. (2018). Terzo titolo.") + end,
                   run("Vedi ")
                   + '<w:fldSimple w:instr=" PAGE "><w:r><w:t>3</w:t></w:r></w:fldSimple>'
                   + run(" pagina."),
                   run("Testo normale dopo la bibliografia."))
    r = apply_edits_docx(src, S(E(1, "Secondo titolo", "Titolo"), E(3, "Vedi  pagina", "Vedi"),
                                E(4, "normale", "comune")), tmp_path / "b.docx")
    assert r.applied == [2]
    assert r.failed == [{"index": 0, "reason": "hyperlink/field"},
                        {"index": 1, "reason": "hyperlink/field"}]


# --- further behaviour -----------------------------------------------------------------


def test_replace_with_comment_anchors_around_the_revision_pair(tmp_path):
    src = write_docx(tmp_path / "a.docx", ["Il sistema e stato installato ieri."])
    out = tmp_path / "b.docx"
    r = apply_edits_docx(src, S(E(0, "e stato", "è stato", "Manca l'accento")), out)
    assert r.applied == [0]
    p = paragraphs(out)[0]
    start = X(p, ".//w:commentRangeStart")
    end = X(p, ".//w:commentRangeEnd")
    ref = X(p, ".//w:commentReference")
    assert len(start) == len(end) == len(ref) == 1
    start, end, ref_run = start[0], end[0], ref[0].getparent()
    assert start.getparent() is p and end.getparent() is p and ref_run.getparent() is p
    assert start.getnext().tag == f"{{{W}}}del"
    assert end.getprevious().tag == f"{{{W}}}ins"
    assert end.getnext() is ref_run
    comment = next(iter(Document(out).comments))
    assert comment.text == "Manca l'accento" and comment.comment_id == int(start.get(f"{{{W}}}id"))


def test_deletion_has_no_insertion(tmp_path):
    src = write_docx(tmp_path / "a.docx", ["Il sistema è stato molto installato."])
    out = tmp_path / "b.docx"
    r = apply_edits_docx(src, S(E(0, "molto ", "", "Avverbio superfluo")), out)
    assert r.applied == [0]
    p = paragraphs(out)[0]
    assert visible_text(p) == "Il sistema è stato installato."
    assert rejected_text(p) == "Il sistema è stato molto installato."
    assert X(p, ".//w:ins") == []
    end = X(p, "./w:commentRangeEnd")[0]
    assert end.getprevious().tag == f"{{{W}}}del"


def test_several_edits_in_one_paragraph(tmp_path):
    text = "Nel 2020 il team ha sviluppato un aplicazione web, poi la ha testata."
    src = write_docx(tmp_path / "a.docx", [text])
    out = tmp_path / "b.docx"
    r = apply_edits_docx(src, S(E(0, "Nel 2020", None, "Mese?"),
                                E(0, "la ha", "l'ha"),
                                E(0, "un aplicazione", "un'applicazione"),
                                E(0, "team", None, "Quale team?")), out)
    assert r.applied == [0, 1, 2, 3] and r.failed == []
    p = paragraphs(out)[0]
    assert visible_text(p) == ("Nel 2020 il team ha sviluppato un'applicazione web, "
                               "poi l'ha testata.")
    assert rejected_text(p) == text
    assert len(Document(out).comments) == 2


def test_tabs_and_breaks_in_find_and_replace(tmp_path):
    src = xml_docx(tmp_path / "a.docx",
                   '<w:r><w:t>Voce</w:t><w:tab/><w:t xml:space="preserve">valore uno</w:t></w:r>')
    out = tmp_path / "b.docx"
    r = apply_edits_docx(src, S(E(0, "Voce\tvalore", "Voce:\nvalore")), out)
    assert r.applied == [0]
    p = paragraphs(out)[0]
    assert visible_text(p) == "Voce:\nvalore uno"
    assert rejected_text(p) == "Voce\tvalore uno"


def test_markers_between_runs_do_not_block_an_edit(tmp_path):
    src = xml_docx(tmp_path / "a.docx",
                   run("Il ") + '<w:proofErr w:type="spellStart"/>' + run("sistma")
                   + '<w:proofErr w:type="spellEnd"/><w:bookmarkStart w:id="3" w:name="seg"/>'
                   + run(" funziona") + '<w:bookmarkEnd w:id="3"/>' + run(" bene."))
    out = tmp_path / "b.docx"
    r = apply_edits_docx(src, S(E(0, "sistma funziona", "sistema funziona")), out)
    assert r.applied == [0]
    p = paragraphs(out)[0]
    assert visible_text(p) == "Il sistema funziona bene."
    assert rejected_text(p) == "Il sistma funziona bene."
    assert len(X(p, "./w:bookmarkStart | ./w:bookmarkEnd")) == 2


def test_runs_inside_a_smart_tag_are_editable(tmp_path):
    src = xml_docx(tmp_path / "a.docx",
                   run("Il ") + '<w:smartTag w:uri="urn:x" w:element="place"><w:smartTagPr>'
                   '<w:attr w:name="a" w:val="b"/></w:smartTagPr>' + run("Bologna")
                   + "</w:smartTag>" + run(" e bella."))
    out = tmp_path / "b.docx"
    r = apply_edits_docx(src, S(E(0, "Il Bologna", "La città di Bologna", "Articolo")), out)
    assert r.applied == [0]
    p = paragraphs(out)[0]
    assert visible_text(p) == "La città di Bologna e bella."
    assert rejected_text(p) == "Il Bologna e bella."
    assert X(p, "./w:smartTag/w:smartTagPr/w:attr")


@pytest.mark.parametrize("between", [
    "<w:r><w:noBreakHyphen/></w:r>",
    '<w:r><w:footnoteReference w:id="1"/></w:r>',
    '<w:r><w:sym w:font="Symbol" w:char="F0B7"/></w:r>',
])
def test_hidden_content_inside_the_match_is_refused(tmp_path, between):
    src = xml_docx(tmp_path / "a.docx", run("posta e") + between + run("mail del corso"))
    r = apply_edits_docx(src, S(E(0, "email", "posta")), tmp_path / "b.docx")
    assert r.failed == [{"index": 0, "reason": "unsupported content"}]
    assert xml(paragraphs(tmp_path / "b.docx")[0]) == xml(paragraphs(src)[0])


def test_paragraph_out_of_range_or_missing(tmp_path):
    src = write_docx(tmp_path / "a.docx", ["Unico paragrafo."])
    r = apply_edits_docx(src, S(E(5, "Unico", "Solo"),
                                Edit(None, "main.tex", 3, "Unico", "Solo", None, "m", "revisore")),
                         tmp_path / "b.docx")
    assert r.applied == []
    assert [f["index"] for f in r.failed] == [0, 1]
    assert all("paragraph" in f["reason"] for f in r.failed)


def test_table_cell_paragraph(tmp_path):
    document = docx.Document()
    document.add_paragraph("Prima della tabella.")
    document.add_table(rows=1, cols=1).cell(0, 0).text = "Cella con eror."
    document.save(str(tmp_path / "a.docx"))
    out = tmp_path / "b.docx"
    r = apply_edits_docx(tmp_path / "a.docx", S(E(1, "eror", "errore")), out)
    assert r.applied == [0]
    assert X(Document(out).tables[0].cell(0, 0)._tc, "string(.//w:ins)") == "errore"


def test_revision_ids_and_dates(tmp_path):
    src = _tutor_doc(tmp_path / "a.docx")
    out = tmp_path / "b.docx"
    apply_edits_docx(src, S(E(0, "ambizioso", "ambizioso,"), E(0, "e stato", "è stato"),
                            E(1, "Secondo", "Terzo")), out, date=DATE)
    body = Document(out).element.body
    ours = X(body, ".//w:ins[@w:author='help-me-write'] | .//w:del[@w:author='help-me-write']")
    ids = [int(el.get(f"{{{W}}}id")) for el in ours]
    assert len(ours) == 6 and len(set(ids)) == 6 and min(ids) > 8
    assert {el.get(f"{{{W}}}date") for el in ours} == {"2026-11-24T10:00:00Z"}

    apply_edits_docx(src, S(E(1, "Secondo", "Terzo")), tmp_path / "c.docx")
    stamp = X(Document(tmp_path / "c.docx").element.body,
              "string(.//w:ins[@w:author='help-me-write']/@w:date)")
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", stamp)


def test_original_is_never_modified(tmp_path):
    src = write_docx(tmp_path / "a.docx", ["Il sistema e stato installato."])
    digest = sha(src)
    apply_edits_docx(src, S(E(0, "e stato", "è stato", "accento")), tmp_path / "b.docx")
    assert sha(src) == digest
    with pytest.raises(ValueError):
        apply_edits_docx(src, S(E(0, "e stato", "è stato")), src)
    assert sha(src) == digest


def test_failed_self_check_restores_the_paragraph(tmp_path, monkeypatch):
    src = write_docx(tmp_path / "a.docx", ["Il sistema e stato installato.", "Un eror qui."])
    real = track_docx._text_run

    def broken(text, rpr):
        return real(text.upper(), rpr) if text == "è stato" else real(text, rpr)

    monkeypatch.setattr(track_docx, "_text_run", broken)
    out = tmp_path / "b.docx"
    r = apply_edits_docx(src, S(E(0, "e stato", "è stato", "accento"), E(0, "sistema", None, "?"),
                                E(1, "eror", "errore")), out)
    assert r.applied == [2]
    assert [f["index"] for f in r.failed] == [0, 1]
    assert all(f["reason"].startswith("internal check failed") for f in r.failed)
    ps = paragraphs(out)
    assert xml(ps[0]) == xml(paragraphs(src)[0])
    assert visible_text(ps[1]) == "Un errore qui."
    assert len(Document(out).comments) == 0


# --- command line ----------------------------------------------------------------------


def _edits_file(path, *edits):
    path.write_text(json.dumps({"author": "help-me-write", "edits": list(edits)},
                               ensure_ascii=False), encoding="utf-8")
    return path


def _raw(paragraph, find, replace=None, comment=None, by="revisore"):
    e = {"paragraph": paragraph, "find": find, "reason": "motivo", "by": by}
    if replace is not None:
        e["replace"] = replace
    if comment is not None:
        e["comment"] = comment
    return e


def test_track_command_writes_the_copy(tmp_path, capsys):
    src = write_docx(tmp_path / "Relazione finale Università.docx",
                     ["Il sistema e stato installato."])
    edits = _edits_file(tmp_path / "edits.json", _raw(0, "e stato", "è stato"))
    out = tmp_path / "Relazione finale Università-revisionata.docx"
    code = cli.main(["track", str(src), "--edits", str(edits), "-o", str(out), "--json"])
    data = json.loads(capsys.readouterr().out)
    assert code == 0
    assert data == {"applied": [0], "failed": [], "conflicts": []}
    assert visible_text(paragraphs(out)[0]) == "Il sistema è stato installato."


def test_track_command_merges_and_reports_failures(tmp_path, capsys):
    src = write_docx(tmp_path / "a.docx", ["Il sistema e stato installato nel 2020.", "uno uno"])
    first = _edits_file(tmp_path / "revisore.json", _raw(0, "e stato", "è stato"),
                        _raw(1, "uno", "1"))
    second = _edits_file(tmp_path / "bib.json",
                         _raw(0, "stato installato", None, "Quando?", by="bibliografia"),
                         _raw(0, "2020", None, "Fonte?", by="bibliografia"))
    out = tmp_path / "b.docx"
    code = cli.main(["track", str(src), "--edits", str(first), "--edits", str(second),
                     "-o", str(out), "--json"])
    data = json.loads(capsys.readouterr().out)
    assert code == 1
    assert data["applied"] == [0, 2]
    assert data["failed"] == [{"index": 1, "reason": "ambiguous",
                               "edit": {"paragraph": 1, "find": "uno", "replace": "1",
                                        "reason": "motivo", "by": "revisore"}}]
    assert len(data["conflicts"]) == 1
    assert data["conflicts"][0]["edit"]["find"] == "stato installato"
    assert visible_text(paragraphs(out)[0]) == "Il sistema è stato installato nel 2020."
    assert len(Document(out).comments) == 1


def test_track_command_readable_summary(tmp_path, capsys):
    src = write_docx(tmp_path / "a.docx", ["Il sistema e stato installato."])
    edits = _edits_file(tmp_path / "e.json", _raw(0, "e stato", "è stato"),
                        _raw(0, "assente", "x"))
    code = cli.main(["track", str(src), "--edits", str(edits), "-o", str(tmp_path / "b.docx")])
    text = capsys.readouterr().out
    assert code == 1
    assert "1 applied" in text and "not found" in text and "assente" in text


def test_track_command_usage_errors(tmp_path, capsys):
    src = write_docx(tmp_path / "a.docx", ["Il sistema e stato installato."])
    good = _edits_file(tmp_path / "e.json", _raw(0, "e stato", "è stato"))
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    invalid = _edits_file(tmp_path / "invalid.json", {"paragraph": 0, "find": "x"})
    corrupt = tmp_path / "corrupt.docx"
    corrupt.write_bytes(b"not a zip")
    tex = tmp_path / "notes.txt"
    tex.write_text("plain", encoding="utf-8")
    out = str(tmp_path / "b.docx")
    digest = sha(src)
    cases = [
        ["track", str(src), "--edits", str(bad), "-o", out],
        ["track", str(src), "--edits", str(invalid), "-o", out],
        ["track", str(src), "--edits", str(good), "-o", str(src)],
        ["track", str(src), "--edits", str(good), "-o", str(good)],
        ["track", str(corrupt), "--edits", str(good), "-o", out],
        ["track", str(tmp_path / "missing.docx"), "--edits", str(good), "-o", out],
        ["track", str(tex), "--edits", str(good), "-o", str(tmp_path / "out")],
        ["track", str(src), "-o", out],
    ]
    for argv in cases:
        assert cli.main(argv) == 2, argv
    err = capsys.readouterr().err
    assert "Traceback" not in err
    assert "unsupported format" in err
    assert "edits[0]" in err
    assert sha(src) == digest
    assert not (tmp_path / "b.docx").exists()


# --- LibreOffice -----------------------------------------------------------------------


def _rich_output(tmp_path):
    src = _tutor_doc(tmp_path / "a.docx")
    document = Document(str(src))
    document.add_paragraph("Il fatturato e cresciuto del 40% nel 2020, in modo molto evidente.")
    document.save(str(src))
    out = tmp_path / "b.docx"
    r = apply_edits_docx(src, S(E(0, "e stato", "è stato", "Accento mancante"),
                                E(2, "e cresciuto", "è cresciuto"),
                                E(2, "del 40%", None, "Indica la fonte di questo dato"),
                                E(2, "molto ", ""),
                                E(1, "Secondo", "Terzo")), out, date=DATE)
    assert r.failed == []
    return src, out


@needs_soffice
def test_tracked_output_opens_in_libreoffice(tmp_path):
    _, out = _rich_output(tmp_path)
    pdf = render.render_pdf(out, tmp_path / "render")
    assert pdf.is_file() and pdf.stat().st_size > 0


@needs_soffice
def test_libreoffice_roundtrip_keeps_revisions_and_comments(tmp_path):
    src, out = _rich_output(tmp_path)
    expected = [visible_text(p) for p in paragraphs(out)]
    original = [visible_text(p) for p in paragraphs(src)]
    outdir, profile = tmp_path / "roundtrip", tmp_path / "profile"
    outdir.mkdir()
    cmd = [render.find_soffice(), f"-env:UserInstallation={profile.absolute().as_uri()}",
           "--headless", "--convert-to", "docx:MS Word 2007 XML", "--outdir", str(outdir), str(out)]
    subprocess.run(cmd, capture_output=True, timeout=180, check=True)
    back = outdir / "b.docx"
    assert back.is_file()
    ps = paragraphs(back)
    texts = [visible_text(p) for p in ps]
    assert [t for t in texts if t] == [t for t in expected if t]
    assert [rejected_text(p) for p in ps if visible_text(p)] == [t for t in original if t]
    body = Document(str(back)).element.body
    assert X(body, ".//w:ins[@w:author='help-me-write']")
    assert X(body, ".//w:del[@w:author='help-me-write']")
    assert X(body, ".//w:del[@w:author='Tutor']")
    with zipfile.ZipFile(back) as z:
        comments = z.read("word/comments.xml").decode("utf-8")
    assert "Indica la fonte di questo dato" in comments and "Accento mancante" in comments
    assert "help-me-write" in comments and "Rivedi questa frase" in comments
