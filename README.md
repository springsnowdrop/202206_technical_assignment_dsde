# CREA technical assignment - data engineer / data scientist

The original brief is reproduced [at the end of this page](#original-brief).

| Part | Question | Answer |
|---|---|---|
| **1a** | Share of population covered by stations within 5, 10, 50 km and beyond, for the US, UK, Turkey, Thailand, the Philippines and India | [Results](#part-1a---population-covered-by-air-quality-monitoring-stations) · code in [`part1a/`](part1a) |
| **1b** (optional) | PM2.5 from CPCB for Kolkata and Lucknow, interactive 365-day running average since 2020 | [Results](#part-1b---pm25-in-kolkata-and-lucknow-cpcb) · code in [`part1b/`](part1b) |
| **2** | Stack to collect and serve air pollution data | [Answer](#part-2---architecture) |

## Part 1a - Population covered by air quality monitoring stations

![Share of population living within 5, 10, 50 km of a monitoring station](part1a/results/coverage.png)

Interactive version (hover for exact values): [`part1a/results/coverage.html`](part1a/results/coverage.html)
(download and open in a browser). Tables: [`part1a/results/coverage.csv`](part1a/results/coverage.csv),
[`coverage_cumulative.csv`](part1a/results/coverage_cumulative.csv); stations used:
[`stations_used.csv`](part1a/results/stations_used.csv).

Share of the population by distance to the nearest station (cumulative):

| Country | Stations | Population (M) | < 5 km | < 10 km | < 50 km | > 50 km |
|---|--:|--:|--:|--:|--:|--:|
| United Kingdom | 341 | 68 | 21% | 46% | 97% | 3% |
| United States | 3,283 | 352 | 19% | 44% | 94% | 6% |
| Turkey | 320 | 81 | 17% | 35% | 94% | 6% |
| Thailand | 228 | 76 | 17% | 30% | 88% | 12% |
| Philippines\* | 53 | 111 | 9% | 14% | 31% | 69% |
| India | 592 | 1,420 | 6% | 12% | 64% | 36% |

\* All 53 Philippine sites are PM2.5-only, almost all in Metro Manila, and most started in
2024-25 (sites named after barangay halls and road intersections, "Demo Unit" sensors, a
NASA calibration node). They look like an indicative sensor network rather than the national
regulatory network (DENR-EMB), which does not seem to be in OpenAQ. So the Philippine figures
describe the data available, not the country's monitoring network.

**Takeaways**

- **UK and US:** about 45% of people live within 10 km of a station and 94-97% within 50 km.
  Monitoring follows population closely; the US has ~10× more stations than the UK for
  similar coverage.
- **Turkey and Thailand:** about a third within 10 km and ~90% within 50 km: sparser than
  the UK or US networks. Thailand has the largest share beyond 50 km (12%) of these four.
- **India** has about as many stations as Turkey and Thailand combined, for 9× their population:
  only 12% of Indians live within 10 km of a station and **36% (≈ 520 million people) live
  more than 50 km away from any station**. That is about 2.4 million people per station,
  against ~0.1-0.2 million in the US and UK.
- **Philippines:** the open data covers Metro Manila and nearby provinces only, leaving 69% of the population
  (≈ 76 million) more than 50 km from a station in the data.

**Sensitivity** (share within 5 / 10 / 50 km):

| Country | Stations | Baseline | + low-cost sensors | CREA's own station list |
|---|---|--:|--:|--:|
| United Kingdom | 341 → 475 | 21 / 46 / 97% | 26 / 54 / 98% | |
| United States | 3,283 → 4,829 | 19 / 44 / 94% | 25 / 51 / 95% | |
| Turkey | 320 → 332 | 17 / 35 / 94% | 18 / 35 / 94% | |
| Thailand | 228 → 469 | 17 / 30 / 88% | 21 / 37 / 94% | |
| Philippines | 53 → 61 | 9 / 14 / 31% | 10 / 16 / 37% | |
| India | 592 → 614 | 6 / 12 / 64% | 6 / 12 / 64% | 6 / 13 / 66% (603 stations) |

- Low-cost sensors add 7-8 points within 10 km in the UK, US and Thailand, where such
  networks are large; elsewhere they change little.
- For India, CREA's own station list (CPCB, from CREA's public bucket) gives almost the same
  result as OpenAQ (65.6% vs 63.6% within 50 km). That supports using OpenAQ as a stand-in
  for CREA's API.

### Method

[`part1a/coverage.py`](part1a/coverage.py)

1. **Population.** The GPWv4 2020 raster gives population *density* (persons per km² of land)
   on a 0.25° grid (~28 km cells). Each cell is split into 25 × 25 sub-cells (~1 km) that keep
   the cell's density. Sub-cells whose centre is outside the country's land are dropped
   (Natural Earth 1:10m boundaries minus lakes). This handles coasts, borders and big lakes:
   without the lakes, Chicago's or Manila's cells would count Lake Michigan or Laguna de Bay as
   inhabited, +3% population for the US and +5% for the Philippines. Each sub-cell holds
   density × its area on the sphere.
2. **Distance.** Great-circle distance from every sub-cell to the nearest station of the same
   country, using a KD-tree on 3-D unit vectors.
3. **Aggregation.** Population is summed into 0.1 km distance bins. That gives the four bands
   (< 5, 5-10, 10-50, > 50 km) and the cumulative curves.

The geometry is checked by [`part1a/test_coverage.py`](part1a/test_coverage.py) on a
synthetic case with a known answer (uniform density, one station): totals are exact and shares
within 5/10/50 km match πr²/area with < 1% mean error.

### Data sources and choices

- **Stations: OpenAQ instead of CREA's API.** The brief asks for CREA's platform
  (`api.energyandcleanair.org`), but the environment this was produced in could not reach it.
  The stations therefore come from the public [OpenAQ archive](https://registry.opendata.aws/openaq/)
  (`s3://openaq-data-archive`), one of the upstream sources CREA aggregates.
  [`part1a/stations.py`](part1a/stations.py) lists its ~56,000 locations, counts each one's
  reporting days per year since 2020, and reads its coordinates and parameters from its latest
  daily file. `python part1a/stations.py --source crea` pulls the same list from CREA's API
  instead (not run here, since the API was unreachable).
- **Which stations count.** A station is counted if it reported on ≥ 30 days in at least one
  year from 2022 to 2025. A single year would measure gaps in OpenAQ's feeds, not in the
  networks: its Turkish data stops in 2023 (202 stations in 2022, 2 in 2025) and its CPCB data
  has a gap in 2023-24 (347 stations in 2022, 7 in 2024, 550 in 2025).
- **Reference monitors only.** OpenAQ mixes regulatory monitors with low-cost sensors
  (PurpleAir, AirGradient, ...) without labelling them. Locations reporting particle counts,
  PM1, VOC or air pressure, or temperature/humidity without any gaseous pollutant, are treated
  as low-cost and excluded. The sensitivity table above shows what they would add.
- **Country of a station.** Natural Earth polygon; coastal sites up to ~5 km offshore take the
  nearest country, matched against all countries so a station in Windsor (Canada) is not
  counted for the US. Coverage only counts stations of the same country.
- **Cross-check with CREA's own data for India.** CREA publishes its India station table
  (612 CPCB stations) in its public bucket. `--source crea-india` uses it.

### Limitations

- At 0.25°, population is spread evenly within each ~28 km cell. Stations sit in cities, where
  people are concentrated within the cell, so the < 5 km and < 10 km shares are probably
  **underestimated**, more so for countries with large, dense cities. A finer population grid
  (GPW 30″, WorldPop, GHSL) would sharpen them; the 50 km figure is much less sensitive.
- "Covered" means "a station nearby", not that the station measures PM2.5 or that its data is
  good.
- Population is 2020 (GPWv4); the station networks are 2022-2025.

### Reproduce

```bash
pip install -r requirements.txt
python part1a/stations.py --source openaq   # ~20 min: crawls the OpenAQ archive (cached afterwards)
python part1a/coverage.py                   # ~1 min
python part1a/plot.py                       # HTML + PNG (PNG export needs Chrome for kaleido)
pytest part1a
```

## Part 1b - PM2.5 in Kolkata and Lucknow (CPCB)

![365-day running average of PM2.5 in Kolkata and Lucknow](part1b/results/pm25_running_average.png)

Interactive chart (hover, zoom, range slider, daily values on click): [`part1b/results/pm25_running_average.html`](part1b/results/pm25_running_average.html)
(download and open in a browser).

- **Collection** - [`part1b/ScrapeCPCB.py`](part1b/ScrapeCPCB.py) drives the
  [CPCB CAAQM portal](https://app.cpcbccr.com/ccr/#/caaqm-dashboard-all/caaqm-landing/data) with
  Selenium: for each station of Kolkata and Lucknow it selects PM2.5, a 24-hour average and
  1 Jan 2020 onwards, then exports the table to Excel. The 12 exports (6 stations per city,
  1 Jan 2020 - 26 Jun 2022) are in [`part1b/data/`](part1b/data).
- **Processing** - [`part1b/running_average.py`](part1b/running_average.py):
  1. the daily city value is the mean of the stations that reported that day (`None` = missing,
     ignored rather than counted as 0);
  2. the running average at date *d* is the mean of the 365 days ending on *d*. It is only shown
     when the whole window lies within the data (so the first point is 30 Dec 2020) and at
     least 75% of its days have data.
- **Result** - Lucknow's annual PM2.5 fell from ~99 µg/m³ (year to May 2021) to ~65-70 µg/m³ in
  2022; Kolkata stayed around 50-60 µg/m³. Both are 10-20 times the WHO annual guideline (5 µg/m³)
  and above India's NAAQS (40 µg/m³).

Changes from the first version of this part (`PlotCPCB.ipynb`, now replaced by the script):
the running average was plotted at the *start* of each 365-day window instead of its end;
stations were matched by row position, assuming all exports had identical dates; paths were
hard-coded to a home directory. The scraper also moved the *oldest* files of `~/Downloads`
instead of the newest ones; that is fixed, but the scraper itself could not be re-run here
(the CPCB portal is not reachable from this environment).

## Part 2 - Architecture

What I would use to collect and serve air pollution data, roughly in the order data flows:

| Layer | Choice | Why |
|---|---|---|
| **Collection** | One small Python *adapter* per source (CPCB, OpenAQ, EEA, AirNow, ...) that fetches, normalises to a common schema (`station, pollutant, unit, timestamp, value, source`) and upserts. Each adapter runs as a container job on a schedule (Cloud Run Jobs + Cloud Scheduler, or Airflow/Prefect once there are dependencies between jobs). | Sources fail independently and change often; isolating them keeps one broken portal from blocking the rest. Upserts on `(station, pollutant, timestamp)` make re-runs and backfills idempotent. |
| **Scraping technique** | Call the JSON API behind a portal with `requests`/`httpx` rather than drive a browser. Selenium/Playwright is the last resort. | The CPCB dashboard is an Angular app backed by an HTTP API: calling it directly is ~100x faster and much more robust than clicking through date pickers (which is what Part 1b's Selenium scraper does). |
| **Raw storage** | Raw responses kept as-is in object storage (GCS/S3), partitioned by source/date. | Parsing bugs can be fixed and re-run without re-scraping; it is also an audit trail. |
| **Database** | PostgreSQL with **TimescaleDB** (hypertable for measurements, continuous aggregates for hourly/daily/yearly means) and **PostGIS** (station locations, admin boundaries). BigQuery as an analytical copy if datasets get very large. | One database answers both time-series ("365-day running mean in Lucknow") and spatial ("population within 10 km of a station") questions; continuous aggregates keep dashboards fast without a separate cache. |
| **Quality control** | Checks in the ingestion step: units, physical ranges, duplicates, flat-lined sensors, stale sources; flags stored with the data rather than deleting values. Freshness alerts per source. | Monitoring data is noisy (e.g. the `None` days and negative values in CPCB/OpenAQ exports); users need to know what was removed and why. |
| **API** | **FastAPI** REST API (stations, measurements, aggregates; JSON/CSV; pagination; API keys and rate limits), containerised on Cloud Run behind a CDN cache. | Typed, self-documented (OpenAPI), async, easy to test. Most queries are repeated aggregates, so HTTP caching does most of the scaling work. |
| **Frontend** | React + Plotly (or Observable Plot) + MapLibre for the public dashboard; Dash/Streamlit for internal tools; static Plotly HTML / images for reports. | Interactive charts and maps like the ones in Part 1 come out of the same API, so analysts and the public see the same numbers. |
| **Ops** | Docker, GitHub Actions CI (unit tests on adapters with recorded fixtures, linting), Terraform for infrastructure, structured logs + Sentry. | Reproducible deployments; adapters are tested against saved responses so a source changing its format shows up as a failing test, not as silently missing data. |

For a small team I would start with the managed, scale-to-zero pieces (Cloud Run, Cloud SQL Postgres + extensions, GCS) and only add a queue (Pub/Sub, Kafka) or a workflow engine when the number of sources or the update frequency calls for it.

## Repository layout

```
part1a/
  common.py          countries, distance bands, Natural Earth boundaries
  stations.py        station locations (OpenAQ archive, CREA API, CREA India table)
  coverage.py        population by distance to the nearest station
  plot.py            chart (HTML + PNG)
  data/              station lists used (stations_*.csv)
  results/           coverage tables and charts
part1b/
  ScrapeCPCB.py      Selenium scraper for the CPCB portal
  running_average.py station average + 365-day running average + chart
  data/              CPCB exports (one .xlsx per station)
  results/           daily data, running averages, chart
data/                GPWv4 population density raster (provided with the assignment)
requirements.txt
```

## Original brief

<details>
<summary>Show the assignment text</summary>

### Technical Assignment

This is a technical assignment for the data engineer / data scientist position at CREA.

#### Part 1a - Data analysis and visualisation

We at CREA have developed an online system that collects air pollution data from a dozen sources globally. In this assignment, we would like you to extract and present some insights using this dataset. Namely, we would like you to present in a single graph (subplots/facets authorised):

- the share of population covered by stations within radii of 5, 10, 50km and beyond for US, UK, Turkey, Thailand, Philippines, India. Population data available here: [data/gpw_v4_population_density_rev11_2020_15_min.tif](data/gpw_v4_population_density_rev11_2020_15_min.tif).

You can use either R or Python for data analysis, and any library or platform to create charts, except Tableau and PowerBI. Code and results can be hosted on a Markdown document, Jupyter notebook, R markdown, simple code and image files, or interactive web page.

#### Part 1b (Optional) - Data scraping and visualisation

If you have no experience with geospatial data and find yourself struggling with Part 1a, you can work on Part 1b instead. If you have finished Part 1a, you can skip directly to Part 2.

Here is a portal to access India's air quality: [CPCB](https://app.cpcbccr.com/ccr/#/caaqm-dashboard-all/caaqm-landing/data)

Collect PM2.5 daily data for all stations located in Kolkata and Lucknow using code only, and provide an **interactive** 365-day running average chart for these two cities from 2020 onward, using stations average.

#### Part 2 - Architecture

What would be your suggested and/or favourite stack to collect and serve air pollution data to users? (e.g. regular scraping, backend, data storage, frontend). Please provide justification or explanation if you have any. Keep it short!

#### Comments

We are interested in the way you solve the problems, how you structure your code and how you present results. There is no particular trap but if you have any doubt or question, feel free to contact [me](hubert@energyandcleanair.org) directly.

#### Submission

Steps:

- fork this repository;
- push your code, results and answers;
- invite [me](hubert@energyandcleanair.org) as a collaborator on your repository once you are done.

If required, you can push your results to another platform and share the link(s) with me.

</details>
