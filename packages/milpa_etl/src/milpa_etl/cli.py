"""CLI unificada ``milpa-etl`` (README §9): delega en los módulos de R1 sin cambiar su comportamiento.

    milpa-etl fetch power|imerg|dem ...      milpa-etl curate|validate --zone ...
    milpa-etl ingest soil-csv --parcel P --file f.csv
    milpa-etl merge imerg --zone Z           milpa-etl build-demo | selftest | scan-privacy
    milpa-etl seed catalog --catalog catalogs/crops.yaml
    milpa-etl register zone|manifest|provenance ...

Los subcomandos que escriben en PostgreSQL (``register …``, ``seed …``, ``fetch dem``) usan la variable
``DATABASE_URL`` con el **rol propietario** (la ETL escribe ``prov/ref/geo``; la API no). La API de R3 no
importa este paquete: lo invoca como proceso (``api.adapters.etl_process``).
"""

from __future__ import annotations

import sys
from collections.abc import Callable

# (grupo, acción) -> (módulo con ``main``, subcomando que espera ese ``main`` o None)
_CORE = {
    ("fetch", "power"): "fetch-power",
    ("fetch", "imerg"): "fetch-imerg",
    ("ingest", "soil-csv"): "ingest-soil",
}
_CORE_SINGLE = {"curate", "validate", "build-demo", "selftest", "scan-privacy"}
_USAGE = __doc__ or ""


def _run(main: Callable[..., int | None], argv: list[str], *, via_sys_argv: bool) -> int:
    if via_sys_argv:  # módulos de R1 cuyo main() lee sys.argv
        old = sys.argv
        sys.argv = ["milpa-etl", *argv]
        try:
            code = main()
        finally:
            sys.argv = old
    else:
        code = main(argv)
    return int(code or 0)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):  # consolas Windows (cp1252) no imprimen «≈», «±»…
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help"}:
        print(_USAGE)
        return 0
    from milpa_etl import core

    head = args[0]
    if head in _CORE_SINGLE:
        return _run(core.main, args, via_sys_argv=False)
    if head == "check-catalog":
        return _run(core.main, args, via_sys_argv=False)
    if len(args) >= 2 and (head, args[1]) in _CORE:
        return _run(core.main, [_CORE[(head, args[1])], *args[2:]], via_sys_argv=False)
    rest = args[2:]
    if head == "fetch" and args[1:2] == ["dem"]:
        from milpa_etl.loaders import dem

        return _run(dem.main, rest, via_sys_argv=True)
    if head == "merge" and args[1:2] == ["imerg"]:
        from milpa_etl import imerg

        return _run(imerg.main, ["merge", *rest], via_sys_argv=False)
    if head == "seed" and args[1:2] == ["catalog"]:
        from milpa_etl.loaders import seed_catalog

        return _run(seed_catalog.main, rest, via_sys_argv=True)
    if head == "register" and args[1:2] == ["zone"]:
        from milpa_etl.loaders import register_zone

        return _run(register_zone.main, rest, via_sys_argv=True)
    if head == "register" and args[1:2] == ["manifest"]:
        from milpa_etl.loaders import load_manifest

        return _run(load_manifest.main, rest, via_sys_argv=True)
    if head == "register" and args[1:2] == ["provenance"]:
        from milpa_etl.loaders import register_provenance

        return _run(register_provenance.main, rest, via_sys_argv=True)
    print(f"Subcomando no reconocido: {' '.join(args[:2])}\n\n{_USAGE}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
