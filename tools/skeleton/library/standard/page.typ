#set page(
$if(typst-page-width)$
  // Custom-Trimm statt Preset - "page-width"/"page-height" sind bereits
  // von Quarto fuer docx/odt reserviert (anderer Typ), daher eigener
  // Schluessel "typst-page-width"/"typst-page-height".
  width: $typst-page-width$,
  height: $typst-page-height$,
$else$
  paper: $if(papersize)$"$papersize$"$else$"us-letter"$endif$,
$endif$
$if(page-margin)$
  // Schema-freie Alternative zu Quartos margin-Feld (das nur x/y/top/
  // bottom/left/right zulaesst) - fuer z. B. inside/outside-Bundsteg
  // beim zweiseitigen Buchdruck (Paperback-Layout-Profil).
  margin: ($for(page-margin/pairs)$$page-margin.key$: $page-margin.value$,$endfor$),
$elseif(margin-geometry)$
  // Margins handled by marginalia.setup below
$elseif(margin)$
  margin: ($for(margin/pairs)$$margin.key$: $margin.value$,$endfor$),
$else$
  margin: (x: 1.25in, y: 1.25in),
$endif$
  numbering: $if(page-numbering)$"$page-numbering$"$else$none$endif$,
  columns: $if(columns)$$columns$$else$1$endif$,
)
$if(logo)$
#set page(background: align($logo.location$, box(inset: $logo.inset$, image("$logo.path$", width: $logo.width$$if(logo.alt)$, alt: "$logo.alt$"$endif$))))
$endif$
$if(margin-geometry)$
// Configure marginalia page geometry (functions defined in definitions.typ)
#show: marginalia.setup.with(
  inner: (
    far: $margin-geometry.inner.far$,
    width: $margin-geometry.inner.width$,
    sep: $margin-geometry.inner.separation$,
  ),
  outer: (
    far: $margin-geometry.outer.far$,
    width: $margin-geometry.outer.width$,
    sep: $margin-geometry.outer.separation$,
  ),
  top: $if(margin.top)$$margin.top$$else$1.25in$endif$,
  bottom: $if(margin.bottom)$$margin.bottom$$else$1.25in$endif$,
  book: false,
  clearance: $margin-geometry.clearance$,
)
$endif$
