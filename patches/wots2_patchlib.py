#!/usr/bin/env python3
"""
patches/wots2_patchlib.py

Gemeinsame Helfer fuer die WOTS2-Patch-Skripte.

Warum es das gibt: Die alten Patches suchten ihre Ziele mit starren
Regex-Mustern (exakte Leerzeichen, exakte Kommentare). Schon ein
Kommentar hinter einer Zeile liess das Muster ins Leere laufen, und das
Skript beendete sich trotzdem mit Status 0. Diese Bibliothek
  - findet Funktionen ueber ihre Signatur + Klammer-Zaehlung,
  - vergleicht Code-Schnipsel whitespace-tolerant,
  - meldet jeden Fehlschlag laut mit dem Praefix 'PATCH-FEHLER:'
    (der Workflow macht daraus eine ::warning::).
"""
import re
import sys

_failures = []


def fail(msg):
    """Fehlschlag melden (laut, auch im CI-Log gut greppbar)."""
    _failures.append(msg)
    print('  PATCH-FEHLER: %s' % msg)


def failures():
    return list(_failures)


def flex(snippet):
    """Code-Schnipsel -> Regex, die Whitespace-Unterschiede toleriert."""
    return r'\s+'.join(re.escape(tok) for tok in snippet.split())


def _skip_literal(t, i):
    """Springt ueber Kommentare, String- und Zeichenliterale. Gibt neuen Index
    zurueck oder -1, wenn an Position i kein Literal beginnt."""
    c = t[i]
    n = len(t)
    if c == '/' and i + 1 < n and t[i + 1] == '/':
        j = t.find('\n', i)
        return n if j < 0 else j
    if c == '/' and i + 1 < n and t[i + 1] == '*':
        j = t.find('*/', i + 2)
        return n if j < 0 else j + 2
    if c in '"\'':
        j = i + 1
        while j < n and t[j] != c:
            j += 2 if t[j] == '\\' else 1
        return j + 1
    return -1


def match_brace(t, open_idx):
    """Index der zu t[open_idx]=='{' passenden '}' (Kommentare/Strings
    werden uebersprungen) oder -1."""
    depth = 0
    i = open_idx
    n = len(t)
    while i < n:
        j = _skip_literal(t, i)
        if j >= 0:
            i = j
            continue
        c = t[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def find_function(t, signature_regex):
    """Findet eine Funktionsdefinition. Gibt (start, body_open, end_exclusive)
    zurueck oder None. start zeigt auf den Anfang der Signatur."""
    for m in re.finditer(signature_regex, t, re.M):
        # nach der Signatur muss (evtl. nach Whitespace) ein '{' folgen
        k = m.end()
        while k < len(t) and t[k] in ' \t\r\n':
            k += 1
        if k < len(t) and t[k] == '{':
            close = match_brace(t, k)
            if close > 0:
                return m.start(), k, close + 1
    return None


def replace_function(t, name, signature_regex, new_text, must_contain=()):
    """Ersetzt eine komplette Funktion (Signatur + Rumpf) durch new_text.
    must_contain: Zeichenketten, die im alten Rumpf vorkommen muessen
    (Sicherheitsnetz gegen eine falsche Funktion). Gibt (text, ok) zurueck."""
    hit = find_function(t, signature_regex)
    if hit is None:
        fail('%s: Funktion nicht gefunden (Signatur geaendert?)' % name)
        return t, False
    s, b, e = hit
    body = t[b:e]
    flat = re.sub(r'\s+', ' ', body)
    for token in must_contain:
        if re.sub(r'\s+', ' ', token) not in flat:
            fail('%s: Rumpf sieht anders aus als erwartet (fehlt: %r)' % (name, token))
            return t, False
    return t[:s] + new_text + t[e:], True


def replace_snippet(t, name, old_snippet, new_text):
    """Ersetzt genau EIN Vorkommen eines whitespace-toleranten Schnipsels."""
    pat = re.compile(flex(old_snippet))
    hits = list(pat.finditer(t))
    if len(hits) != 1:
        fail('%s: %d Treffer statt genau 1' % (name, len(hits)))
        return t, False
    m = hits[0]
    return t[:m.start()] + new_text + t[m.end():], True


def last_include_end(t):
    last = None
    for m in re.finditer(r'^[ \t]*#[ \t]*include[^\n]*\n', t, re.M):
        last = m
    return last.end() if last else -1


def finish(strict_env='WOTS2_PATCH_STRICT'):
    """Am Ende jedes Skripts aufrufen: Exit-Code 0, ausser im Strict-Modus."""
    import os
    if _failures:
        print('  >>> %d Fehlschlag/Fehlschlaege in diesem Patch.' % len(_failures))
        if os.environ.get(strict_env, '') == '1':
            sys.exit(2)
