#!/bin/bash

INDEX_FILE="index.html"
TEMP_LINKS="links.tmp"
TEMP_INDEX="index.tmp"

# Verify the index file exists before running
if [[ ! -f "$INDEX_FILE" ]]; then
    echo "Error: $INDEX_FILE not found in the current directory."
    exit 1
fi

> "$TEMP_LINKS"

# Process all HTML files except the index
for file in *.html; do
    if [[ "$file" != "$INDEX_FILE" && -f "$file" ]]; then
        
        # Extract title cleanly using awk
        title=$(awk -F'[<>]' 'tolower($0) ~ /<title>/ {print $3; exit}' "$file")
        
        # Fallback to the capitalized filename if the title tag is missing or empty
        if [[ -z "$title" ]]; then
            filename="${file%.*}"
            title="$(tr '[:lower:]' '[:upper:]' <<< ${filename:0:1})${filename:1}"
        fi
        
        # Build the HTML list item matching the visual theme
        echo "<a href=\"$file\" class=\"recipe-link\">" >> "$TEMP_LINKS"
        echo "  <span class=\"arrow\">→</span>" >> "$TEMP_LINKS"
        echo "  <div><strong>$title</strong></div>" >> "$TEMP_LINKS"
        echo "</a>" >> "$TEMP_LINKS"
    fi
done

# Inject the generated links safely between the HTML markers
awk '
/<!-- RECIPE_LINKS_START -->/ {
    print
    system("cat links.tmp")
    skip=1
    next
}
/<!-- RECIPE_LINKS_END -->/ {
    skip=0
}
!skip {print}
' "$INDEX_FILE" > "$TEMP_INDEX"

# Overwrite the old index and clean up temporary files
mv "$TEMP_INDEX" "$INDEX_FILE"
rm "$TEMP_LINKS"

echo "✅ $INDEX_FILE has been successfully updated with the latest recipes."