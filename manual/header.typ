// Typst rules pandoc includes in the manual's preamble (manual/build.py).
// pandoc puts every table in a figure, which typst will not split across
// pages unless told to (a long table otherwise leaves a blank page behind
// it); centres each one, which `auto` cell alignment inherits; and the
// pages' tables are written to read left-aligned and in a smaller face.
#show figure: set block(breakable: true)
#show table.cell: set align(left + horizon)
#show table: set text(size: 8.5pt)
