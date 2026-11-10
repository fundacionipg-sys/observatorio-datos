"""Arma las tablas de una edición del Termómetro de seguridad a partir de datos/seguridad/.

Uso: python scripts/termometro_edicion.py --datos datos/seguridad --salida <carpeta>
Escribe JSON (listas de filas) listos para el tablero.
"""
import argparse, csv, json, os, collections, datetime as dt

DELITOS = [  # clave, archivo, columna de conteo, etiqueta
    ("homicidio", "seg_homicidio", "casos", "Homicidios"),
    ("extorsion", "seg_extorsion", "casos", "Extorsiones"),
    ("secuestro", "seg_secuestro", "casos", "Secuestros"),
    ("masacres", "seg_masacres", "casos", "Masacres"),
    ("fuerza_publica", "seg_fuerza_publica", "casos", "Miembros de la Fuerza Pública afectados"),
    ("terrorismo", "seg_terrorismo", "casos", "Actos de terrorismo"),
    ("hurto_personas", "seg_hurto_personas", "casos", "Hurtos a personas"),
    ("hurto_vehiculos", "seg_hurto_vehiculos", "casos", "Hurtos de vehículos y motos"),
    ("hurto_residencias", "seg_hurto_residencias", "casos", "Hurtos a residencias"),
    ("hurto_comercio", "seg_hurto_comercio", "casos", "Hurtos a comercio"),
    ("incautacion_cocaina", "seg_incautacion_cocaina", "cantidad", "Cocaína incautada (kg)"),
    ("erradicacion", "seg_erradicacion", "cantidad", "Erradicación manual (ha)"),
]
GOBIERNOS = [  # el mes de agosto se asigna al gobierno entrante (posesión el 7 de agosto)
    ("Santos I", "2010-08", "2014-07"),
    ("Santos II", "2014-08", "2018-07"),
    ("Duque", "2018-08", "2022-07"),
    ("Petro", "2022-08", "2026-07"),
    ("Gobierno 2026-2030", "2026-08", "2030-07"),
]


def gobierno(mes):
    for g, a, b in GOBIERNOS:
        if a <= mes <= b:
            return g
    return None


def leer(ruta):
    with open(ruta, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def mes_ant(m, k=1):
    y, mm = int(m[:4]), int(m[5:7])
    t = y * 12 + mm - 1 - k
    return f"{t // 12:04d}-{t % 12 + 1:02d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datos", default="datos/seguridad")
    ap.add_argument("--salida", required=True)
    a = ap.parse_args()
    os.makedirs(a.salida, exist_ok=True)
    D = a.datos

    # Fecha de corte por fuente y último mes completo
    cortes = {}
    for k, *_ in DELITOS:
        p = os.path.join(D, f"qc_corte_{k}.csv")
        if os.path.exists(p):
            r = leer(p)[0]
            cortes[k] = r["ultima"][:10]
    # Población (para tasas)
    pob = {}
    p = os.path.join(D, "poblacion_municipal.csv")
    if os.path.exists(p):
        for r in leer(p):
            pob[(r["cod_muni"].zfill(5), int(r["anio"]))] = int(r["poblacion"])
    pob_nal = collections.Counter()
    for (c, y), v in pob.items():
        pob_nal[y] += v

    def pob_anio(cod, y):
        if not pob:
            return None
        ys = [yy for (cc, yy) in pob if cc == cod] if cod else list(pob_nal)
        if not ys:
            return None
        yy = min(max(y, min(ys)), max(ys))
        return pob.get((cod, yy)) if cod else pob_nal[yy]

    mensual, municipal, nombres = {}, {}, {}
    for k, arch, col, etq in DELITOS:
        p = os.path.join(D, arch + ".csv")
        if not os.path.exists(p):
            continue
        m = collections.Counter(); mm = collections.defaultdict(collections.Counter)
        for r in leer(p):
            mes = (r.get("mes") or "")[:7]
            if not mes:
                continue
            v = num(r.get(col))
            m[mes] += v
            cod = (r.get("cod_muni") or "").split(".")[0].zfill(5)
            mm[cod][mes] += v
            nombres.setdefault(cod, (r.get("municipio", "").title(), r.get("departamento", "").title()))
        mensual[k], municipal[k] = m, mm

    # último mes completo: el mes de la fecha de corte cuenta solo si el corte es el último día
    def ultimo_completo(k):
        c = cortes.get(k)
        if not c:
            return max(mensual[k])
        d = dt.date.fromisoformat(c)
        sig = d + dt.timedelta(days=1)
        return c[:7] if sig.month != d.month else mes_ant(c[:7])

    filas_mensual, kpis, gob_rows, mapa = [], [], [], []
    for k, arch, col, etq in DELITOS:
        if k not in mensual:
            continue
        um = ultimo_completo(k)
        for mes, v in sorted(mensual[k].items()):
            if mes <= um:
                filas_mensual.append({"delito": k, "mes": mes, "valor": round(v, 1), "gobierno": gobierno(mes)})
        y = int(um[:4]); n = int(um[5:7])
        ytd = sum(v for mes, v in mensual[k].items() if mes[:4] == str(y) and mes <= um)
        ytd_ant = sum(v for mes, v in mensual[k].items() if mes[:4] == str(y - 1) and mes <= f"{y-1}-{n:02d}")
        u12 = sum(mensual[k].get(mes_ant(um, i), 0) for i in range(12))
        p12 = sum(mensual[k].get(mes_ant(um, i + 12), 0) for i in range(12))
        kpis.append({"delito": k, "etiqueta": etq, "ultimo_mes": um, "corte_fuente": cortes.get(k, ""),
                     "valor_mes": round(mensual[k].get(um, 0), 1), "valor_mes_anio_ant": round(mensual[k].get(mes_ant(um, 12), 0), 1),
                     "ytd": round(ytd, 1), "ytd_anio_ant": round(ytd_ant, 1),
                     "var_ytd_pct": round(100 * (ytd / ytd_ant - 1), 1) if ytd_ant else None,
                     "ult12": round(u12, 1), "prev12": round(p12, 1),
                     "var_12m_pct": round(100 * (u12 / p12 - 1), 1) if p12 else None})
        # comparación por gobiernos: promedio mensual y tasa anual por 100.000
        porg = collections.defaultdict(list)
        for mes, v in mensual[k].items():
            g = gobierno(mes)
            if g and mes <= um:
                porg[g].append((mes, v))
        for g, a_, b_ in GOBIERNOS:
            xs = sorted(porg.get(g, []))
            if not xs:
                continue
            meses = len(xs); tot = sum(v for _, v in xs)
            prom = tot / meses
            # mismos primeros N meses que lleva el gobierno actual
            n_act = len(porg.get(GOBIERNOS[-1][0], []))
            primeros = sum(v for _, v in xs[:n_act]) if n_act else None
            pm = [pob_anio(None, int(mes[:4])) for mes, _ in xs]
            tasa = (sum(v / p for (mes, v), p in zip(xs, pm) if p) / meses * 12 * 1e5) if all(pm) and pob else None
            gob_rows.append({"delito": k, "gobierno": g, "desde": a_, "hasta": xs[-1][0], "meses": meses,
                             "total": round(tot, 1), "promedio_mensual": round(prom, 1),
                             "tasa_anual_100k": round(tasa, 2) if tasa else None,
                             "primeros_n_meses": n_act, "total_primeros_n": round(primeros, 1) if primeros is not None else None})
    # municipios: últimos 12 meses de homicidio, extorsión y secuestro, con tasa
    um_h = ultimo_completo("homicidio")
    y_h = int(um_h[:4])
    cods = set()
    for k in ("homicidio", "extorsion", "secuestro", "masacres", "fuerza_publica", "hurto_personas"):
        cods |= set(municipal.get(k, {}))
    for cod in sorted(cods):
        if not cod.strip("0"):
            continue
        r = {"cod_muni": cod, "municipio": nombres.get(cod, ("", ""))[0], "departamento": nombres.get(cod, ("", ""))[1]}
        for k in ("homicidio", "extorsion", "secuestro", "masacres", "fuerza_publica", "hurto_personas"):
            mm = municipal.get(k, {}).get(cod, {})
            r[k + "_12m"] = round(sum(mm.get(mes_ant(um_h, i), 0) for i in range(12)), 1)
            r[k + "_prev12m"] = round(sum(mm.get(mes_ant(um_h, i + 12), 0) for i in range(12)), 1)
        pp = pob_anio(cod, y_h)
        r["poblacion"] = pp
        r["tasa_homicidio_100k"] = round(r["homicidio_12m"] / pp * 1e5, 1) if pp else None
        r["tasa_extorsion_100k"] = round(r["extorsion_12m"] / pp * 1e5, 1) if pp else None
        mapa.append(r)
    # coca detectada (hectáreas por año), nacional y por municipio
    coca_nal, coca_mun = [], []
    p = os.path.join(D, "seg_coca_detectada.csv")
    if os.path.exists(p):
        tot = collections.Counter()
        for r in leer(p):
            anios = {int(c.strip("_")): num(v) for c, v in r.items() if c.strip("_").isdigit()}
            for y, v in anios.items():
                tot[y] += v
            ult = max(y for y in anios if anios[y] > 0) if any(anios.values()) else None
            coca_mun.append({"cod_muni": (r.get("codmpio") or "").split(".")[0].zfill(5), "municipio": (r.get("municipio") or "").title(),
                             "departamento": (r.get("departamento") or "").title(),
                             **{f"ha_{y}": round(v, 1) for y, v in sorted(anios.items()) if y >= 2018}})
        coca_nal = [{"anio": y, "hectareas": round(v)} for y, v in sorted(tot.items())]

    def guardar(nombre, filas):
        with open(os.path.join(a.salida, nombre + ".json"), "w", encoding="utf-8") as f:
            json.dump(filas, f, ensure_ascii=False, separators=(",", ":"))
        print(nombre, len(filas))
    guardar("kpis", kpis); guardar("mensual", filas_mensual); guardar("gobiernos", gob_rows)
    guardar("municipios", mapa); guardar("coca_nacional", coca_nal); guardar("coca_municipios", coca_mun)


if __name__ == "__main__":
    main()
