"""tests/scenari/check_bozza_parziale.py: the number check (5) reads LaTeX number formatting."""
import sys

from conftest import ROOT

sys.path.insert(0, str(ROOT / "tests" / "scenari"))
import check_bozza_parziale as checker  # noqa: E402


def test_conclusion_numbers_normalise_latex_formatting():
    """S1: the conclusions wrote `\\(32{,}4\\,\\%\\)`, chapter 5 has `32,4\\,\\%`: the same
    number, never a false FAIL on "32"."""
    conclusion = (r"\chapter{Conclusioni}" "\n"
                  r"% commento con 99 numeri" "\n"
                  r"La precisione è salita al \(32{,}4\,\%\), con 1\,200~campioni e il 12\% di"
                  r" scarto; il modello \num{0{.}85} e la tabella~\ref{tab:x}." "\n")
    corpus = (r"Nel capitolo 5 la precisione arriva al 32,4\,\% su 1\,200 campioni;"
              r" lo scarto è il 12~\% e l'indice vale 0.85.")
    text, numbers, untraced = checker.traceable_numbers(conclusion, corpus)
    assert numbers == ["0.85", "1", "12", "200", "32,4"]  # no "32" and "4", no comment
    assert untraced == []
    # a number that is really missing is still found
    _, _, untraced = checker.traceable_numbers(conclusion + r"Poi il \(45{,}1\,\%\)." "\n", corpus)
    assert untraced == ["45,1"]


def test_normalize_numbers():
    assert checker.normalize_numbers(r"\(32{,}4\,\%\) e 1~000 e 3{.}5\;kg") == \
        r"\(32,4 %\) e 1 000 e 3.5 kg"
