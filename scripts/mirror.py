#!/usr/bin/env python3
"""Miroir statique du catalogue Cuisinier, en lecture seule et avec liste blanche."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import escape
import json
from pathlib import Path
import re
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SOURCE = "https://lesmenusduchat.synology.me/menus2/catalogue-public.php"
SCHEMA = "cuisinier-public-readonly-v1"
ID = re.compile(r"^RF-[0-9A-F]{12}$")
INDEX = ("id", "titre", "categorie", "portions", "temps", "objectif", "note", "favori", "tags")
DETAIL = INDEX + ("materiel", "ingredients", "etapes", "attention", "rechauffage", "enfant")
LISTS = {"tags", "ingredients", "etapes", "attention", "rechauffage"}

def read(url):
    last = None
    for retry in range(3):
        try:
            request = Request(url, headers={"Accept": "application/json", "User-Agent": "CuisinierMirror/1.0"})
            with urlopen(request, timeout=25) as response:
                body = response.read(5000001)
            if len(body) > 5000000:
                raise ValueError("Réponse trop volumineuse")
            obj = json.loads(body.decode("utf-8-sig"))
            if not isinstance(obj, dict):
                raise ValueError("JSON non valide")
            return obj
        except Exception as exc:
            last = exc
            if retry < 2:
                time.sleep(retry + 1)
    raise RuntimeError(f"Impossible de récupérer la source: {last}")

def clean(raw, detailed=False):
    if not isinstance(raw, dict):
        raise ValueError("Une fiche n'est pas un objet")
    ident, name, note = raw.get("id"), raw.get("titre"), raw.get("note")
    if not isinstance(ident, str) or not ID.fullmatch(ident):
        raise ValueError("Identifiant incorrect")
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"Recette sans nom: {ident}")
    if type(note) is not int or note not in (3, 4, 5):
        raise ValueError(f"Recette non admissible: {ident}")
    result = {}
    for field in DETAIL if detailed else INDEX:
        value = raw.get(field)
        if field in LISTS:
            result[field] = [x for x in value if isinstance(x, str)] if isinstance(value, list) else []
        elif field == "note":
            result[field] = note
        elif field == "favori":
            result[field] = value is True
        elif field == "portions":
            result[field] = value if type(value) is int and 0 < value <= 1000 else 4
        elif field in ("id", "titre"):
            result[field] = value
        else:
            result[field] = value if isinstance(value, str) else ""
    return result

def get_data(source):
    rows, page, total, visited = [], 1, None, set()
    while page is not None:
        if page in visited or len(visited) >= 100:
            raise ValueError("Pagination cyclique")
        visited.add(page)
        doc = read(source + "?" + urlencode({"eligible": 1, "page": page, "limit": 500}))
        if doc.get("schema") != SCHEMA or doc.get("lecture_seule") is not True:
            raise ValueError("Schéma index inattendu")
        if doc.get("filtres", {}).get("eligible") is not True or doc.get("page") != page:
            raise ValueError("Filtre ou page incorrect")
        size = doc.get("nombre_total")
        if type(size) is not int or not 0 <= size <= 5000:
            raise ValueError("Taille index incorrecte")
        if total is None:
            total = size
        elif total != size:
            raise ValueError("Catalogue modifié pendant la lecture")
        part = doc.get("recettes")
        if not isinstance(part, list):
            raise ValueError("Liste absente")
        rows.extend(clean(x) for x in part)
        nxt = doc.get("page_suivante")
        if nxt is not None and (type(nxt) is not int or nxt <= page):
            raise ValueError("Pagination incorrecte")
        page = nxt
    if len(rows) != total or len({r["id"] for r in rows}) != len(rows):
        raise ValueError("Recettes manquantes ou doublonnées")
    details = {}
    def get_detail(row):
        doc = read(source + "?" + urlencode({"id": row["id"]}))
        if doc.get("schema") != SCHEMA:
            raise ValueError("Schéma détail incorrect")
        value = clean(doc.get("recette"), detailed=True)
        if {field: value[field] for field in INDEX} != row:
            raise ValueError("Fiche modifiée pendant la lecture")
        return value
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(get_detail, r) for r in rows]
        for future in as_completed(futures):
            r = future.result()
            details[r["id"]] = r
    index = {
        "schema": SCHEMA, "lecture_seule": True,
        "nombre_total": len(rows), "page": 1, "limite": len(rows),
        "page_suivante": None,
        "filtres": {"eligible": True, "categorie": ""},
        "recettes": sorted(rows, key=lambda r: (r["titre"].casefold(), r["id"]))
    }
    return index, details

def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def publish(destination, index, details):
    destination.mkdir(parents=True, exist_ok=True)
    dump(destination / "catalogue.json", index)
    dump(destination / "manifest.json", {
        "schema": SCHEMA, "lecture_seule": True,
        "nombre_total": len(details)
    })
    for ident, value in details.items():
        dump(destination / "recettes" / (ident + ".json"), {"schema": SCHEMA, "recette": value})
    links = "\n".join(
        '<li><a href="recettes/' + escape(r["id"]) + '.json">' +
        escape(r["titre"]) + '</a> — ' + str(r["note"]) +
        '/5' + (' (favori)' if r["favori"] else '') + '</li>'
        for r in index["recettes"]
    )
    html = (
        '<!doctype html><html lang="fr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Catalogue Cuisinier</title>'
        '<style>body{font:16px/1.6 system-ui,sans-serif;max-width:850px;margin:35px auto;padding:0 20px}'
        'a{color:#236b75}li{margin:8px 0}</style></head><body>'
        '<h1>Catalogue Cuisinier (lecture seule)</h1><p>' + str(len(details)) +
        ' recettes notées au moins 3 étoiles. <a href="catalogue.json">Catalogue JSON</a></p>'
        '<ul>' + links + '</ul></body></html>'
    )
    (destination / "index.html").write_text(html, encoding="utf-8")
    (destination / ".nojekyll").write_text("", encoding="utf-8")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=SOURCE)
    parser.add_argument("--output", default="public")
    args = parser.parse_args()
    if not args.source.startswith("https://"):
        raise ValueError("Source HTTPS nécessaire")
    index, details = get_data(args.source)
    publish(Path(args.output), index, details)
    print(f"Publication prête: {len(details)} recettes admissibles.")

if __name__ == "__main__":
    main()
