#!/usr/bin/env python3
"""
Extractor masivo de datos.gov.co (plataforma Socrata) para el Observatorio de IpG.

Solo usa la librería estándar de Python 3.9+. Uso:

    # 1) Catálogo completo vía Discovery API (ids de 4x4, columnas, fechas, descargas)
    python3 extractor_datosgov.py catalogo --salida datos/catalogo_api.csv

    # 2) Cruzar el catálogo con la lista de datasets ancla (agrega el id a cada título)
    python3 extractor_datosgov.py cruzar --catalogo datos/catalogo_api.csv \
        --ancla catalogo_ancla.csv --salida datos/ancla_con_ids.csv

    # 3) Descargar un dataset completo, por páginas (SODA 2.1)
    python3 extractor_datosgov.py descargar jbjy-vk9h --salida datos/crudos/

    # 4) Descarga incremental: solo filas creadas o modificadas desde una fecha
    python3 extractor_datosgov.py descargar jbjy-vk9h --desde 2026-10-01 --salida datos/crudos/

    # 5) Descargar todos los ancla en lote
    python3 extractor_datosgov.py lote --ids datos/ancla_con_ids.csv --salida datos/crudos/

    # 6) Diccionario de columnas de los ancla (nombre, tipo, descripción)
    python3 extractor_datosgov.py metadatos --ids datos/ancla_con_ids.csv --salida datos/diccionario_ancla.csv

    # 7) Consultas agregadas definidas en un archivo JSON (tablas pequeñas, listas para publicar)
    python3 extractor_datosgov.py consultas --config consultas.json --salida datos/productos/

Token de aplicación (recomendado; gratis en https://www.datos.gov.co/profile/edit/developer_settings):
    export SOCRATA_APP_TOKEN=xxxxxxxx
Sin token la API limita por IP y corta descargas largas.
"""
import argparse, csv, io, json, os, sys, time, unicodedata, urllib.parse, urllib.request
from datetime import datetime, timezone

DOMINIO = "www.datos.gov.co"
DISCOVERY = "https://api.us.socrata.com/api/catalog/v1"
PAGINA = 50000          # filas por petición SODA (máximo práctico recomendado)
REINTENTOS = 5


def _get(url, params=None):
    if params:
        url = url + "?" + urllib.parse.urlencode(params, safe="$:,")
    headers = {"User-Agent": "IpG-Observatorio/0.1"}
    token = os.environ.get("SOCRATA_APP_TOKEN")
    if token:
        headers["X-App-Token"] = token
    for intento in range(REINTENTOS):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=300) as r:
                return r.read()
        except Exception as e:  # 429/5xx/timeout: espera exponencial
            espera = 2 ** (intento + 1)
            print(f"  aviso: {e}; reintento en {espera}s", file=sys.stderr)
            time.sleep(espera)
    raise RuntimeError(f"fallo definitivo: {url}")


def catalogo(salida):
    """Recorre la Discovery API y guarda una fila por dataset público."""
    campos = ["id", "nombre", "entidad", "categoria", "etiquetas", "creado", "actualizado_metadatos",
              "actualizado_datos", "descargas", "vistas", "columnas", "enlace"]
    os.makedirs(os.path.dirname(salida) or ".", exist_ok=True)
    offset, total, n = 0, None, 0
    with open(salida, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        while total is None or offset < total:
            data = json.loads(_get(DISCOVERY, {"domains": DOMINIO, "search_context": DOMINIO,
                                               "only": "dataset", "limit": 100, "offset": offset}))
            total = data.get("resultSetSize", 0)
            res = data.get("results", [])
            if not res:
                break
            for x in res:
                r, c = x.get("resource", {}), x.get("classification", {})
                w.writerow({
                    "id": r.get("id"), "nombre": r.get("name"), "entidad": r.get("attribution"),
                    "categoria": c.get("domain_category"), "etiquetas": "|".join(c.get("domain_tags") or []),
                    "creado": r.get("createdAt"), "actualizado_metadatos": r.get("metadata_updated_at"),
                    "actualizado_datos": r.get("data_updated_at"), "descargas": r.get("download_count"),
                    "vistas": (r.get("page_views") or {}).get("page_views_total"),
                    "columnas": "|".join(r.get("columns_field_name") or []), "enlace": x.get("link")})
                n += 1
            offset += len(res)
            print(f"  catálogo: {n}/{total}", file=sys.stderr)
    print(f"Listo: {n} datasets en {salida}")


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return " ".join(s.split())


def cruzar(cat, ancla, salida):
    """Asigna el id de 4x4 a cada título de la lista ancla (coincidencia exacta normalizada)."""
    with open(cat, encoding="utf-8") as f:
        idx = {}
        for r in csv.DictReader(f):
            idx.setdefault(_norm(r["nombre"]), []).append(r)
    with open(ancla, encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    for r in filas:
        cand = idx.get(_norm(r["titulo"]), [])
        cand.sort(key=lambda c: int(c.get("descargas") or 0), reverse=True)
        r["id"] = cand[0]["id"] if cand else ""
        r["coincidencias"] = len(cand)
    with open(salida, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
        w.writeheader(); w.writerows(filas)
    sin = sum(1 for r in filas if not r["id"])
    print(f"Listo: {len(filas) - sin} con id, {sin} sin coincidencia -> {salida}")


def descargar(ds_id, carpeta, desde=None, where=None):
    """Descarga paginada en CSV con orden estable por :id. --desde filtra por :updated_at."""
    os.makedirs(carpeta, exist_ok=True)
    sello = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destino = os.path.join(carpeta, f"{ds_id}_{sello}.csv")
    filtros = []
    if desde:
        filtros.append(f":updated_at > '{desde}T00:00:00'")
    if where:
        filtros.append(f"({where})")
    url = f"https://{DOMINIO}/resource/{ds_id}.csv"
    offset, n = 0, 0
    with open(destino, "w", newline="", encoding="utf-8") as out:
        while True:
            p = {"$limit": PAGINA, "$offset": offset, "$order": ":id"}
            if filtros:
                p["$where"] = " AND ".join(filtros)
            texto = _get(url, p).decode("utf-8")
            lineas = list(csv.reader(io.StringIO(texto)))
            if len(lineas) <= 1:
                break
            w = csv.writer(out)
            w.writerows(lineas if offset == 0 else lineas[1:])
            n += len(lineas) - 1
            offset += PAGINA
            print(f"  {ds_id}: {n} filas", file=sys.stderr)
            if len(lineas) - 1 < PAGINA:
                break
    print(f"Listo: {ds_id} -> {destino} ({n} filas)")
    return destino


def lote(archivo_ids, carpeta, desde=None):
    with open(archivo_ids, encoding="utf-8") as f:
        ids = [r["id"] for r in csv.DictReader(f) if r.get("id")]
    for i in ids:
        try:
            descargar(i, carpeta, desde)
        except Exception as e:
            print(f"ERROR {i}: {e}", file=sys.stderr)


def metadatos(archivo_ids, salida):
    """Guarda el diccionario de columnas de cada dataset (api/views/{id}.json)."""
    with open(archivo_ids, encoding="utf-8") as f:
        filas = [r for r in csv.DictReader(f) if r.get("id")]
    os.makedirs(os.path.dirname(salida) or ".", exist_ok=True)
    with open(salida, "w", newline="", encoding="utf-8") as out:
        w = csv.writer(out)
        w.writerow(["id", "titulo", "linea", "columna_api", "nombre_visible", "tipo", "descripcion"])
        for r in filas:
            try:
                v = json.loads(_get(f"https://{DOMINIO}/api/views/{r['id']}.json"))
            except Exception as e:
                print(f"ERROR {r['id']}: {e}", file=sys.stderr); continue
            for c in v.get("columns", []):
                w.writerow([r["id"], r.get("titulo"), r.get("linea"), c.get("fieldName"), c.get("name"),
                            c.get("dataTypeName"), (c.get("description") or "")[:300]])
    print(f"Listo: diccionario en {salida}")


def consultas(config, carpeta):
    """Ejecuta consultas SoQL agregadas (lista JSON de {nombre, id, select, where, group, order})."""
    with open(config, encoding="utf-8") as f:
        qs = json.load(f)
    os.makedirs(carpeta, exist_ok=True)
    for q in qs:
        if q.get("activa") is False:
            continue
        p = {"$limit": q.get("limit", 500000)}
        for k in ("select", "where", "group", "order", "having"):
            if q.get(k):
                p["$" + k] = q[k]
        try:
            datos = _get(f"https://{DOMINIO}/resource/{q['id']}.csv", p)
        except Exception as e:
            print(f"ERROR {q['nombre']}: {e}", file=sys.stderr); continue
        with open(os.path.join(carpeta, q["nombre"] + ".csv"), "wb") as out:
            out.write(datos)
        print(f"Listo: {q['nombre']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("catalogo"); a.add_argument("--salida", default="datos/catalogo_api.csv")
    b = sub.add_parser("cruzar"); b.add_argument("--catalogo", required=True); b.add_argument("--ancla", required=True)
    b.add_argument("--salida", default="datos/ancla_con_ids.csv")
    c = sub.add_parser("descargar"); c.add_argument("id"); c.add_argument("--salida", default="datos/crudos")
    c.add_argument("--desde"); c.add_argument("--where", help="filtro SoQL adicional, p. ej. \"departamento='ANTIOQUIA'\"")
    d = sub.add_parser("lote"); d.add_argument("--ids", required=True); d.add_argument("--salida", default="datos/crudos")
    d.add_argument("--desde")
    e = sub.add_parser("metadatos"); e.add_argument("--ids", required=True)
    e.add_argument("--salida", default="datos/diccionario_ancla.csv")
    g = sub.add_parser("consultas"); g.add_argument("--config", required=True); g.add_argument("--salida", default="datos/productos")
    x = ap.parse_args()
    if x.cmd == "catalogo": catalogo(x.salida)
    elif x.cmd == "cruzar": cruzar(x.catalogo, x.ancla, x.salida)
    elif x.cmd == "descargar": descargar(x.id, x.salida, x.desde, x.where)
    elif x.cmd == "lote": lote(x.ids, x.salida, x.desde)
    elif x.cmd == "metadatos": metadatos(x.ids, x.salida)
    elif x.cmd == "consultas": consultas(x.config, x.salida)
