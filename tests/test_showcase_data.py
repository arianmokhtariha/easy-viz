"""The showcase dataset carries every planted pattern at its documented strength.

``gallery/data/INSIGHTS.md`` is the answer key of the showcase dataset. Its summary
table lists one measurable metric per row (``| ID | Pattern | Table | Metric |
Documented value |``). ``METRICS`` below says how each ID is measured on the
committed CSV files, and with what tolerance. The checks:

* the documented IDs and the measured IDs are exactly the same set (no
  undocumented check, no unchecked claim), and every documented value matches the
  measurement;
* the tables are one coherent business: keys are unique, foreign keys resolve, and
  the aggregates stored in ``customers`` and ``daily_metrics`` equal the orders;
* the committed CSV files are exactly what ``gallery/data/generate.py`` produces,
  so they were never edited by hand.
"""

import datetime as dt
import importlib.util
import math
import re
import sys
from collections.abc import Callable
from itertools import combinations
from pathlib import Path
from typing import NamedTuple

import numpy as np
import numpy.typing as npt
import polars as pl
import pytest
from scipy.stats import f_oneway, gaussian_kde, rankdata

DATA = Path(__file__).resolve().parents[1] / "gallery" / "data"
INSIGHTS = DATA / "INSIGHTS.md"
GENERATOR = DATA / "generate.py"
TABLE_NAMES = (
    "customers",
    "products",
    "orders",
    "daily_metrics",
    "listings",
    "churn_scores",
    "checkout_test",
)
REGENERATE = "Re-run `uv run python gallery/data/generate.py`"
SUMMARY_HEADER = ("ID", "Pattern", "Table", "Metric", "Documented value")

Tables = dict[str, pl.DataFrame]
FloatArray = npt.NDArray[np.float64]


# --- Measurements --------------------------------------------------------------------


def values(frame: pl.DataFrame, column: str) -> FloatArray:
    return frame[column].cast(pl.Float64).to_numpy()


def mean(frame: pl.DataFrame, column: str) -> float:
    return float(values(frame, column).mean())


def pearson(frame: pl.DataFrame, x: str, y: str) -> float:
    return float(np.corrcoef(values(frame, x), values(frame, y))[0, 1])


def simpson_overall_r(t: Tables) -> float:
    return pearson(t["listings"], "price", "conversion_rate")


def simpson_min_within_region_r(t: Tables) -> float:
    groups = t["listings"].partition_by("region")
    return min(pearson(g, "price", "conversion_rate") for g in groups)


def top20_profit_share(t: Tables) -> float:
    """Share of total profit from the top 20 % of ordering customers."""
    profit = (
        t["orders"]
        .group_by("customer_id")
        .agg(pl.col("profit").sum())
        .sort("profit", descending=True)["profit"]
        .to_numpy()
    )
    top = round(0.2 * profit.size)
    return float(profit[:top].sum() / profit.sum())


KDE_BANDWIDTH_DAYS = 0.3  # wider than the 0.1-day rounding step of delivery_days
MODE_MIN_HEIGHT = 0.05  # ignore bumps below 5 % of the highest peak


def kde_modes(days: FloatArray) -> int:
    """Count the peaks of a kernel density estimate with a fixed bandwidth."""
    kde = gaussian_kde(days, bw_method=KDE_BANDWIDTH_DAYS / days.std(ddof=1))
    density = kde(np.linspace(days.min(), days.max(), 400))
    inner = density[1:-1]
    peaks = (
        (inner > density[:-2])
        & (inner >= density[2:])
        & (inner > MODE_MIN_HEIGHT * density.max())
    )
    return int(peaks.sum())


def delivery_modes_overall(t: Tables) -> float:
    return kde_modes(values(t["orders"], "delivery_days"))


def delivery_modes_max_within(t: Tables) -> float:
    groups = t["orders"].partition_by("warehouse")
    return max(kde_modes(values(g, "delivery_days")) for g in groups)


def delivery_median(warehouse: str) -> Callable[[Tables], float]:
    def measure(t: Tables) -> float:
        hub = t["orders"].filter(pl.col("warehouse") == warehouse)
        return float(np.median(values(hub, "delivery_days")))

    return measure


def window(t: Tables, year: int, first_month: int, last_month: int) -> pl.DataFrame:
    date = pl.col("date")
    return t["daily_metrics"].filter(
        (date.dt.year() == year) & date.dt.month().is_between(first_month, last_month)
    )


def orders_ratio(first_month: int, last_month: int) -> Callable[[Tables], float]:
    """Mean daily orders in 2025 over the same months of 2024."""

    def measure(t: Tables) -> float:
        new, old = (window(t, y, first_month, last_month) for y in (2025, 2024))
        return mean(new, "orders") / mean(old, "orders")

    return measure


def aov_ratio(t: Tables) -> float:
    """Average order value, April-October 2025 over April-October 2024."""
    new, old = (window(t, y, 4, 10) for y in (2025, 2024))
    new_aov = values(new, "revenue").sum() / values(new, "orders").sum()
    old_aov = values(old, "revenue").sum() / values(old, "orders").sum()
    return float(new_aov / old_aov)


def season_peak_ratio(t: Tables) -> float:
    """Mean daily orders in November-December over June-August, both years."""
    month = pl.col("date").dt.month()
    daily = t["daily_metrics"]
    peak = mean(daily.filter(month >= 11), "orders")
    return peak / mean(daily.filter(month.is_between(6, 8)), "orders")


def black_friday(year: int) -> dt.date:
    first = dt.date(year, 11, 1)
    thursday = first + dt.timedelta(days=(3 - first.weekday()) % 7)
    return thursday + dt.timedelta(weeks=3, days=1)


def black_friday_ratio(t: Tables) -> float:
    """Orders on Black Friday over the mean of the 28 days before; mean of years."""
    daily = t["daily_metrics"].sort("date")
    orders = values(daily, "orders")
    ratios = []
    for year in (2024, 2025):
        position = daily["date"].to_list().index(black_friday(year))
        ratios.append(orders[position] / orders[position - 28 : position].mean())
    return float(np.mean(ratios))


def black_friday_weekend_by_category(t: Tables) -> pl.DataFrame:
    """Orders and mean order revenue per category, Black Friday to Cyber Monday 2025.

    Rows are ranked by mean revenue, highest first.
    """
    friday = black_friday(2025)
    weekend = t["orders"].filter(
        pl.col("order_date").is_between(friday, friday + dt.timedelta(days=3))
    )
    return (
        weekend.join(t["products"], on="product_id")
        .group_by("category")
        .agg(pl.len().alias("orders"), pl.col("revenue").mean())
        .sort("revenue", descending=True)
    )


def office_weekend_rank(t: Tables) -> float:
    ranked = black_friday_weekend_by_category(t)["category"].to_list()
    return float(ranked.index("Office") + 1)


def office_weekend_orders(t: Tables) -> float:
    weekend = black_friday_weekend_by_category(t)
    return float(weekend.filter(pl.col("category") == "Office")["orders"].item())


def weekend_categories_below_30(t: Tables) -> float:
    return float((black_friday_weekend_by_category(t)["orders"] < 30).sum())


def weekday_ratio(t: Tables) -> float:
    """Busiest weekday's mean daily orders over the quietest weekday's."""
    by_day = (
        t["daily_metrics"]
        .group_by(pl.col("date").dt.weekday())
        .agg(pl.col("orders").mean())
    )
    orders = values(by_day, "orders")
    return float(orders.max() / orders.min())


def category_shares(t: Tables) -> FloatArray:
    revenue = (
        t["orders"]
        .join(t["products"], on="product_id")
        .group_by("category")
        .agg(pl.col("revenue").sum())
    )
    shares = values(revenue, "revenue")
    return np.sort(shares / shares.sum())[::-1]


def top3_category_share(t: Tables) -> float:
    return float(category_shares(t)[:3].sum())


def categories_below_2pct(t: Tables) -> float:
    return float((category_shares(t) < 0.02).sum())


def gifts_weeks_without_orders(t: Tables) -> float:
    """Weeks (Monday to Sunday) between the first and last order with no Gifts order."""
    week = pl.col("order_date").dt.truncate("1w")  # polars weeks start on Monday
    span = (week.max() - week.min()).dt.total_days() // 7 + 1
    weeks: int = t["orders"].select(span).item()
    gifts = (
        t["orders"]
        .join(t["products"], on="product_id")
        .filter(pl.col("category") == "Gifts")
        .select(week)["order_date"]
    )
    return float(weeks - gifts.n_unique())


BLOCKS = {
    "engagement": (
        "sessions_per_month",
        "pages_per_session",
        "app_opens_per_month",
        "email_click_rate",
    ),
    "spending": ("orders_12m", "spend_12m", "items_per_order"),
    "service": (
        "support_tickets_12m",
        "returns_12m",
        "late_deliveries_12m",
        "satisfaction_score",
    ),
}


def block_correlations(t: Tables) -> tuple[list[float], list[float]]:
    """|Pearson r| of every column pair inside a block, and between blocks."""
    block_of = {c: b for b, cols in BLOCKS.items() for c in cols}
    within: list[float] = []
    between: list[float] = []
    for a, b in combinations(block_of, 2):
        r = abs(pearson(t["customers"], a, b))
        (within if block_of[a] == block_of[b] else between).append(r)
    return within, between


def blocks_median_within(t: Tables) -> float:
    return float(np.median(block_correlations(t)[0]))


def blocks_min_within(t: Tables) -> float:
    return min(block_correlations(t)[0])


def blocks_max_between(t: Tables) -> float:
    return max(block_correlations(t)[1])


def income_missing_shares(t: Tables) -> dict[str, float]:
    shares = (
        t["customers"]
        .group_by("segment")
        .agg(pl.col("annual_income").is_null().mean().alias("missing"))
    )
    return dict(zip(shares["segment"], shares["missing"], strict=True))


def student_income_missing(t: Tables) -> float:
    return income_missing_shares(t)["Student"]


def max_other_income_missing(t: Tables) -> float:
    shares = income_missing_shares(t)
    return max(v for k, v in shares.items() if k != "Student")


def price_typo_mask(orders: pl.DataFrame) -> npt.NDArray[np.bool_]:
    """Rows whose unit_price is far above the price implied by their revenue."""
    implied = values(orders, "revenue") / (
        values(orders, "quantity") * (1 - values(orders, "discount"))
    )
    return values(orders, "unit_price") / implied > 10


def price_typo_share_pct(t: Tables) -> float:
    return float(price_typo_mask(t["orders"]).mean() * 100)


def churn_auc(t: Tables) -> float:
    """Area under the ROC curve, from the Mann-Whitney rank sum."""
    scores = t["churn_scores"]
    churned = scores["churned_90d"].to_numpy() == 1
    ranks = rankdata(values(scores, "churn_probability"))
    n_pos, n_neg = churned.sum(), (~churned).sum()
    return float((ranks[churned].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def top_decile(t: Tables) -> pl.DataFrame:
    # customer_id breaks ties: polars' sort does not keep the order of equal values.
    scores = t["churn_scores"].sort(
        "churn_probability", "customer_id", descending=[True, False]
    )
    return scores.head(scores.height // 10)


def churn_top_decile_predicted(t: Tables) -> float:
    return mean(top_decile(t), "churn_probability")


def churn_top_decile_actual(t: Tables) -> float:
    return mean(top_decile(t), "churned_90d")


def variant_values(t: Tables) -> dict[str, FloatArray]:
    test = t["checkout_test"]
    return {
        v: values(test.filter(pl.col("variant") == v), "order_value")
        for v in sorted(test["variant"].unique())
    }


def checkout_max_lift(t: Tables) -> float:
    means = [x.mean() for x in variant_values(t).values()]
    return float(max(means) / min(means) - 1)


def checkout_anova_p(t: Tables) -> float:
    return float(f_oneway(*variant_values(t).values()).pvalue)


BOOTSTRAP_RESAMPLES = 4_000


def checkout_cis_overlap(t: Tables) -> float:
    """1 if the 95 % bootstrap intervals of every pair of variant means overlap."""
    rng = np.random.default_rng(0)
    intervals = []
    for x in variant_values(t).values():
        means = rng.choice(x, size=(BOOTSTRAP_RESAMPLES, x.size)).mean(axis=1)
        intervals.append(np.quantile(means, [0.025, 0.975]))
    overlap = all(
        min(a[1], b[1]) > max(a[0], b[0]) for a, b in combinations(intervals, 2)
    )
    return float(overlap)


class Metric(NamedTuple):
    measure: Callable[[Tables], float]
    tolerance: float  # documented values have 2 decimals; counts must be exact


TWO_DECIMALS = 0.01

METRICS: dict[str, Metric] = {
    "simpson-overall-r": Metric(simpson_overall_r, TWO_DECIMALS),
    "simpson-min-within-region-r": Metric(simpson_min_within_region_r, TWO_DECIMALS),
    "pareto-top20-profit-share": Metric(top20_profit_share, TWO_DECIMALS),
    "delivery-modes-overall": Metric(delivery_modes_overall, 0),
    "delivery-modes-max-within-warehouse": Metric(delivery_modes_max_within, 0),
    "delivery-median-north-hub": Metric(delivery_median("North hub"), TWO_DECIMALS),
    "delivery-median-south-hub": Metric(delivery_median("South hub"), TWO_DECIMALS),
    "season-weekday-ratio": Metric(weekday_ratio, TWO_DECIMALS),
    "season-peak-vs-summer-ratio": Metric(season_peak_ratio, TWO_DECIMALS),
    "season-black-friday-ratio": Metric(black_friday_ratio, TWO_DECIMALS),
    "break-pre-orders-ratio": Metric(orders_ratio(1, 3), TWO_DECIMALS),
    "break-post-orders-ratio": Metric(orders_ratio(4, 10), TWO_DECIMALS),
    "break-post-aov-ratio": Metric(aov_ratio, TWO_DECIMALS),
    "longtail-top3-revenue-share": Metric(top3_category_share, TWO_DECIMALS),
    "longtail-categories-below-2pct": Metric(categories_below_2pct, 0),
    "longtail-gifts-weeks-without-orders": Metric(gifts_weeks_without_orders, 0),
    "blocks-median-within-abs-r": Metric(blocks_median_within, TWO_DECIMALS),
    "blocks-min-within-abs-r": Metric(blocks_min_within, TWO_DECIMALS),
    "blocks-max-between-abs-r": Metric(blocks_max_between, TWO_DECIMALS),
    "mnar-student-income-missing": Metric(student_income_missing, TWO_DECIMALS),
    "mnar-max-other-income-missing": Metric(max_other_income_missing, TWO_DECIMALS),
    "typo-unit-price-share-pct": Metric(price_typo_share_pct, TWO_DECIMALS),
    "churn-auc": Metric(churn_auc, TWO_DECIMALS),
    "churn-top-decile-predicted": Metric(churn_top_decile_predicted, TWO_DECIMALS),
    "churn-top-decile-actual": Metric(churn_top_decile_actual, TWO_DECIMALS),
    "checkout-max-lift": Metric(checkout_max_lift, TWO_DECIMALS),
    "checkout-anova-p": Metric(checkout_anova_p, TWO_DECIMALS),
    "checkout-cis-overlap": Metric(checkout_cis_overlap, 0),
    "smallgroups-office-weekend-rank": Metric(office_weekend_rank, 0),
    "smallgroups-office-weekend-orders": Metric(office_weekend_orders, 0),
    "smallgroups-weekend-categories-below-30": Metric(weekend_categories_below_30, 0),
}


# --- The answer key ------------------------------------------------------------------


def parse_summary(text: str) -> dict[str, float]:
    """Read ``ID -> documented value`` from the summary table of INSIGHTS.md.

    Raises ``ValueError`` when the table is missing, a row is malformed, a value
    is not a plain number, or an ID appears twice.
    """
    lines = text.splitlines()
    header = re.compile(r"^\|\s*" + r"\s*\|\s*".join(SUMMARY_HEADER) + r"\s*\|\s*$")
    start = next((i for i, line in enumerate(lines) if header.match(line)), None)
    if start is None:
        raise ValueError(f"no summary table with the header {list(SUMMARY_HEADER)}")
    documented: dict[str, float] = {}
    for line in lines[start + 2 :]:  # skip the header and the |---| separator
        if not line.startswith("|"):
            break
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != len(SUMMARY_HEADER):
            raise ValueError(f"summary row has {len(cells)} cells, not 5: {line!r}")
        metric_id, raw = cells[0].strip("`"), cells[-1]
        if not re.fullmatch(r"-?\d+(\.\d+)?", raw):
            raise ValueError(f"{metric_id}: documented value {raw!r} is not a number")
        if metric_id in documented:
            raise ValueError(f"{metric_id}: listed twice in the summary table")
        documented[metric_id] = float(raw)
    return documented


def check_documented(
    documented: dict[str, float], metrics: dict[str, Metric], tables: Tables
) -> list[str]:
    """List every disagreement between the answer key and the measurements."""
    problems = [
        f"INSIGHTS.md: '{i}' is documented but has no measurement. Add it to "
        f"METRICS in tests/test_showcase_data.py, or remove the row."
        for i in sorted(documented.keys() - metrics.keys())
    ]
    problems += [
        f"INSIGHTS.md: metric '{i}' is measured but not documented. Add a row to "
        f"the summary table."
        for i in sorted(metrics.keys() - documented.keys())
    ]
    for metric_id in sorted(documented.keys() & metrics.keys()):
        measured = metrics[metric_id].measure(tables)
        expected = documented[metric_id]
        if not abs(measured - expected) <= metrics[metric_id].tolerance + 1e-9:
            problems.append(
                f"INSIGHTS.md: '{metric_id}' documents {expected} but the data "
                f"measures {measured:.4f}. If the generator changed on purpose, "
                f"update the value (and its section); otherwise the generator lost "
                f"this pattern. {REGENERATE} after fixing it."
            )
    return problems


# --- Fixtures ------------------------------------------------------------------------


def load_tables() -> Tables:
    missing = [n for n in TABLE_NAMES if not (DATA / f"{n}.csv").is_file()]
    assert not missing, f"gallery/data: missing {missing}. {REGENERATE}."
    return {
        n: pl.read_csv(DATA / f"{n}.csv", try_parse_dates=True) for n in TABLE_NAMES
    }


@pytest.fixture(scope="module")
def tables() -> Tables:
    return load_tables()


# --- The answer key matches the data -------------------------------------------------


def test_every_documented_pattern_is_present_at_its_strength(tables: Tables) -> None:
    documented = parse_summary(INSIGHTS.read_text(encoding="utf-8"))
    problems = check_documented(documented, METRICS, tables)
    assert not problems, "\n" + "\n".join(problems)


def test_the_answer_key_check_fails_on_wrong_or_unmatched_rows(tables: Tables) -> None:
    text = (
        "| ID | Pattern | Table | Metric | Documented value |\n|---|---|---|---|---|\n"
        "| `a` | p | t | m | 0.50 |\n| `b` | p | t | m | 2 |\n| `c` | p | t | m | 1 |\n"
    )
    metrics = {
        "a": Metric(lambda _: 0.505, TWO_DECIMALS),  # within tolerance
        "b": Metric(lambda _: 1.0, 0),  # wrong value
        "d": Metric(lambda _: 1.0, 0),  # measured, not documented
    }
    problems = "\n".join(check_documented(parse_summary(text), metrics, tables))
    assert "'a'" not in problems
    assert "'b' documents 2.0 but the data measures 1.0000" in problems
    assert "'c' is documented but has no measurement" in problems
    assert "'d' is measured but not documented" in problems
    with pytest.raises(ValueError, match="not a number"):
        parse_summary(text.replace("| 2 |", "| ~2 |"))
    with pytest.raises(ValueError, match="listed twice"):
        parse_summary(text.replace("`c`", "`a`"))


# --- One coherent business -----------------------------------------------------------


def test_keys_are_unique_and_foreign_keys_resolve(tables: Tables) -> None:
    keys = {
        "customers": "customer_id",
        "products": "product_id",
        "orders": "order_id",
        "daily_metrics": "date",
        "churn_scores": "customer_id",
        "checkout_test": "checkout_id",
    }
    for name, key in keys.items():
        assert tables[name][key].is_unique().all(), f"{name}.{key} has duplicates."
    assert tables["listings"].select("product_id", "region").is_unique().all()
    references = [
        ("orders", "customer_id", "customers"),
        ("orders", "product_id", "products"),
        ("listings", "product_id", "products"),
        ("churn_scores", "customer_id", "customers"),
    ]
    for child, key, parent in references:
        orphans = set(tables[child][key]) - set(tables[parent][key])
        assert not orphans, (
            f"{child}.{key}: {len(orphans)} values missing from {parent}, e.g. "
            f"{sorted(orphans)[:3]}. Fix the generator; {REGENERATE}."
        )


def test_customer_aggregates_equal_their_2025_orders(tables: Tables) -> None:
    last_12m = (
        tables["orders"]
        .filter(pl.col("order_date").dt.year() == 2025)
        .group_by("customer_id")
        .agg(n=pl.len(), spend=pl.col("revenue").sum())
    )
    joined = tables["customers"].join(last_12m, on="customer_id", how="left")
    n = joined["n"].fill_null(0)
    spend = joined["spend"].fill_null(0.0)
    assert (joined["orders_12m"] == n).all(), (
        f"customers.orders_12m differs from the 2025 order count. {REGENERATE}."
    )
    assert np.allclose(values(joined, "spend_12m"), spend.to_numpy(), atol=0.011), (
        f"customers.spend_12m differs from the 2025 revenue. {REGENERATE}."
    )
    cap = joined["orders_12m"]
    assert (joined["returns_12m"] <= cap).all()
    assert (joined["late_deliveries_12m"] <= cap).all()


def test_every_customer_ordered_in_each_year_since_signing_up(tables: Tables) -> None:
    # INSIGHTS.md describes customers as the active base: everyone ordered in 2025
    # and in every earlier year of the data they were signed up for.
    years = {2024, 2025}
    ordered = set(
        tables["orders"]
        .select("customer_id", year=pl.col("order_date").dt.year())
        .unique()
        .iter_rows()
    )
    missing = [
        (customer, year)
        for customer, signup in tables["customers"]
        .select("customer_id", pl.col("signup_date").dt.year())
        .iter_rows()
        for year in years
        if year >= signup and (customer, year) not in ordered
    ]
    assert not missing, (
        f"{len(missing)} customer-years without an order, e.g. {missing[:3]}, but "
        f"INSIGHTS.md promises an active customer base. Fix the generator; "
        f"{REGENERATE}."
    )


def test_daily_metrics_equal_the_daily_order_totals(tables: Tables) -> None:
    daily = tables["daily_metrics"].sort("date")
    steps = daily["date"].diff().drop_nulls().dt.total_days()
    assert (steps == 1).all(), "daily_metrics must hold every calendar day once."
    totals = (
        tables["orders"]
        .group_by("order_date")
        .agg(n=pl.len(), revenue=pl.col("revenue").sum())
    )
    joined = daily.join(totals, left_on="date", right_on="order_date", how="left")
    assert (joined["orders"] == joined["n"].fill_null(0)).all(), (
        f"daily_metrics.orders differs from the orders per day. {REGENERATE}."
    )
    assert np.allclose(
        values(joined, "revenue"), joined["revenue_right"].fill_null(0.0), atol=0.011
    ), f"daily_metrics.revenue differs from the revenue per day. {REGENERATE}."


def test_orders_are_consistent_with_customers_products_and_prices(
    tables: Tables,
) -> None:
    orders = tables["orders"].join(tables["customers"], on="customer_id")
    early = orders.filter(pl.col("order_date") < pl.col("signup_date"))
    assert early.is_empty(), f"{early.height} orders predate the customer's signup."
    # Revenue always uses the true price. Planted typos store unit_price x100.
    typo = price_typo_mask(tables["orders"])
    o = tables["orders"]
    price = np.where(typo, values(o, "unit_price") / 100, values(o, "unit_price"))
    implied = values(o, "quantity") * price * (1 - values(o, "discount"))
    assert np.allclose(values(o, "revenue"), implied, atol=0.011), (
        "orders.revenue must equal quantity x unit_price x (1 - discount), apart "
        "from the planted x100 unit_price typos."
    )
    listed = tables["listings"].join(tables["products"], on="product_id")
    assert (listed["price"] == listed["list_price"]).all(), (
        "listings.price must equal the product's list_price."
    )


def test_churn_scores_cover_exactly_the_plus_members(tables: Tables) -> None:
    plus = tables["customers"].filter(pl.col("plan") == "Plus")["customer_id"]
    assert set(tables["churn_scores"]["customer_id"]) == set(plus), (
        f"churn_scores must score every Plus member and nobody else. {REGENERATE}."
    )


# --- The CSV files are the generator's output ----------------------------------------


def import_generator() -> Callable[[], Tables]:
    """Import gallery/data/generate.py by path (it is a script, not a package)."""
    spec = importlib.util.spec_from_file_location("showcase_generate", GENERATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses look their module up here
    spec.loader.exec_module(module)
    build: Callable[[], Tables] = module.build_tables
    return build


def test_committed_csvs_match_the_generator(tables: Tables) -> None:
    built = import_generator()()
    assert list(built) == list(TABLE_NAMES), f"generate.py builds {list(built)}."
    for name, fresh in built.items():
        stored = pl.read_csv(DATA / f"{name}.csv", schema_overrides=fresh.schema)
        hint = f"gallery/data/{name}.csv differs from generate.py's output"
        assert stored.columns == fresh.columns, f"{hint} (columns). {REGENERATE}."
        assert stored.height == fresh.height, f"{hint} (row count). {REGENERATE}."
        for column in fresh.columns:
            new, old = fresh[column], stored[column]
            assert new.is_null().equals(old.is_null()), f"{hint} ({column} nulls)."
            if new.dtype.is_float():
                same = np.allclose(
                    new.drop_nulls().to_numpy(),
                    old.drop_nulls().to_numpy(),
                    rtol=1e-6,
                    atol=0.011,  # numpy's last bit can differ between CPUs
                )
            else:
                same = new.equals(old)
            assert same, f"{hint} (column {column}). {REGENERATE}; never edit by hand."


def test_metric_functions_are_finite(tables: Tables) -> None:
    """A NaN would pass no comparison silently, but name the metric clearly."""
    broken = [i for i, m in METRICS.items() if not math.isfinite(m.measure(tables))]
    assert not broken, f"metrics that measure NaN or infinity: {broken}"
