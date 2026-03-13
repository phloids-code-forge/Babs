#!/bin/bash
# Reassemble the split architecture prompt into a single document.
# Restores original section order (not the concern-grouped file order).
#
# Original order:
#   Title/Preamble/Execution Protocol (from 00, top half)
#   Hardware Environment (from 01, first section)
#   Sections 1-4 (from 02)
#   Sections 5-8 (from 03)
#   Sections 9-10 (from 01, middle sections)
#   Sections 11-13 (from 04)
#   Sections 14-16 (from 01, last sections: backup, G14 prework, EdgeXpert bootstrap)
#   Section 17 (from 05, open questions)
#   Output Requirements + Style (from 00, bottom half)

DIR="$(dirname "$0")"
OUT="${1:-$DIR/babs-architecture-prompt-assembled.md}"

# Helper: extract from a file between two section headers (or to end)
extract_between() {
    local file="$1" start="$2" end="$3"
    if [ -z "$end" ]; then
        sed -n "/^## $start/,\$p" "$file"
    else
        sed -n "/^## $start/,/^## $end/{/^## $end/!p}" "$file"
    fi
}

{
    # Title block + Preamble + Execution Protocol (from 00)
    sed -n '1,/^## Execution Protocol/p' "$DIR/00-preamble-and-meta.md"
    sed -n '/^## Execution Protocol/,/^## Output Requirements/{/^## Execution Protocol/!{/^## Output Requirements/!p}}' "$DIR/00-preamble-and-meta.md"

    # Hardware Environment (from 01)
    extract_between "$DIR/01-hardware-and-infrastructure.md" "Hardware Environment" "Section 9"

    # Sections 1-4 (from 02, full file)
    cat "$DIR/02-core-architecture.md"

    # Sections 5-8 (from 03, full file)
    cat "$DIR/03-behavior-and-agency.md"

    # Sections 9-10 (from 01)
    extract_between "$DIR/01-hardware-and-infrastructure.md" "Section 9" "Section 14"

    # Sections 11-13 (from 04, full file)
    cat "$DIR/04-interface-and-proactivity.md"

    # Sections 14-16 (from 01: backup, G14 prework, EdgeXpert bootstrap)
    extract_between "$DIR/01-hardware-and-infrastructure.md" "Section 14" ""

    # Section 17: Open Questions (from 05, full file)
    cat "$DIR/05-open-questions.md"

    # Output Requirements + Style (from 00)
    extract_between "$DIR/00-preamble-and-meta.md" "Output Requirements" ""

} > "$OUT"

echo "Assembled: $OUT ($(wc -l < "$OUT") lines, $(wc -c < "$OUT") bytes)"