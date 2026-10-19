# Reglas de limpieza del valor de los contratos (SECOP II)

Versión 1 · 19 de octubre de 2026 · Observatorio de datos, Ideas para Gobernar

## Por qué hace falta

SECOP II (conjunto `jbjy-vk9h`) trae valores de contrato digitados por cada entidad, sin validación. En la serie 2022-2026 hay contratos de "mínima cuantía" registrados por 6.453 billones de pesos, más de diez veces el Presupuesto General de la Nación. Una sola cifra así distorsiona cualquier suma: en 2024 la suma bruta da 6.641 billones, cuando el valor plausible ronda 125 billones.

## Principio

1. **Los conteos no se tocan.** Todos los contratos cuentan como contratos.
2. **Solo se excluye el valor** de los contratos que cumplen una regla objetiva. Se publica siempre el valor bruto junto al valor limpio y el número de contratos excluidos.
3. **Cada exclusión queda listada** con su regla, su enlace al SECOP y su objeto, en `datos/qc/qc_excluidos_por_regla.csv`, para que cualquiera pueda auditarla.

## Reglas

| Regla | Condición | Razón |
|---|---|---|
| R1 | Valor nulo o menor o igual a cero | No es un valor de contrato. |
| R2 | Modalidad "Mínima cuantía" con valor mayor a 200 millones | Por ley la mínima cuantía no supera el 10 % de la menor cuantía, es decir, 100 SMMLV (142 millones en 2025). 200 millones está por encima del tope de cualquier año del periodo. |
| R3 | Valor de 10 billones o más | Ningún contrato individual del periodo alcanza esa cifra; equivale a cerca del 2 % del presupuesto nacional. |
| R4 | Valor de 100.000 millones o más y objeto con "servicios profesionales" o "apoyo a la gestión" | Son contratos de servicios personales; un valor así es un error de digitación. |
| R5 | Valor de 100.000 millones o más, con valor facturado positivo y más de 500 veces menor que el valor | Patrón típico de error de unidades (se digitaron ceros de más). |

## Lo que la limpieza no resuelve

- Contratos grandes reales pero atípicos (concesiones a 20 años, adquisición de aeronaves, operaciones de crédito público) se conservan. Para análisis de "compras" conviene separar las operaciones de crédito público y las concesiones.
- Errores pequeños por debajo de los umbrales. Por eso, para comparar entidades se usan medianas y conteos, no solo sumas.
- La lista de contratos de 100.000 millones o más (`datos/qc/qc_contratos_valor_alto.csv`) se revisa a mano en cada edición; las correcciones manuales se documentan aquí.

## Control de calidad por edición

1. Correr el flujo "Control de calidad" en GitHub.
2. Revisar `qc_excluidos_por_regla.csv`: confirmar que ninguna exclusión es un contrato real.
3. Revisar `qc_contratos_valor_alto.csv`: marcar errores que las reglas no capturan.
4. Segunda persona verifica los puntos 2 y 3 antes de publicar (doble revisión del protocolo).
