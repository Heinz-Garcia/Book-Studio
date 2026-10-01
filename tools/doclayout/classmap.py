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

from collections.abc import Iterable
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

--- Eintrag fuer eine Klasse: genau, sonst der Stufentyp -- das Endstueck
--- nach einem "_" (``<projekt>_spanisch`` -> ``spanisch``). Gegenstueck:
--- ``zuordnungs_schluessel`` in tools/doclayout/classmap.py.
local function lookup(name)
  if classmap[name] then return classmap[name] end
  local rest = name
  while true do
    local pos = string.find(rest, "_", 1, true)
    if not pos then return nil end
    rest = string.sub(rest, pos + 1)
    if classmap[rest] then return classmap[rest] end
  end
end

--- Absatzformat zu einem Div ermitteln, oder nil.
local function style_for(classes)
  for _, class in ipairs(classes) do
    local name = normalize(class)
    local style = lookup(name)
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

-- Kastentitel und Zwischentitel kommen aus der Layout-Definition, nie aus dem
-- Inhalt (Nutzer, 2026-10-01). Derselbe Filter laeuft fuer DOCX und Typst.
local kastentitel = {kastentitel_lua}
local zwischentitel = {zwischentitel_lua}
local kastenstil = {kastenstil_lua}
local symbol_font = {symbol_font_lua}

local function is_typst()
  return FORMAT:match("typst") ~= nil
end

--- Absatz, der nur aus Hervorhebung besteht (``*Transparenzhinweis*``).
local function nur_hervorhebung(block)
  if block.t ~= "Para" and block.t ~= "Plain" then return false end
  local gefunden = false
  for _, inline in ipairs(block.content) do
    if inline.t == "Emph" or inline.t == "Strong" then
      gefunden = true
    elseif inline.t ~= "Space" and inline.t ~= "SoftBreak" then
      return false
    end
  end
  return gefunden
end

--- Einfarbiges Symbol in der Symbolschrift des Layouts.
local function symbol_inline(icon)
  if is_typst() then
    return pandoc.RawInline("typst", '#text(font: "' .. symbol_font .. '")[' .. icon .. ']')
  end
  return pandoc.RawInline("openxml",
    [[<w:r><w:rPr><w:rFonts w:ascii="]] .. symbol_font .. [[" w:hAnsi="]] .. symbol_font
    .. [[" w:eastAsia="]] .. symbol_font .. [[" w:cs="]] .. symbol_font
    .. [["/></w:rPr><w:t xml:space="preserve">]] .. xml_escape(icon) .. [[</w:t></w:r>]])
end

local function mit_format(blocks, format)
  return pandoc.Div(blocks, pandoc.Attr("", {{}}, {{["custom-style"] = format}}))
end

--- Typst: Zwischentitel und Kastentitel bleiben bei ihrem Folgeabsatz.
local function klebend(blocks)
  local out = {{pandoc.RawBlock("typst", "#block(sticky: true)[")}}
  for _, b in ipairs(blocks) do table.insert(out, b) end
  table.insert(out, pandoc.RawBlock("typst", "]"))
  return out
end

--- Zwischentitel im Block: eigenes Absatzformat (DOCX), fett (Typst).
local function mit_zwischentiteln(blocks, style)
  local ziel = zwischentitel[style]
  if not ziel then return blocks end
  local out = {{}}
  for _, block in ipairs(blocks) do
    if nur_hervorhebung(block) then
      if is_typst() then
        for _, b in ipairs(klebend({{pandoc.Para({{pandoc.Strong(block.content)}})}})) do
          table.insert(out, b)
        end
      else
        table.insert(out, mit_format({{pandoc.Para(block.content)}}, ziel))
      end
    else
      table.insert(out, block)
    end
  end
  return out
end

--- Titelzeile aus dem Layout vor den Kasteninhalt. Ohne Text bringt der
--- Kasten seinen Titel selbst mit (Callout ``## Titel``) -- dann nur das Symbol.
local function mit_kastentitel(blocks, style)
  local titel = kastentitel[style]
  if not titel then return blocks end
  local symbol = {{}}
  if titel.icon ~= "" then symbol = {{symbol_inline(titel.icon), pandoc.Space()}} end
  if titel.text == "" then
    local erster = blocks[1]
    if erster and (erster.t == "Para" or erster.t == "Plain") and #symbol > 0 then
      local inhalt = {{}}
      for _, s in ipairs(symbol) do table.insert(inhalt, s) end
      for _, i in ipairs(erster.content) do table.insert(inhalt, i) end
      blocks[1] = pandoc.Para(inhalt)
    end
    return blocks
  end
  local inlines = {{}}
  for _, s in ipairs(symbol) do table.insert(inlines, s) end
  local text = pandoc.Inlines(titel.text)
  local kopf
  if is_typst() or titel.format == "" then
    table.insert(inlines, pandoc.Strong(text))
    kopf = pandoc.Para(inlines)
  else
    for _, i in ipairs(text) do table.insert(inlines, i) end
    kopf = mit_format({{pandoc.Para(inlines)}}, titel.format)
  end
  local out = {{}}
  if is_typst() then
    -- Titel und erster Absatz zusammen: nie allein am Seitenfuss.
    local erstes = {{kopf}}
    if blocks[1] then table.insert(erstes, blocks[1]) end
    for _, b in ipairs(klebend(erstes)) do table.insert(out, b) end
    for i = 2, #blocks do table.insert(out, blocks[i]) end
    return out
  end
  table.insert(out, kopf)
  for _, b in ipairs(blocks) do table.insert(out, b) end
  return out
end

--- Typst: der Kasten als Block mit Hintergrund und Rahmen aus dem Layout.
local function typst_kasten(blocks, style)
  local s = kastenstil[style] or {{}}
  local teile = {{"width: 100%", "breakable: true", "inset: 7pt"}}
  if s.fill then table.insert(teile, 'fill: rgb("#' .. s.fill .. '")') end
  if s.stroke then
    table.insert(teile, "stroke: " .. s.width .. 'pt + rgb("#' .. s.stroke .. '")')
  end
  local out = {{pandoc.RawBlock("typst", "#block(" .. table.concat(teile, ", ") .. ")[")}}
  for _, b in ipairs(blocks) do table.insert(out, b) end
  table.insert(out, pandoc.RawBlock("typst", "]"))
  return out
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
  if is_typst() then
    -- Typst: nur Kaesten mit Titel und Bloecke mit Zwischentiteln -- alles
    -- andere (Frage, Trenner, Ausrichtung) regelt der Typst-Weg selbst.
    local style = style_for(el.classes)
    if not style or not (kastentitel[style] or zwischentitel[style]) then return nil end
    if callout then el.content = callout_titles(el.content) end
    local inhalt = mit_zwischentiteln(el.content, style)
    if not kastentitel[style] then
      el.content = inhalt
      return el
    end
    return typst_kasten(mit_kastentitel(inhalt, style), style)
  end
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
  el.content = mit_kastentitel(mit_zwischentiteln(el.content, style), style)
  -- Leerer Absatz ohne Rahmen: sonst laufen farbige Kaesten
  -- (Spanisch/KeyTakeaway/Callout) ineinander. Als Rohabsatz -- ein leeres
  -- ``pandoc.Para`` laesst der DOCX-Writer weg, und Word verband die Rahmen
  -- beider Kaesten zu einem (Reisefuehrer 2026-09-30).
  if style == "Spanisch" or style == "KeyTakeaway" or style == "Callout" then
    return {{el, pandoc.RawBlock("openxml",
      [[<w:p><w:pPr><w:pStyle w:val="BodyText"/></w:pPr></w:p>]])}}
  end
  return el
end

--- Quarto macht aus ``::: {{.callout-*}}`` einen eigenen Knoten, bevor ein
--- Filter ihn als Div sieht -- und setzt ihn im Typst-Satz farbig. Hier wird er
--- zum Kasten des Layouts (Format der Klasse ``callout``), wie im DOCX.
local function Callout(el)
  if not is_typst() then return nil end
  local style = classmap["callout"] or classmap["callout-tip"] or classmap["callout-note"]
  if not style or not kastentitel[style] then return nil end
  local blocks = {{}}
  local titel = el.title and pandoc.utils.stringify(el.title) or ""
  if titel ~= "" then
    table.insert(blocks, pandoc.Para({{pandoc.Strong(pandoc.Inlines(titel))}}))
  end
  for _, b in ipairs(callout_titles(el.content)) do table.insert(blocks, b) end
  return typst_kasten(mit_kastentitel(mit_zwischentiteln(blocks, style), style), style)
end

--- Typst-Verzeichnis (Pflichtseite IVZ, ``#outline(...)``): Tiefe aus der
--- Layout-Definition wie im DOCX; die oberste Ebene, die im Verzeichnis
--- steht, hervorgehoben -- im Frage-Antwort-Buch die Gliederung, nicht die
--- (stillen) Kapitel. Nutzer, 2026-10-01.
local toc_tiefe = {toc_depth_lua}
local ivz_regel = [[
#show outline.entry: it => context {{
  let ebenen = query(heading).filter(h => h.outlined).map(h => h.level)
  let oben = if ebenen.len() > 0 {{ calc.min(..ebenen) }} else {{ 1 }}
  if it.level == oben {{ v(0.9em, weak: true); strong(it) }} else {{ it }}
}}
]]

local function RawBlock(el)
  if not is_typst() or el.format ~= "typst" then return nil end
  if not el.text:find("#outline(", 1, true) then return nil end
  local text = el.text:gsub("depth:%s*%d+", "depth: " .. toc_tiefe)
  return pandoc.RawBlock("typst", ivz_regel .. text)
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
  {{Div = Div, Image = Image, Callout = Callout, RawBlock = RawBlock}},
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


def _lua_tabelle(eintraege: dict[str, str]) -> str:
    zeilen = "".join(f"  [{lua_string(k)}] = {v},\n" for k, v in sorted(eintraege.items()))
    return "{\n" + zeilen + "}" if zeilen else "{}"


def _kastenstil(definition: LayoutDefinition, style_id: str) -> str:
    """Hintergrund und Rahmen eines Kastens (wirksam, mit Vererbung) für Typst."""
    wirksam = definition.resolve_style(style_id)
    teile: list[str] = []
    if wirksam is None:
        return "{}"
    fill = definition.resolve_color(wirksam.shading) if wirksam.shading else None
    if fill and fill.upper() != "AUTO":
        teile.append(f"fill = {lua_string(fill.upper())}")
    rahmen = wirksam.borders.get("left") or wirksam.borders.get("top") or next(
        iter(wirksam.borders.values()), None
    )
    if rahmen is not None:
        farbe = definition.resolve_color(rahmen.color) or "000000"
        if farbe.upper() == "AUTO":
            farbe = "000000"
        teile.append(f"stroke = {lua_string(farbe.upper())}")
        teile.append(f"width = {lua_string(f'{rahmen.width_pt:g}')}")
    return "{" + ", ".join(teile) + "}"


def build_lua_filter(definition: LayoutDefinition) -> str:
    """Erzeugt den Lua-Filter fuer die ``classmap`` von *definition*.

    Dazu Kastentitel, Zwischentitel und die Kastengestalt für Typst -- alles
    aus der Definition, damit DOCX und Typst denselben Satz bekommen.
    """
    entries = "".join(
        f"  [{lua_string(cls)}] = {lua_string(_word_name(style, definition))},\n"
        for cls, style in sorted(definition.classmap.items())
    )
    classmap_lua = "{\n" + entries + "}" if entries else "{}"
    titel: dict[str, str] = {}
    stil: dict[str, str] = {}
    zwischen: dict[str, str] = {}
    for sid, style in definition.styles.items():
        name = _word_name(sid, definition)
        kt = style.kastentitel
        if kt is not None and not kt.is_empty():
            fmt = _word_name(kt.format, definition) if kt.format else ""
            titel[name] = (
                "{text = " + lua_string(kt.text) + ", icon = " + lua_string(kt.icon)
                + ", format = " + lua_string(fmt) + "}"
            )
            stil[name] = _kastenstil(definition, sid)
        if style.zwischentitel:
            zwischen[name] = lua_string(_word_name(style.zwischentitel, definition))
    return _LUA_TEMPLATE.format(
        layout_name=definition.name,
        classmap_lua=classmap_lua,
        zentriert_lua=lua_string(ZENTRIERT),
        kastentitel_lua=_lua_tabelle(titel),
        zwischentitel_lua=_lua_tabelle(zwischen),
        kastenstil_lua=_lua_tabelle(stil),
        symbol_font_lua=lua_string(definition.typography.symbol_font),
        toc_depth_lua=str(int(definition.toc_depth)),
    )


def write_lua_filter(definition: LayoutDefinition, out_path: Path | str) -> Path:
    """Schreibt den Lua-Filter nach *out_path*."""
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_lua_filter(definition), encoding="utf-8", newline="\n")
    return path


def zuordnungs_schluessel(bekannt: Iterable[str], klasse: str) -> str | None:
    """Der Eintrag, der für *klasse* gilt -- genau, sonst der Stufentyp.

    GrammarGraph benennt Klassen nach der Stufe, mit dem Projekt davor
    (``ifjn_reisefuehrer_ernstfall_andalusien_v_2_spanisch``). Eine Zuordnung
    unter dem Stufentyp (``spanisch``) gilt für jedes Buch mit dieser Stufe --
    auch für ``…_v_3`` (Nutzer, 2026-09-30). Geprüft wird vom längsten zum
    kürzesten Endstück nach einem ``_``; dieselbe Regel wie ``lookup`` im Filter.
    """
    namen = set(bekannt)
    name = normalize_class(klasse)
    if name in namen:
        return name
    teile = name.split("_")
    for i in range(1, len(teile)):
        kandidat = "_".join(teile[i:])
        if kandidat in namen:
            return kandidat
    return None


def stufentyp(klasse: str, buchname: str) -> str:
    """*klasse* ohne das Projekt davor -- der Schlüssel für eine dauerhafte Zuordnung.

    ``ifjn_…_v_2_spanisch`` im Buch ``IFJN_…_v_2`` → ``spanisch``. Beginnt die
    Klasse nicht mit dem Buchnamen, bleibt sie, wie sie ist.
    """
    name = normalize_class(klasse)
    kopf = str(buchname or "").strip().lower() + "_"
    if len(kopf) > 1 and name.lower().startswith(kopf) and len(name) > len(kopf):
        return name[len(kopf):]
    return name


def normalize_class(name: str) -> str:
    """Python-Gegenstueck zu ``normalize`` im Filter -- fuer Tests und Pruefungen."""
    text = str(name or "").strip()
    if text.startswith("{"):
        text = text[1:]
    if text.endswith("}"):
        text = text[:-1]
    return text.lstrip(".")


__all__ = [
    "build_lua_filter",
    "lua_string",
    "normalize_class",
    "stufentyp",
    "write_lua_filter",
    "zuordnungs_schluessel",
]
