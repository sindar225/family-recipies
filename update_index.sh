#!/bin/bash

set -euo pipefail

INDEX_FILE="index.html"
TEMP_LINKS="links.tmp"
TEMP_INDEX="index.tmp"
TEMP_GALLERY="gallery.tmp"
RECIPES_DIR="./recipes"
GALLERY_MARK_START="<!-- GALLERY_START -->"
GALLERY_MARK_END="<!-- GALLERY_END -->"

REFRESH_MODE=false

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --refresh)
      REFRESH_MODE=true
      shift
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

if [[ ! -f "$INDEX_FILE" ]]; then
  echo "Error: ${INDEX_FILE} not found."
  exit 1
fi

# Build list of recipe html files based on repository layout
if [[ -d "$RECIPES_DIR" ]]; then
  RECIPE_FILES="$(find "$RECIPES_DIR" -mindepth 2 -type f -name "*.html" | sort)"
else
  # fallback for any layout: find all non-index HTML files anywhere in repo
  RECIPE_FILES="$(find . -type f -name "*.html" ! -name "index.html" | sort)"
fi

# ---------- Job 1: update index ----------
> "$TEMP_LINKS"

while IFS= read -r file; do
  [[ -z "$file" ]] && continue
  title=$(awk -F'[<>]' 'tolower($0) ~ /<title>/ {print $3; exit}' "$file")
  if [[ -z "$title" ]]; then
    filename="$(basename "$file")"
    filename="${filename%.*}"
    title="$(tr '[:lower:]' '[:upper:]' <<< "${filename:0:1}")${filename:1}"
  fi
  rel_path="${file#./}"
  echo "<a href=\"${rel_path}\" class=\"recipe-link\">" >> "$TEMP_LINKS"
  echo "  <span class=\"arrow\">→</span>" >> "$TEMP_LINKS"
  echo "  <div><strong>${title}</strong></div>" >> "$TEMP_LINKS"
  echo "</a>" >> "$TEMP_LINKS"
done <<< "$RECIPE_FILES"

awk '
/<!-- RECIPE_LINKS_START -->/ {
    print
    system("cat '"$TEMP_LINKS"'")
    skip=1
    next
}
/<!-- RECIPE_LINKS_END -->/ {
    skip=0
}
!skip {print}
' "$INDEX_FILE" > "$TEMP_INDEX"

mv "$TEMP_INDEX" "$INDEX_FILE"
rm -f "$TEMP_LINKS"

# ---------- Job 2: inject gallery ----------
while IFS= read -r file; do
  [[ -z "$file" ]] && continue
  dir=$(dirname "$file")
  photos_dir="${dir}/photos"
  if [[ ! -d "$photos_dir" ]]; then
    continue
  fi

  image_list=$(find "$photos_dir" -maxdepth 1 -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.gif" \) 2>/dev/null | sort) || true

  if [[ -z "$image_list" ]]; then
    if [[ "$REFRESH_MODE" == true ]] && grep -q "$GALLERY_MARK_START" "$file"; then
      # remove existing gallery block (no photos to show)
      awk -v start="$GALLERY_MARK_START" -v end="$GALLERY_MARK_END" '
        $0 ~ start { inside=1; next }
        inside && $0 ~ end { inside=0; next }
        !inside { print }
      ' "$file" > "$file.tmp"
      mv "$file.tmp" "$file"
      # remove button line (only the HTML button, not CSS rules)
      sed -i '' '/<button class="gallery-btn"/d' "$file"
      echo " - Removed gallery (no photos): $file"
    fi
    continue
  fi

  # Remove all metadata from images using ExifTool
  if command -v exiftool >/dev/null 2>&1; then
    while IFS= read -r img; do
      exiftool -overwrite_original -all= "$img" >/dev/null 2>&1 || true
    done <<< "$image_list"
  else
    echo "⚠️  ExifTool не найден. Установите его: brew install exiftool" >&2
    exit 1
  fi

  # skip if already injected and not refreshing
  if [[ "$REFRESH_MODE" != true ]] && grep -q "$GALLERY_MARK_START" "$file"; then
    echo " - already has gallery: $file"
    continue
  fi

  > "$TEMP_GALLERY"
  {
    echo "$GALLERY_MARK_START"
    echo '<style>'
    echo '  .gallery-btn{ margin: 10px 0; padding: 8px 14px; border:1px solid var(--green); border-radius:20px; background: var(--green-soft); cursor:pointer; font-size:13px; color:var(--green); }'
    echo '  .gallery-modal{ position: fixed; top:0; left:0; width:100%; height:100%; background: rgba(0,0,0,0.8); z-index:9999; display:none; align-items:center; justify-content:center; }'
    echo '  .gallery-close{ position: absolute; top:15px; right:25px; font-size:45px; color:#fff; cursor:pointer; }'
    echo '  .gallery-slides{ text-align:center; }'
    echo '  .gallery-modal img{ max-width:90%; max-height:80vh; margin:auto; }'
    echo '  .gallery-prev,.gallery-next{ position:absolute; top:50%; transform:translateY(-50%); background:transparent; border:none; color:#fff; font-size:40px; cursor:pointer; }'
    echo '  .gallery-prev{ left:10px; }'
    echo '  .gallery-next{ right:10px; }'
    echo '  @media print { .gallery-modal, .gallery-btn { display: none !important; } }'
    echo '</style>'
    echo '<div id="gallery-modal" class="gallery-modal" style="display:none">'
    echo '  <span class="gallery-close" onclick="closeGallery()">&times;</span>'
    echo '  <div class="gallery-slides">'
    while IFS= read -r img; do
      base=$(basename "$img")
      echo "    <img class=\"gallery-slide\" src=\"photos/${base}\" alt=\"Фото\" style=\"display:none\">"
    done <<< "$image_list"
    echo '  </div>'
    echo '  <button class="gallery-prev" onclick="changeSlide(-1)">&#10094;</button>'
    echo '  <button class="gallery-next" onclick="changeSlide(1)">&#10095;</button>'
    echo '</div>'
    echo '<script>'
    echo '  let currentSlide = 0;'
    echo '  const slides = document.querySelectorAll(".gallery-slide");'
    echo '  function openGallery(){ document.getElementById("gallery-modal").style.display = "flex"; showSlide(currentSlide); }'
    echo '  function closeGallery(){ document.getElementById("gallery-modal").style.display = "none"; }'
    echo '  function showSlide(n){ if(!slides.length) return; if(n >= slides.length) n = 0; if(n < 0) n = slides.length-1; currentSlide = n; slides.forEach(s => s.style.display = "none"); slides[n].style.display = "block"; }'
    echo '  function changeSlide(n){ showSlide(currentSlide + n); }'
    echo '</script>'
    echo "$GALLERY_MARK_END"
  } > "$TEMP_GALLERY"

  # Ensure button exists (only add if not already present)
  if ! grep -q '<button class="gallery-btn"' "$file"; then
    btn='<button class="gallery-btn" onclick="openGallery()">📸 Посмотреть фото</button>'
    awk -v btn="$btn" '
        /<main[^>]*>|<div class="page"[^>]*>/ && !done {
            print
            print btn
            done = 1
            next
        }
        { print }
    ' "$file" > "$file.tmp"
    mv "$file.tmp" "$file"
  fi

  # Replace existing gallery block if needed, otherwise insert before </body>
  if grep -q "$GALLERY_MARK_START" "$file"; then
    awk -v gal="$TEMP_GALLERY" -v start="$GALLERY_MARK_START" -v end="$GALLERY_MARK_END" '
      $0 ~ start {
        while ((getline line < gal) > 0) print line
        close(gal)
        inside=1
        next
      }
      inside && $0 ~ end {
        inside=0
        next
      }
      inside { next }
      { print }
    ' "$file" > "$file.tmp"
    mv "$file.tmp" "$file"
  else
    awk -v gal="$TEMP_GALLERY" '
        /<\/body>/ {
            while ((getline line < gal) > 0) print line
            close(gal)
        }
        { print }
    ' "$file" > "$file.tmp"
    mv "$file.tmp" "$file"
  fi

  rm -f "$TEMP_GALLERY"

  echo " - Gallery processed: $file"
done <<< "$RECIPE_FILES"

echo "✅ ${INDEX_FILE} updated and galleries processed."
