"""Descarga las proyecciones de población municipal del DANE y las deja en CSV largo.

Salida: datos/seguridad/poblacion_municipal.csv con cod_muni, anio, poblacion (área total).
Busca los enlaces .xlsx en la página de proyecciones del DANE y prueba también rutas conocidas.
Uso: python scripts/poblacion_dane.py --salida datos/seguridad
"""
import argparse, csv, io, os, re, sys, urllib.error, urllib.request

PAGINAS = [
    "https://www.dane.gov.co/index.php/estadisticas-por-tema/demografia-y-poblacion/proyecciones-de-poblacion",
]
CANDIDATOS = [
    "https://www.dane.gov.co/files/censo2018/proyecciones-de-poblacion/Municipal/DCD-area-proypoblacion-Mun-2005-2017_VP.xlsx",
    "https://www.dane.gov.co/files/censo2018/proyecciones-de-poblacion/Municipal/PPED-AreaMun-2018-2042_VP.xlsx",
    "https://www.dane.gov.co/files/censo2018/proyecciones-de-poblacion/Municipal/PPED-AreaMun-1985-2017_VP.xlsx",
    "https://www.dane.gov.co/files/censo2018/proyecciones-de-poblacion/Municipal/PPED-AreaMun-2020-2035_VP.xlsx",
    "https://www.dane.gov.co/files/censo2018/proyecciones-de-poblacion/Municipal/anexo-proyecciones-poblacion-Municipal_2018-2035.xlsx",
]
UA = {"User-Agent": "Mozilla/5.0 (IpG-Observatorio)"}


def bajar(url):
    ultimo = None
    for intento in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180) as r:
                return r.read()
        except urllib.error.HTTPError:
            raise
        except Exception as e:
            ultimo = e
    raise ultimo


def enlaces():
    vistos = []
    for p in PAGINAS:
        try:
            html = bajar(p).decode("utf-8", "ignore")
        except Exception as e:
            print(f"::warning::No pude leer {p}: {e}")
            continue
        for h in re.findall(r'href="([^"]+\.xlsx?)"', html, flags=re.I):
            hl = h.lower()
            # solo totales por área municipal (no sexo-edad ni pertenencia étnica)
            if ("areamun" in hl or "area-proypoblacion-mun" in hl) and "sexo" not in hl and "etnic" not in hl:
                u = h if h.startswith("http") else "https://www.dane.gov.co" + ("" if h.startswith("/") else "/") + h
                vistos.append(u)
    for u in vistos:
        print(f"::notice::enlace DANE: {u[:240]}")
    return vistos + CANDIDATOS


def leer(xlsx):
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(xlsx), read_only=True, data_only=True)
    filas = []
    for ws in wb.worksheets:
        enc = None
        for fila in ws.iter_rows(values_only=True):
            celdas = [str(c).strip().upper() if c is not None else "" for c in fila]
            if enc is None:
                if any(c in ("AÑO", "ANO", "AÑO ") for c in celdas) and any(c in ("DPMP", "MPIO", "COD_MPIO") for c in celdas):
                    enc = celdas
                    print(f"::notice::hoja {ws.title} encabezado: {[c for c in enc if c][:20]}")
                    i_cods = [enc.index(c) for c in ("DPMP", "COD_MPIO", "MPIO") if c in enc]
                    i_cod = i_cods[0]
                    i_anio = next(i for i, c in enumerate(enc) if c.startswith("AÑO") or c == "ANO")
                    i_area = next((i for i, c in enumerate(enc) if "ÁREA" in c or "AREA" in c), None)
                    i_tot = next((i for i, c in enumerate(enc) if c.startswith("TOTAL") or c.startswith("POBLACI")), None)
                    if i_tot is None:
                        enc = None
                continue
            try:
                cod, anio, tot = fila[i_cod], fila[i_anio], fila[i_tot]
                area = str(fila[i_area]).lower() if i_area is not None else "total"
            except IndexError:
                continue
            if cod is None or anio is None or tot is None or "total" not in area:
                continue
            # el código puede estar en DPMP o en MPIO según el archivo: tomar el que sea numérico
            cod = next((str(fila[i]).split(".")[0].strip() for i in i_cods
                        if fila[i] is not None and str(fila[i]).split(".")[0].strip().isdigit()), "")
            if not cod:
                continue
            cod = cod.zfill(5)
            if len(filas) < 3:
                print(f"::notice::muestra: {[str(c)[:12] for c in fila[:14]]}")
            filas.append((cod, int(float(anio)), int(round(float(tot)))))
        if filas:
            break
    return filas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--salida", default="datos/seguridad")
    a = ap.parse_args()
    os.makedirs(a.salida, exist_ok=True)
    datos = {}
    for u in dict.fromkeys(enlaces()):
        try:
            x = bajar(u)
        except Exception as e:
            print(f"::warning::fallo {u[-80:]}: {e}")
            continue
        try:
            f = leer(x)
        except Exception as e:
            print(f"::warning::no pude leer {u[-80:]}: {e}")
            continue
        print(f"::notice::{u[-80:]} -> {len(f)} filas")
        for cod, anio, tot in f:
            datos.setdefault((cod, anio), tot)
    if not datos:
        print("::error::No se obtuvo población municipal del DANE")
        sys.exit(1)
    with open(os.path.join(a.salida, "poblacion_municipal.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["cod_muni", "anio", "poblacion"])
        for (cod, anio), tot in sorted(datos.items()):
            w.writerow([cod, anio, tot])
    anios = sorted({k[1] for k in datos})
    print(f"::notice::Población: {len(datos)} filas, años {anios[0]}-{anios[-1]}")


if __name__ == "__main__":
    main()
