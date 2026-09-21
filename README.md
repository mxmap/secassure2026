# Email Provider Dependencies and Email Security in Municipalities Across Germany, Austria, and Switzerland

[![CI](https://github.com/mxmap/secassure2026/actions/workflows/ci.yml/badge.svg)](https://github.com/mxmap/secassure2026/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/mxmap/secassure2026/branch/main/graph/badge.svg)](https://codecov.io/gh/mxmap/secassure2026)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/downloads/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with pyright](https://img.shields.io/badge/type%20checker-pyright-yellow.svg)](https://github.com/microsoft/pyright)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Automated pipeline to collect email domains, classify email providers, and analyze email security for municipalities in Germany, Austria, and Switzerland.

## Pipeline

1. **Resolve** — Collect municipality websites from official registries and Wikidata, scrape for email addresses, validate via DNS/MX, and produce a municipality-to-domain mapping.
2. **Classify** — Fingerprint DNS records (MX, SPF, autodiscover, SMTP banners, ASN) to determine email provider (Microsoft 365, Google Workspace, AWS, domestic hosting, etc.).
3. **Scan** — Evaluate DANE/DNSSEC and email authentication (SPF, DMARC) per domain via a Kotlin/Docker scanner.

## How to run

Install [`uv`](https://docs.astral.sh/uv/getting-started/installation/), then:

```bash
uv sync                               # install deps
uv run resolve <ch|de|at|--all>       # Stage 1: resolve email domains
uv run classify <ch|de|at>            # Stage 2: classify providers
uv run scan <ch|de|at>                # Stage 3: DANE/SPF/DMARC (requires Docker)
```

Common flags: `--dry-run`, `-v`, `--no-cache`. See `uv run <cmd> --help`.

> [!IMPORTANT]
> This tool requires unrestricted outbound port 25 (SMTP). Most residential ISPs and laptops block this.
> For best results, run from a cloud VM with port 25 access opened.

## Validation

The classifier is validated via bounce probing — a separate, manual process (not part of the pipeline above) that sends probe emails to a stratified sample of municipalities and parses the resulting NDRs to identify the actual backend MTA. The validation tooling and data is maintained in a separate repository.

## Output files

Results are written to `output/`:

| Stage | Files | Description |
|-------|-------|-------------|
| Resolve | `domains/domains_{cc}.json` | Minimal: code, name, region, website, email domain |
| | `domains/domains_{cc}_detailed.json` | Full: includes source, confidence, flags |
| | `domains/domains_{cc}_review.json` | Low-confidence entries for manual review |
| Classify | `providers/providers_{cc}.json` | Provider, confidence, evidence signals, gateway |
| | `providers/providers_{cc}.min.json` | Minified for frontend consumption |
| Scan | `security/security_{cc}.json` | DANE, SPF, DMARC assessment per municipality |
| Export | `export.xlsx` | Combined workbook: all municipalities + statistics |

## Maps

Interactive Leaflet maps visualizing email provider distribution and security posture are available in the `maps/` directory. 

To view them:

```bash
python3 -m http.server              # from the project root
```

Now open http://localhost:8000/maps/ in a browser.

## Paper

This repository accompanies the following paper:

> Bischof, M., Huser, D., Ochsner, A., Petrlic, R., Portmann, E.: Email provider dependencies and email security in municipalities across Germany, Austria, and Switzerland. In: Computer Security. ESORICS 2026 International Workshops (SecAssure 2026). Lecture Notes in Computer Science, Springer Nature Switzerland (2026), to appear

**[PDF (accepted manuscript)](https://papers.mxmap-project.org/secassure2026.pdf)** — the Version of Record will be available from Springer once published. The manuscript is not covered by this repository's MIT license; its use is subject to Springer Nature's [Accepted Manuscript terms of use](https://www.springernature.com/gp/open-research/policies/accepted-manuscript-terms).

```bibtex
@inproceedings{bischof2026email,
  author    = {Bischof, Mario and Huser, David and Ochsner, Alexej and Petrlic, Ronald and Portmann, Edy},
  title     = {Email Provider Dependencies and Email Security in Municipalities Across {Germany}, {Austria}, and {Switzerland}},
  booktitle = {Computer Security. ESORICS 2026 International Workshops (SecAssure 2026)},
  series    = {Lecture Notes in Computer Science},
  publisher = {Springer Nature Switzerland},
  year      = {2026},
  note      = {to appear}
}
```

## Origins

This project builds on [MXmap](https://mxmap.ch) ([source](https://github.com/davidhuser/mxmap)), a solo project by David Huser mapping the email providers of ~2,100 Swiss municipalities, which spawned around ten country-specific forks across Europe. SecAssure2026 extends that work to all of Germany, Austria and Switzerland and adds a dedicated email-security scanning stage.

## License

First-party code in this repository is released under the **MIT License** — see [LICENSE](LICENSE).

Third-party subtrees retain their own licenses. Notably, `src/security_test/scanner/testssl.sh/` is vendored under **GPL-2.0** (see the `LICENSE` file in that directory). Redistribution of the repository as a combined binary artifact (e.g., a single Docker image) is therefore constrained by GPL-2.0 terms; the MIT grant applies to the first-party Python code.
