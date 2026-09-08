"""Klassen-Abbildung: aus ``::: {.prompt}`` wird das Absatzformat ``Prompt-Frage``.

Pandoc bildet einen Fenced-Div nur dann auf ein benanntes Word-Format ab, wenn
er das Attribut ``custom-style`` traegt. Die Quelle zeichnet aber semantisch aus
(``.prompt``), nicht gestalterisch (``Prompt-Frage``) -- und das ist richtig so:
welche Klasse wie aussieht, entscheidet das Layout, nicht der Generator. Dieser
Lua-Filter ist die Uebersetzung dazwischen.

Zwei Altlasten fangt er zusaetzlich ab:

1. **``::: {prompt}`` ohne Punkt.** Pandoc liest das nicht als Attributblock,
   sondern faellt auf die Kurzform zurueck und vergibt die Klasse woertlich als
   ``{prompt}`` -- mit Klammern. Bestehende Publish-Pakete sehen so aus, also
   wird diese Form beim Nachschlagen mit normalisiert.
2. **Die Frage als Listenpunkt.** Steht im Div ein ``1. Frage?``, macht Pandoc
   daraus eine OrderedList; deren Absaetze bekommen den Listenstil und das
   ``custom-style`` des Divs verfaellt. Bei einer einelementigen Liste zieht der
   Filter den Inhalt zu einem Absatz zusammen und stellt die Nummer als Text
   voran -- sichtbar identisch, aber formatierbar.

Beides betrifft nur Inhalte, die bereits ausgezeichnet sind. Der Filter raet
nie, welcher Absatz eine Frage sein koennte.
"""

from __future__ import annotations

from pathlib import Path

from tools.doclayout.schema import LayoutDefinition

_LUA_TEMPLATE = '''-- Erzeugt von tools/doclayout -- nicht von Hand aendern.
-- Layout: {layout_name}
--
-- Bildet Markdown-Klassen auf benannte Absatzformate der reference.docx ab.

local classmap = {classmap_lua}

--- Klassennamen normalisieren: "{{prompt}}" (Altform ohne Punkt) -> "prompt".
local function normalize(name)
  return (name:gsub("^{{", ""):gsub("}}$", ""))
end

--- Absatzformat zu einem Div ermitteln, oder nil.
local function style_for(classes)
  for _, class in ipairs(classes) do
    local style = classmap[normalize(class)]
    if style then return style end
  end
  return nil
end

--- Einelementige Aufzaehlung zu einem Absatz zusammenziehen.
-- Ohne das gewinnt der Listenstil und das custom-style des Divs verfaellt.
local function flatten_single_item_list(blocks)
  if #blocks ~= 1 or blocks[1].t ~= "OrderedList" then return nil end
  local list = blocks[1]
  if #list.content ~= 1 then return nil end
  local item = list.content[1]
  if #item ~= 1 or (item[1].t ~= "Plain" and item[1].t ~= "Para") then return nil end

  local start = (list.listAttributes and list.listAttributes.start) or 1
  local inlines = {{pandoc.Str(tostring(start) .. "."), pandoc.Space()}}
  for _, inline in ipairs(item[1].content) do
    table.insert(inlines, inline)
  end
  return {{pandoc.Para(inlines)}}
end

function Div(el)
  local style = style_for(el.classes)
  if not style then return nil end
  el.attributes["custom-style"] = style
  local flattened = flatten_single_item_list(el.content)
  if flattened then el.content = flattened end
  return el
end
'''


#: Die Zeichen, die ein Lua-Literal wirklich zerlegen. Alles andere --
#: Umlaute eingeschlossen -- geht woertlich hinein: Lua-Quelltext ist eine
#: Bytefolge, und Pandoc liest den Filter als UTF-8.
_LUA_ESCAPES = {
    "\\": "\\\\",
    '"': '\\"',
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
}


def lua_string(text: str) -> str:
    """Eine Zeichenkette als Lua-Literal -- ausdruecklich **nicht** ``json.dumps``.

    JSON und Lua sehen fast gleich aus und unterscheiden sich genau dort, wo es
    hier zaehlt: ``json.dumps`` schreibt jedes Nicht-ASCII-Zeichen als
    ``\\uXXXX``. Diese Schreibweise kennt Lua nicht (dort hiesse sie
    ``\\u{XXXX}``); der Filter ist damit syntaktisch kaputt, und Pandoc bricht
    den **ganzen** Lauf ab -- ``missing '{' near '"\\u0'``.

    Ein einziger Umlaut in einem Klassennamen oder einem Absatzformat machte so
    jeden DOCX-Export des Buches unmoeglich. In einer deutschsprachigen
    Anwendung ist das kein Randfall: ``Begruessung``, ``Fussnote`` oder
    ``Uebung`` entstehen von selbst, sobald der Layout-Editor ueber "Fehlende
    Klassen anlegen" ein Format zu einer Generator-Klasse erzeugt.

    Ersetzt werden deshalb nur die Zeichen, die das Literal beenden oder die
    Zeile umbrechen wuerden. Steuerzeichen haben in einem Namen nichts
    verloren, koennen den Filter aber ebenfalls zerreissen und werden als
    Lua-Dezimal-Escape (``\\ddd``) geschrieben.
    """
    out = ['"']
    for ch in str(text):
        ersatz = _LUA_ESCAPES.get(ch)
        if ersatz is not None:
            out.append(ersatz)
        elif ord(ch) < 0x20 or ord(ch) == 0x7F:
            out.append(f"\\{ord(ch):03d}")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def build_lua_filter(definition: LayoutDefinition) -> str:
    """Erzeugt den Lua-Filter fuer die ``classmap`` von *definition*."""
    entries = "".join(
        f"  [{lua_string(cls)}] = {lua_string(style)},\n"
        for cls, style in sorted(definition.classmap.items())
    )
    classmap_lua = "{\n" + entries + "}" if entries else "{}"
    return _LUA_TEMPLATE.format(
        layout_name=definition.name,
        classmap_lua=classmap_lua,
    )


def write_lua_filter(definition: LayoutDefinition, out_path: Path | str) -> Path:
    """Schreibt den Lua-Filter nach *out_path*."""
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_lua_filter(definition), encoding="utf-8", newline="\n")
    return path


def normalize_class(name: str) -> str:
    """Python-Gegenstueck zu ``normalize`` im Filter -- fuer Tests und Pruefungen."""
    text = str(name or "").strip()
    if text.startswith("{"):
        text = text[1:]
    if text.endswith("}"):
        text = text[:-1]
    return text.lstrip(".")


__all__ = ["build_lua_filter", "lua_string", "normalize_class", "write_lua_filter"]
