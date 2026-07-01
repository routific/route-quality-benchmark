# Third-party software

The solver harnesses under [`solvers/`](solvers/) package third-party open-source solvers. Each solver
is **pulled or built at runtime** (via Docker) and is **not redistributed** in this repository; it
remains under its own upstream license, listed here. The adapter/harness code in this repo is
Apache-2.0 (see [`LICENSE`](LICENSE)).

| Solver | Upstream | License | Version pinned here |
|---|---|---|---|
| **VROOM** | [VROOM-Project/vroom](https://github.com/VROOM-Project/vroom) | BSD-2-Clause | image `ghcr.io/vroom-project/vroom-docker:v1.15.0` |
| **PyVRP** | [PyVRP/PyVRP](https://github.com/PyVRP/PyVRP) | MIT | `pyvrp>=0.11,<0.12` |
| **OR-Tools** | [google/or-tools](https://github.com/google/or-tools) | Apache-2.0 | `ortools>=9.11,<9.13` |
| **jsprit** | [graphhopper/jsprit](https://github.com/graphhopper/jsprit) | Apache-2.0 | `jsprit-core:1.9.0-beta.12` |

### jsprit service — additional build/runtime dependencies

The jsprit HTTP service (`solvers/jsprit/`) also uses:

| Library | Purpose | License |
|---|---|---|
| [Javalin](https://github.com/javalin/javalin) `6.3.0` | HTTP server | Apache-2.0 |
| [Jackson Databind](https://github.com/FasterXML/jackson-databind) `2.16.1` | JSON | Apache-2.0 |
| [SLF4J Simple](https://www.slf4j.org/) `2.0.9` | logging | MIT |

### Data

Travel-time matrices in the datasets are a **Produced Work** over **OpenStreetMap** data (ODbL); see
[`NOTICE`](NOTICE) for the required attribution.
