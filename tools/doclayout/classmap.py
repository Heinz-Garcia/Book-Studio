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

from tools.doclayout.schema import PANDOC_BASISFORMATE, ZENTRIERT, LayoutDefinition

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
    local name = normalize(class)
    local style = classmap[name]
    if style then return style end
    -- Quarto-Callouts (callout-tip, callout-note, …) auf gemeinsames Format.
    if string.sub(name, 1, 7) == "callout" then
      return classmap["callout"] or classmap["callout-tip"] or classmap["callout-note"]
    end
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

--- Listenpunkte als Absaetze, Unterlisten eingerueckt dahinter. Unterlisten
--- gingen frueher verloren (nur Plain/Para des Punkts wurden uebernommen).
local function flatten_items(list, out, depth)
  local einzug = string.rep(utf8.char(0xA0), 4 * depth)
  local nummer = (list.t == "OrderedList" and list.listAttributes
    and list.listAttributes.start) or 1
  for _, item in ipairs(list.content) do
    local marke = depth == 0 and "•" or "◦"
    if list.t == "OrderedList" then marke = tostring(nummer) .. "." end
    nummer = nummer + 1
    local inlines = {{pandoc.Str(einzug .. marke), pandoc.Space()}}
    local danach = {{}}
    for _, part in ipairs(item) do
      if part.t == "Plain" or part.t == "Para" then
        for _, inline in ipairs(part.content) do
          table.insert(inlines, inline)
        end
      else
        table.insert(danach, part)
      end
    end
    table.insert(out, pandoc.Para(inlines))
    for _, part in ipairs(danach) do
      if part.t == "BulletList" or part.t == "OrderedList" then
        flatten_items(part, out, depth + 1)
      else
        table.insert(out, part)
      end
    end
  end
end

--- Aufzaehlungen im Div zu Absaetzen mit Bullet: sonst gewinnt der Listenstil
--- und KeyTakeaway/Spanisch/Callout verlieren ihre Vorlage.
local function flatten_bullet_lists(blocks, style)
  local out = {{}}
  local changed = false
  for _, block in ipairs(blocks) do
    if block.t == "BulletList" then
      changed = true
      flatten_items(block, out, 0)
    else
      table.insert(out, block)
    end
  end
  if changed then return out end
  return nil
end

-- Satz-Modus: nur wenn tools/doclayout/typeset das Buch setzt
-- (``-M bs-typeset=true``). Quartos eigener DOCX-Render nutzt denselben
-- Filter; dort bleiben IVZ-Platzhalter und Kapitelgrenzen wirkungslos.
local satz = false
local toc_title = ""
local toc_depth = "2"

local function read_meta(meta)
  local flag = meta["bs-typeset"]
  satz = flag == true or (flag ~= nil and pandoc.utils.stringify(flag) == "true")
  if meta["toc-title"] ~= nil then
    toc_title = pandoc.utils.stringify(meta["toc-title"])
  end
  if meta["bs-toc-depth"] ~= nil then
    toc_depth = pandoc.utils.stringify(meta["bs-toc-depth"])
  end
  return nil
end

local function xml_escape(text)
  return (text:gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;"))
end

--- Verzeichnis an der Stelle von ``::: {{.bs-ivz}}`` (Pflichtseite IVZ).
--- Gleiches Feld wie Pandocs ``--toc`` -- das setzt es aber immer an den
--- Anfang, vor Impressum und Titelseiten.
local function toc_block()
  local titel = ""
  if toc_title ~= "" then
    titel = [[<w:p><w:pPr><w:pStyle w:val="TOCHeading"/></w:pPr>]]
      .. [[<w:r><w:t xml:space="preserve">]] .. xml_escape(toc_title)
      .. [[</w:t></w:r></w:p>]]
  end
  -- Feldschalter mit string.char(92) statt woertlichem Backslash: Backslash
  -- plus u sieht im Filter aus wie ein JSON-Escape (siehe lua_string).
  local bs = string.char(92)
  local feld = "TOC " .. bs .. "o &quot;1-" .. toc_depth .. "&quot; "
    .. bs .. "h " .. bs .. "z " .. bs .. "u"
  return pandoc.RawBlock("openxml",
    [[<w:sdt><w:sdtPr><w:docPartObj><w:docPartGallery w:val="Table of Contents"/>]]
    .. [[<w:docPartUnique/></w:docPartObj></w:sdtPr><w:sdtContent>]] .. titel
    .. [[<w:p><w:r><w:fldChar w:fldCharType="begin" w:dirty="true"/>]]
    .. [[<w:instrText xml:space="preserve">]] .. feld
    .. [[</w:instrText><w:fldChar w:fldCharType="separate"/>]]
    .. [[<w:fldChar w:fldCharType="end"/></w:r></w:p></w:sdtContent></w:sdt>]])
end

local function page_break()
  return pandoc.RawBlock("openxml", [[<w:p><w:r><w:br w:type="page"/></w:r></w:p>]])
end

local function is_callout(classes)
  for _, class in ipairs(classes) do
    if string.sub(normalize(class), 1, 7) == "callout" then return true end
  end
  return false
end

--- Callout-Titel (``## Titel`` im Div) als fetter Absatz: als Ueberschrift
--- landete er im Verzeichnis und verlöre die Callout-Vorlage. Abbildungen
--- ebenso als schlichter Absatz -- sonst steht das Bild ausserhalb des Kastens.
local function callout_titles(blocks)
  local out = {{}}
  for _, block in ipairs(blocks) do
    if block.t == "Header" then
      table.insert(out, pandoc.Para({{pandoc.Strong(block.content)}}))
    elseif block.t == "Figure" then
      for _, inner in ipairs(block.content) do
        if inner.t == "Plain" then
          table.insert(out, pandoc.Para(inner.content))
        else
          table.insert(out, inner)
        end
      end
    else
      table.insert(out, block)
    end
  end
  return out
end

--- Der Fragen-Trenner aelterer Lieferungen: ``::: {{style="text-align: center;"}}``
--- mit genau einer Zeile, ohne Klasse. Dieselbe Regel wie im Typst-Weg
--- (``pre_processor._PROMPT_SEPARATOR_DIV_RE``) -- sonst stuende das Zeichen
--- im DOCX linksbuendig im Fliesstext, im PDF zentriert und abgesetzt.
local function separator_style(el)
  local css = el.attributes["style"] or ""
  if not css:match("text%-align:%s*center") then return nil end
  if #el.content ~= 1 then return nil end
  local block = el.content[1]
  if block.t ~= "Para" and block.t ~= "Plain" then return nil end
  for _, inline in ipairs(block.content) do
    if inline.t == "SoftBreak" or inline.t == "LineBreak" then return nil end
  end
  return classmap["prompt-separator"]
end

--- Jede andere Anweisung ``text-align: center``: das Hilfsformat, das jede
--- Vorlage mitbringt (schema.HILFSFORMATE). Keine Klasse, also kein Eintrag
--- in der Zuordnung -- und keine Luecke in der Formatinventur.
local function centered_style(el)
  local css = el.attributes["style"] or ""
  if css:match("text%-align:%s*center") then return {zentriert_lua} end
  return nil
end

function Div(el)
  if el.classes:includes("bs-ivz") then
    if satz then return toc_block() end
    return nil
  end
  local callout = is_callout(el.classes)
  if callout then el.content = callout_titles(el.content) end
  local style = style_for(el.classes) or separator_style(el) or centered_style(el)
  if not style then
    if callout then return el end
    return nil
  end
  el.attributes["custom-style"] = style
  -- Sprache fuer Rechtschreibpruefung (DE/ES parallel im selben Dokument).
  if style == "Spanisch" then
    el.attributes["lang"] = "es-ES"
  elseif style == "Callout" or style == "KeyTakeaway" or style == "Fachtext"
      or style == "Prompt-Frage" then
    el.attributes["lang"] = "de-DE"
  end
  local flattened = flatten_single_item_list(el.content)
  if flattened then el.content = flattened end
  local bullets = flatten_bullet_lists(el.content, style)
  if bullets then el.content = bullets end
  -- Leerer Absatz ohne Schattierung: sonst laufen farbige Kaesten
  -- (Spanisch/KeyTakeaway/Callout) optisch ineinander.
  if style == "Spanisch" or style == "KeyTakeaway" or style == "Callout" then
    return {{el, pandoc.Para({{}})}}
  end
  return el
end

--- Quarto deutet ``/img/x.png`` als Pfad ab Buchwurzel; Pandoc laeuft im Buch.
function Image(img)
  if satz and string.sub(img.src, 1, 1) == "/" then
    img.src = string.sub(img.src, 2)
    return img
  end
  return nil
end

--- Sichtbar im DOCX? Typst-Rohbloecke, Kommentare und leere Absaetze nicht.
local function visible(block)
  if block.t == "RawBlock" then return block.format == "openxml" end
  if block.t == "Para" or block.t == "Plain" then return #block.content > 0 end
  if block.t == "Div" then
    for _, inner in ipairs(block.content) do
      if visible(inner) then return true end
    end
    return false
  end
  return true
end

--- Jedes Kapitel auf eine neue Seite. Die Grenzen (``::: {{.bs-kapitel}}``)
--- setzt tools/doclayout/typeset zwischen die Kapiteldateien. Umbrochen wird
--- erst vor dem naechsten sichtbaren Block: Reine Typst-Seiten
--- (Schmutztitel, Deckblatt) ergeben so keine leeren Seiten und das Buch
--- endet nicht auf einer Leerseite.
local function chapter_breaks(doc)
  if not satz then return nil end
  local out = {{}}
  local seit_umbruch = doc.meta.title ~= nil -- der Titelblock steht davor
  local offen = false
  for _, block in ipairs(doc.blocks) do
    if block.t == "Div" and block.classes:includes("bs-kapitel") then
      if seit_umbruch then
        offen = true
        seit_umbruch = false
      end
    elseif visible(block) then
      if offen then
        table.insert(out, page_break())
        offen = false
      end
      table.insert(out, block)
      seit_umbruch = true
    else
      table.insert(out, block)
    end
  end
  doc.blocks = out
  return doc
end

return {{
  {{Meta = read_meta}},
  {{Div = Div, Image = Image}},
  {{Pandoc = chapter_breaks}},
}}
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


def _word_name(style_id: str, definition: LayoutDefinition) -> str:
    """Was als ``custom-style`` im Filter stehen muss.

    Eigene Formate heißen wie ihre Kennung. Pandocs Basisformate nicht
    („BodyText“ heißt „Body Text“) -- mit der Kennung legte Pandoc ein
    zweites, ungestaltetes Format gleicher Kennung an.
    """
    if style_id in definition.styles:
        return style_id
    return PANDOC_BASISFORMATE.get(style_id, style_id)


def build_lua_filter(definition: LayoutDefinition) -> str:
    """Erzeugt den Lua-Filter fuer die ``classmap`` von *definition*."""
    entries = "".join(
        f"  [{lua_string(cls)}] = {lua_string(_word_name(style, definition))},\n"
        for cls, style in sorted(definition.classmap.items())
    )
    classmap_lua = "{\n" + entries + "}" if entries else "{}"
    return _LUA_TEMPLATE.format(
        layout_name=definition.name,
        classmap_lua=classmap_lua,
        zentriert_lua=lua_string(ZENTRIERT),
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
