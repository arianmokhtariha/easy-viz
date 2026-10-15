"""Generate the Fernway showcase dataset used by every gallery notebook.

Fernway is a fictional online home-and-lifestyle retailer with a paid membership,
Fernway Plus (free shipping, member prices). This script builds two years of its
data (2024-01-01 to 2025-12-31) as seven related tables and writes each one as
``<table>.csv`` next to this file. Everything comes from one seed, so every run
produces the same files.

Ten patterns are planted on purpose, each one chosen because a specific easy-viz
chart reveals it. ``INSIGHTS.md`` is the answer key, and
``tests/test_showcase_data.py`` checks that every pattern is present at its
documented strength and that the committed CSV files match this script's output.

Run with ``uv run python gallery/data/generate.py``.
"""

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt
import polars as pl

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]
BoolArray = npt.NDArray[np.bool_]
StrArray = npt.NDArray[np.str_]
DateArray = npt.NDArray[np.datetime64]

SEED = 20240101
OUT_DIR = Path(__file__).resolve().parent

# --- Calendar ----------------------------------------------------------------------
START = dt.date(2024, 1, 1)
END = dt.date(2025, 12, 31)
LAST_12M_START = dt.date(2025, 1, 1)  # customers' *_12m columns cover 2025
PRICE_RISE_DATE = dt.date(2025, 4, 1)
SCORE_DATE = dt.date(2025, 9, 30)  # the churn model scored Plus members on this day
SIGNUP_START = dt.date(2021, 1, 1)
ONE_DAY = np.timedelta64(1, "D")

# --- Sizes ---------------------------------------------------------------------------
N_CUSTOMERS = 4_000
N_PRODUCTS = 300
TARGET_ORDERS = 30_000  # expected size of the orders table

# --- Customers -----------------------------------------------------------------------
REGIONS = ("North", "South", "East", "West")
REGION_SHARES = (0.27, 0.23, 0.28, 0.22)
SEGMENTS = ("Consumer", "Student", "Small business")
SEGMENT_SHARES = (0.72, 0.14, 0.14)
CHANNELS = ("Organic search", "Paid social", "Referral", "Email", "Marketplace")
CHANNEL_SHARES = (0.32, 0.22, 0.14, 0.12, 0.20)
EARLY_SIGNUP_SHARE = 0.7  # signed up before 2024; the rest during 2024-2025
PLAN_STANDARD, PLAN_PLUS = "Standard", "Plus"
PLUS_LOGIT = -0.55  # about 37 % of customers are Plus members
PLUS_SPEND_EFFECT = 0.5  # bigger spenders join Plus more often

# Median annual income and its spread (log scale) per segment.
INCOME_MEDIAN = {"Consumer": 52_000.0, "Student": 17_000.0, "Small business": 70_000.0}
INCOME_SIGMA = {"Consumer": 0.45, "Student": 0.35, "Small business": 0.5}
# Missing-not-at-random: the chance of skipping the income question falls with
# income itself (a logistic curve centred on SKIP_INCOME_MID).
SKIP_INCOME_MID = 21_000.0
SKIP_INCOME_SCALE = 3_000.0

# Correlated blocks: each column follows its block's latent factor (engagement columns
# with correlation BLOCK_LOADING; spending comes from the orders, service below).
BLOCK_LOADING = 0.85
SPEND_SIGMA = 1.2  # spread of order frequency between customers (profit concentration)
PLUS_ORDER_BOOST = 1.3  # free shipping: members order more often
QTY_EXTRA = 0.6  # quantity = 1 + Poisson(QTY_EXTRA x exp(QTY_SPEND_EFFECT x spend)),
QTY_SPEND_EFFECT = 0.8
MAX_QUANTITY = 6  # capped here: nobody buys ten sofas in one order
# Service block: each yearly count is round(median x exp(SERVICE_EFFECT x factor)),
# where the factor follows the customer's service latent with SERVICE_LOADING.
SERVICE_MEDIANS = {
    "support_tickets_12m": 1.6,
    "returns_12m": 0.65,  # never more than the customer's orders
    "late_deliveries_12m": 0.8,  # never more than the customer's orders
}
SERVICE_EFFECT = 0.6  # how strongly service problems vary between customers
SERVICE_LOADING = 0.9  # how closely each count follows the service factor
SATISFACTION_MEAN = 7.3
SATISFACTION_EFFECT = 1.5  # points lost per standard deviation of service problems
SATISFACTION_NOISE = 0.6

# --- Products ------------------------------------------------------------------------
ADJECTIVES = (
    "Oak", "Linen", "Nordic", "Harbor", "Willow", "Slate",
    "Juniper", "Coastal", "Alder", "Meadow", "Ember", "Birch",
)  # fmt: skip
PRICE_SIGMA = 0.45  # spread of list prices inside a category (log scale)
COST_RATIO = (0.38, 0.62)  # unit_cost / list_price is drawn uniformly in this range
MIN_PRODUCTS_PER_CATEGORY = 6


@dataclass(frozen=True)
class Category:
    """A product category and the revenue share it is planted to reach."""

    name: str
    revenue_share: float  # long tail: target share of total revenue
    base_price: float  # typical list price
    nouns: tuple[str, ...]


CATEGORIES = (
    Category("Furniture", 0.22, 260.0, ("Sofa", "Armchair", "Coffee Table", "Desk")),
    Category("Kitchen", 0.18, 45.0, ("Pan", "Knife Set", "Kettle", "Mixing Bowl")),
    Category("Bedding", 0.14, 70.0, ("Duvet", "Pillow", "Sheet Set", "Throw")),
    Category("Lighting", 0.10, 80.0, ("Floor Lamp", "Pendant", "Desk Lamp")),
    Category("Rugs", 0.08, 150.0, ("Area Rug", "Runner", "Doormat")),
    Category("Decor", 0.06, 35.0, ("Vase", "Mirror", "Bookend")),
    Category("Bath", 0.05, 30.0, ("Towel Set", "Bath Mat", "Soap Dish")),
    Category("Storage", 0.04, 40.0, ("Basket", "Shelf", "Storage Box")),
    Category("Outdoor", 0.03, 120.0, ("Lounger", "Planter", "Parasol")),
    Category("Tableware", 0.017, 25.0, ("Plate Set", "Mug", "Serving Bowl")),
    Category("Textiles", 0.015, 35.0, ("Cushion", "Curtain", "Tablecloth")),
    Category("Wall art", 0.013, 60.0, ("Print", "Canvas", "Wall Clock")),
    Category("Office", 0.012, 90.0, ("Desk Chair", "Monitor Stand", "Organizer")),
    Category("Candles", 0.011, 18.0, ("Pillar Candle", "Tealight Set", "Candle Jar")),
    Category("Plants", 0.010, 28.0, ("Fern", "Olive Tree", "Succulent Set")),
    Category("Kids", 0.009, 32.0, ("Play Mat", "Night Light", "Toy Chest")),
    Category("Pet", 0.008, 30.0, ("Pet Bed", "Feeding Bowl", "Scratching Post")),
    Category("Gifts", 0.005, 22.0, ("Gift Box", "Gift Card Holder", "Keepsake")),
)

# --- Orders and the daily demand model ----------------------------------------------
WEEKDAY_FACTORS = (1.06, 1.03, 1.00, 0.98, 0.93, 0.90, 1.10)  # Monday ... Sunday
YEARLY_AMPLITUDE = 0.12  # smooth yearly wave: peak late December, low in late June
HOLIDAY_BUMP = 0.30  # extra demand in the Christmas shopping season
HOLIDAY_CENTRE_DOY = 338  # early December
HOLIDAY_WIDTH_DAYS = 16.0
# Black Friday weekend: demand multipliers for Friday, Saturday, Sunday, Cyber Monday.
BLACK_FRIDAY_FACTORS = (2.6, 1.7, 1.6, 2.0)
BLACK_FRIDAY_DISCOUNTS = (0.20, 0.25, 0.30)
PRICE_RISE = 0.12  # every price rises 12 % on PRICE_RISE_DATE ...
PRICE_RISE_ORDER_DROP = 0.15  # ... and daily orders fall 15 % in level
DISCOUNTS = (0.0, 0.05, 0.10, 0.15, 0.20)
DISCOUNT_SHARES = (0.60, 0.15, 0.15, 0.07, 0.03)
PLUS_SHIPPING_COST = 6.0  # Fernway pays the shipping of Plus orders
BASE_CONVERSION = 0.028  # orders per session before the price rise
SESSION_NOISE = 0.04

# Two warehouses with very different delivery times (hidden bimodality).
HUB_NORTH, HUB_SOUTH = "North hub", "South hub"
HUB_OF_REGION = {
    "North": HUB_NORTH,
    "East": HUB_NORTH,
    "South": HUB_SOUTH,
    "West": HUB_SOUTH,
}
HOME_HUB_SHARE = 0.9  # the rest ships from the other hub (stock-outs)
DELIVERY_DAYS = {HUB_NORTH: (2.0, 0.6), HUB_SOUTH: (5.5, 1.0)}  # (mean, sd)

PRICE_TYPO_SHARE = 0.003  # unit_price typed in cents instead of dollars (x100)
PRICE_TYPO_FACTOR = 100

# --- Listings (Simpson's paradox) ----------------------------------------------------
# Each regional storefront features the products around its price-percentile centre:
# the South storefront is the value range, the West storefront the premium range.
STOREFRONT_CENTRE = {"South": 0.12, "East": 0.37, "North": 0.63, "West": 0.88}
STOREFRONT_WIDTH = 0.2
# Baseline conversion falls as the storefront gets pricier ...
STOREFRONT_CONVERSION = {"South": 0.09, "East": 0.055, "North": 0.03, "West": 0.015}
# ... while inside a storefront pricier products convert better.
LISTING_PRICE_EFFECT = 0.12
LISTING_NOISE = 0.15
LISTING_VIEWS_MEDIAN = 4_000.0
LISTING_VIEWS_SIGMA = 0.5

# --- Churn model ---------------------------------------------------------------------
CHURN_LOGIT_MEAN = -1.8  # about one Plus member in five churns within 90 days
CHURN_LOGIT_SD = 1.2  # how well the true risk separates churners (sets the AUC)
CHURN_OVERCONFIDENCE = 2.0  # the model stretches log-odds around the mean by this
CHURN_HIDDEN_NOISE = 0.5  # risk the customer table does not explain

# --- Checkout A/B/C test -------------------------------------------------------------
VARIANTS = ("A", "B", "C")
DEVICES = ("Desktop", "Mobile")
DEVICE_MEAN = {"Desktop": 92.0, "Mobile": 68.0}  # identical for every variant
VARIANT_SAMPLE_LIFT = {"A": 1.00, "B": 1.10, "C": 1.04}  # sample means, by design
CHECKOUT_CELL_SIZE = (40, 60)  # rows per variant x device cell, inclusive
CHECKOUT_SIGMA = 0.6  # order values are right-skewed (log-normal spread)

STREAMS = ("products", "customers", "orders", "daily", "listings", "churn", "checkout")


# --- Small helpers -------------------------------------------------------------------


def _sigmoid(x: FloatArray) -> FloatArray:
    """Return the logistic function of ``x``."""
    return 1.0 / (1.0 + np.exp(-x))


def _standardise(x: FloatArray) -> FloatArray:
    """Return ``x`` rescaled to mean 0 and standard deviation 1."""
    return (x - x.mean()) / x.std()


def _loaded(
    latent: FloatArray, rng: np.random.Generator, loading: float = BLOCK_LOADING
) -> FloatArray:
    """Return one noisy indicator of ``latent``, correlated ``loading`` with it."""
    noise = rng.standard_normal(latent.size)
    indicator: FloatArray = loading * latent + np.sqrt(1 - loading**2) * noise
    return indicator


def _days(first: dt.date, last: dt.date) -> DateArray:
    """Return every calendar day from ``first`` to ``last``, inclusive."""
    return np.arange(np.datetime64(first), np.datetime64(last) + ONE_DAY, ONE_DAY)


def _black_friday(year: int) -> dt.date:
    """Return the day after the fourth Thursday of November."""
    first = dt.date(year, 11, 1)
    first_thursday = first + dt.timedelta(days=(3 - first.weekday()) % 7)
    return first_thursday + dt.timedelta(weeks=3, days=1)


def _ids(prefix: str, n: int, width: int) -> list[str]:
    """Return ``n`` identifiers such as ``C00001`` (1-based, zero-padded)."""
    return [f"{prefix}{i:0{width}d}" for i in range(1, n + 1)]


# --- Products ------------------------------------------------------------------------


@dataclass(frozen=True)
class _Products:
    frame: pl.DataFrame
    pick_weight: FloatArray  # chance that an order line is this product


def build_products(rng: np.random.Generator) -> _Products:
    """Build the product catalogue and how often each product is ordered.

    Long-tail categories: each category is planted to reach its ``revenue_share``.
    A product is picked with probability proportional to its target revenue share
    divided by its price, so expected revenue per category matches the target no
    matter how expensive the category is.
    """
    shares = np.array([c.revenue_share for c in CATEGORIES])
    raw = np.sqrt(shares) / np.sqrt(shares).sum() * N_PRODUCTS
    counts = np.maximum(MIN_PRODUCTS_PER_CATEGORY, np.round(raw)).astype(np.int64)
    counts[0] += N_PRODUCTS - counts.sum()  # absorb rounding in the biggest category

    names: list[str] = []
    categories: list[str] = []
    prices: list[FloatArray] = []
    weights: list[FloatArray] = []
    for category, count in zip(CATEGORIES, counts, strict=True):
        combos = [f"{a} {n}" for n in category.nouns for a in ADJECTIVES]
        chosen = rng.choice(len(combos), size=count, replace=False)
        names += [combos[i] for i in chosen]
        categories += [category.name] * int(count)
        price = category.base_price * np.exp(PRICE_SIGMA * rng.standard_normal(count))
        prices.append(np.floor(price) + 0.99)  # shop prices end in .99
        popularity = rng.lognormal(0.0, 0.9, count)
        weights.append(category.revenue_share * popularity / popularity.sum())

    list_price = np.concatenate(prices)
    unit_cost = np.round(list_price * rng.uniform(*COST_RATIO, N_PRODUCTS), 2)
    pick = np.concatenate(weights) / list_price
    frame = pl.DataFrame(
        {
            "product_id": _ids("P", N_PRODUCTS, 4),
            "product_name": names,
            "category": categories,
            "unit_cost": unit_cost,
            "list_price": list_price,
        }
    )
    return _Products(frame, pick / pick.sum())


# --- Customers -----------------------------------------------------------------------


@dataclass(frozen=True)
class _Customers:
    frame: pl.DataFrame  # identity, demographics and the engagement block
    spend: FloatArray  # latent spending level
    service: FloatArray  # latent exposure to service problems
    signup: DateArray
    region: StrArray
    is_plus: BoolArray


def _annual_income(
    segment: StrArray, rng: np.random.Generator
) -> tuple[FloatArray, BoolArray]:
    """Draw incomes, and which customers skip the income question.

    Missing-not-at-random: the chance of skipping depends on the income itself, so
    low earners (mostly Students) are missing far more often. The observed incomes
    are therefore biased upwards, which no per-column summary reveals.
    """
    median = np.array([INCOME_MEDIAN[s] for s in segment])
    sigma = np.array([INCOME_SIGMA[s] for s in segment])
    income = np.round(median * np.exp(sigma * rng.standard_normal(segment.size)), -2)
    skip_chance = _sigmoid((SKIP_INCOME_MID - income) / SKIP_INCOME_SCALE)
    return income, rng.random(segment.size) < skip_chance


def build_customers(rng: np.random.Generator) -> _Customers:
    """Build customer attributes and their three independent latent factors.

    Correlated blocks: engagement, spending and service each come from their own
    latent factor, so columns correlate strongly inside a block and barely between
    blocks. The spending and service columns are added after the orders exist,
    because spending must agree with the orders table.
    """
    n = N_CUSTOMERS
    engagement, spend, service = rng.standard_normal((3, n))
    region = rng.choice(REGIONS, size=n, p=REGION_SHARES)
    segment = rng.choice(SEGMENTS, size=n, p=SEGMENT_SHARES)
    channel = rng.choice(CHANNELS, size=n, p=CHANNEL_SHARES)

    early = rng.random(n) < EARLY_SIGNUP_SHARE
    early_days = (START - SIGNUP_START).days
    late_days = (END - START).days + 1
    offset = np.where(
        early,
        rng.integers(0, early_days, n),
        early_days + rng.integers(0, late_days, n),
    )
    signup = np.datetime64(SIGNUP_START) + offset.astype("m8[D]")

    student = segment == "Student"
    age = np.where(
        student,
        rng.integers(18, 27, n),
        np.clip(np.round(rng.normal(44, 12, n)), 24, 79),
    ).astype(np.int64)
    income, skipped = _annual_income(segment, rng)
    is_plus = rng.random(n) < _sigmoid(PLUS_LOGIT + PLUS_SPEND_EFFECT * spend)

    frame = pl.DataFrame(
        {
            "customer_id": _ids("C", n, 5),
            "signup_date": pl.Series(signup).cast(pl.Date),
            "region": region,
            "segment": segment,
            "acquisition_channel": channel,
            "age": age,
            "annual_income": pl.Series(np.where(skipped, np.nan, income))
            .fill_nan(None)
            .cast(pl.Int64),
            "plan": np.where(is_plus, PLAN_PLUS, PLAN_STANDARD),
            # Engagement block: four views of one latent factor.
            "sessions_per_month": np.round(
                np.exp(np.log(8.0) + 0.55 * _loaded(engagement, rng)), 1
            ),
            "pages_per_session": np.round(
                np.exp(np.log(4.5) + 0.30 * _loaded(engagement, rng)), 1
            ),
            "app_opens_per_month": np.round(
                np.exp(np.log(6.0) + 0.70 * _loaded(engagement, rng))
            ).astype(np.int64),
            "email_click_rate": np.round(
                _sigmoid(-2.2 + 0.6 * _loaded(engagement, rng)), 4
            ),
        }
    )
    return _Customers(frame, spend, service, signup, region, is_plus)


# --- Daily demand model --------------------------------------------------------------


def demand_shape(days: DateArray) -> tuple[FloatArray, FloatArray]:
    """Return relative daily demand with and without the price-rise drop.

    Seasonality: a weekly cycle, a smooth yearly wave (summer low, December high),
    a Christmas-season bump and the Black Friday weekend spike. Structural break:
    from ``PRICE_RISE_DATE`` on, demand is ``1 - PRICE_RISE_ORDER_DROP`` lower.
    The second array (no drop) drives site traffic, which the price rise does not
    change: fewer visitors buy, so the conversion rate falls.
    """
    year_start = days.astype("M8[Y]").astype("M8[D]")
    doy = (days - year_start).astype(np.int64) + 1
    weekday = (days.astype(np.int64) + 3) % 7  # 1970-01-01 was a Thursday
    shape = np.asarray(WEEKDAY_FACTORS)[weekday]
    shape = shape * (1 + YEARLY_AMPLITUDE * np.cos(2 * np.pi * (doy - 355) / 365.25))
    bump = np.exp(-0.5 * ((doy - HOLIDAY_CENTRE_DOY) / HOLIDAY_WIDTH_DAYS) ** 2)
    shape = shape * (1 + HOLIDAY_BUMP * bump)
    for year in range(START.year, END.year + 1):
        friday = np.datetime64(_black_friday(year))
        for offset, factor in enumerate(BLACK_FRIDAY_FACTORS):
            shape = np.where(days == friday + offset * ONE_DAY, shape * factor, shape)
    after_rise = days >= np.datetime64(PRICE_RISE_DATE)
    with_break = np.where(after_rise, shape * (1 - PRICE_RISE_ORDER_DROP), shape)
    return with_break, shape


def _black_friday_mask(days: DateArray) -> BoolArray:
    """Mark the Black Friday weekends (Friday to Cyber Monday)."""
    mask = np.zeros(days.size, dtype=np.bool_)
    for year in range(START.year, END.year + 1):
        friday = np.datetime64(_black_friday(year))
        mask |= (days >= friday) & (days < friday + len(BLACK_FRIDAY_FACTORS) * ONE_DAY)
    return mask


# --- Orders --------------------------------------------------------------------------


def _pick_customers(
    day_of_order: DateArray, customers: _Customers, rng: np.random.Generator
) -> IntArray:
    """Pick the customer of each order, in proportion to their order frequency.

    Only customers who had signed up by the order date can be picked. Customers are
    sorted by signup date, so the eligible ones are a prefix of the sorted list and
    one ``searchsorted`` on cumulative weights samples every order at once.
    """
    weight = np.exp(SPEND_SIGMA * customers.spend)
    weight = np.where(customers.is_plus, weight * PLUS_ORDER_BOOST, weight)
    by_signup = np.argsort(customers.signup, kind="stable")
    cumulative = np.cumsum(weight[by_signup])
    n_eligible = np.searchsorted(customers.signup[by_signup], day_of_order, "right")
    draw = rng.random(day_of_order.size) * cumulative[n_eligible - 1]
    picked: IntArray = by_signup[np.searchsorted(cumulative, draw, "right")]
    return picked


def _anchor_slots(
    day_of_order: DateArray, customers: _Customers, rng: np.random.Generator
) -> tuple[IntArray, IntArray]:
    """Give every customer one order in each year they were signed up.

    The customer table is the active base: everyone ordered in the last 12
    months. Reserving one order per customer in 2025 alone would put more small
    buyers into 2025 than into 2024 and blur the price-rise story, so every year a
    customer was signed up gets one anchor order, on or after the signup date.
    Customers with the fewest eligible days choose first. The slots already exist
    (``day_of_order`` is sorted), so daily totals and their seasonality are
    unchanged; only who placed those orders changes.

    Returns the anchored order positions and the customer of each.
    """
    slots: list[int] = []
    owners: list[int] = []
    for year in range(START.year, END.year + 1):
        first_day = np.datetime64(dt.date(year, 1, 1))
        after_year = np.datetime64(dt.date(year + 1, 1, 1))
        free = (day_of_order >= first_day) & (day_of_order < after_year)
        members = np.flatnonzero(customers.signup < after_year)
        earliest = np.maximum(customers.signup[members], first_day)
        first_slot = np.searchsorted(day_of_order, earliest, "left")
        for i in np.argsort(-first_slot, kind="stable"):
            candidates = first_slot[i] + np.flatnonzero(free[first_slot[i] :])
            slot = int(candidates[rng.integers(candidates.size)])
            free[slot] = False
            slots.append(slot)
            owners.append(int(members[i]))
    return np.asarray(slots, dtype=np.int64), np.asarray(owners, dtype=np.int64)


def build_orders(
    customers: _Customers, products: _Products, rng: np.random.Generator
) -> pl.DataFrame:
    """Build one row per order (a single product line), sorted by date.

    ``revenue`` is always quantity x true price x (1 - discount). Data-entry
    outliers: in about 0.3 % of rows ``unit_price`` was typed in cents (x100); the
    revenue of those rows stays correct, as it would in a real billing system.
    """
    days = _days(START, END)
    demand, _ = demand_shape(days)
    daily_orders = rng.poisson(demand * TARGET_ORDERS / demand.sum())
    day = np.repeat(np.arange(days.size), daily_orders)
    order_day = days[day]
    n = day.size

    who = _pick_customers(order_day, customers, rng)
    anchored, owner = _anchor_slots(order_day, customers, rng)
    who[anchored] = owner
    what = rng.choice(N_PRODUCTS, size=n, p=products.pick_weight)
    basket = QTY_EXTRA * np.exp(QTY_SPEND_EFFECT * customers.spend[who])
    quantity = 1 + np.minimum(rng.poisson(basket), MAX_QUANTITY - 1).astype(np.int64)

    # The price list rose on PRICE_RISE_DATE; list_price is the current price.
    list_price = products.frame["list_price"].to_numpy()[what]
    before_rise = order_day < np.datetime64(PRICE_RISE_DATE)
    true_price = np.where(
        before_rise, np.round(list_price / (1 + PRICE_RISE), 2), list_price
    )
    discount = rng.choice(DISCOUNTS, size=n, p=DISCOUNT_SHARES)
    discount = np.where(
        _black_friday_mask(days)[day],
        rng.choice(BLACK_FRIDAY_DISCOUNTS, size=n),
        discount,
    )
    revenue = np.round(quantity * true_price * (1 - discount), 2)
    unit_cost = products.frame["unit_cost"].to_numpy()[what]
    shipping = np.where(customers.is_plus[who], PLUS_SHIPPING_COST, 0.0)
    profit = np.round(revenue - quantity * unit_cost - shipping, 2)

    home_hub = np.array([HUB_OF_REGION[r] for r in customers.region[who]])
    other_hub = np.where(home_hub == HUB_NORTH, HUB_SOUTH, HUB_NORTH)
    hub = np.where(rng.random(n) < HOME_HUB_SHARE, home_hub, other_hub)
    delivery = np.zeros(n)
    for name, (mean, sd) in DELIVERY_DAYS.items():
        at_hub = hub == name
        shape = (mean / sd) ** 2  # gamma: unimodal and right-skewed, like real waits
        delivery[at_hub] = rng.gamma(shape, mean / shape, at_hub.sum())

    typo = rng.random(n) < PRICE_TYPO_SHARE
    unit_price = np.where(typo, true_price * PRICE_TYPO_FACTOR, true_price)

    return pl.DataFrame(
        {
            "order_id": _ids("O", n, 6),
            "order_date": pl.Series(order_day).cast(pl.Date),
            "customer_id": customers.frame["customer_id"].to_numpy()[who],
            "product_id": products.frame["product_id"].to_numpy()[what],
            "warehouse": hub,
            "quantity": quantity,
            "unit_price": np.round(unit_price, 2),
            "discount": discount,
            "revenue": revenue,
            "profit": profit,
            "delivery_days": np.round(delivery, 1),
        }
    )


def finish_customers(
    customers: _Customers, orders: pl.DataFrame, rng: np.random.Generator
) -> pl.DataFrame:
    """Add the spending and service blocks to the customer table.

    Spending comes straight from the 2025 orders, so ``orders_12m`` and
    ``spend_12m`` always equal the orders table. Service counts come from the
    service factor; returns and late deliveries never exceed the number of orders.
    Satisfaction falls as service problems rise.
    """
    last_12m = (
        orders.filter(pl.col("order_date") >= LAST_12M_START)
        .group_by("customer_id")
        .agg(
            orders_12m=pl.len(),
            spend_12m=pl.col("revenue").sum().round(2),
            items_per_order=pl.col("quantity").mean().round(2),
        )
    )
    # A join does not promise to keep row order, but the service arrays below are
    # matched to customers by position: restore the original order explicitly.
    frame = (
        customers.frame.with_row_index("row")
        .join(last_12m, on="customer_id", how="left")
        .sort("row")
        .drop("row")
        .with_columns(
            pl.col("orders_12m").fill_null(0).cast(pl.Int64),
            pl.col("spend_12m").fill_null(0.0),
            pl.col("items_per_order").fill_null(0.0),
        )
    )
    n_orders = frame["orders_12m"].to_numpy()
    counts: dict[str, IntArray] = {}
    for column, median in SERVICE_MEDIANS.items():
        factor = _loaded(customers.service, rng, SERVICE_LOADING)
        counts[column] = np.round(median * np.exp(SERVICE_EFFECT * factor))
    for column in ("returns_12m", "late_deliveries_12m"):
        counts[column] = np.minimum(counts[column], n_orders)
    satisfaction = (
        SATISFACTION_MEAN
        - SATISFACTION_EFFECT * customers.service
        + rng.normal(0, SATISFACTION_NOISE, n_orders.size)
    )
    return frame.with_columns(
        **{column: count.astype(np.int64) for column, count in counts.items()},
        satisfaction_score=np.clip(np.round(satisfaction), 1, 10).astype(np.int64),
    )


# --- Daily metrics -------------------------------------------------------------------


def build_daily_metrics(orders: pl.DataFrame, rng: np.random.Generator) -> pl.DataFrame:
    """Build one row per day: traffic, and orders and revenue summed from orders.

    Sessions follow demand *without* the price-rise drop, so after the rise the
    same traffic converts less, while each order is worth more.
    """
    days = _days(START, END)
    _, traffic = demand_shape(days)
    expected_orders = traffic * TARGET_ORDERS / demand_shape(days)[0].sum()
    sessions = rng.poisson(
        expected_orders / BASE_CONVERSION * rng.lognormal(0, SESSION_NOISE, days.size)
    ).astype(np.int64)
    totals = orders.group_by("order_date").agg(
        orders=pl.len(), revenue=pl.col("revenue").sum()
    )
    return (
        pl.DataFrame({"date": pl.Series(days).cast(pl.Date), "sessions": sessions})
        .join(totals, left_on="date", right_on="order_date", how="left")
        .with_columns(
            pl.col("orders").fill_null(0).cast(pl.Int64),
            pl.col("revenue").fill_null(0.0).round(2),
        )
        .with_columns(
            conversion_rate=(pl.col("orders") / pl.col("sessions")).round(4),
            avg_order_value=(pl.col("revenue") / pl.col("orders")).round(2),
        )
        .sort("date")
    )


# --- Listings ------------------------------------------------------------------------


def build_listings(products: _Products, rng: np.random.Generator) -> pl.DataFrame:
    """Build product-page results per regional storefront for Q4 2025.

    Simpson's paradox: each storefront features products around its own price
    level, and pricier storefronts have lower baseline conversion, so price and
    conversion correlate negatively overall. Inside each storefront, pricier
    products convert better, so the correlation is positive within every region.
    """
    price = products.frame["list_price"].to_numpy()
    percentile = (np.argsort(np.argsort(price)) + 0.5) / price.size
    parts: list[pl.DataFrame] = []
    for region in REGIONS:
        centre = STOREFRONT_CENTRE[region]
        featured = rng.random(price.size) < np.exp(
            -0.5 * ((percentile - centre) / STOREFRONT_WIDTH) ** 2
        )
        p = price[featured]
        relative = np.clip(_standardise(p), -2.5, 2.5)
        conversion = STOREFRONT_CONVERSION[region] * np.exp(
            LISTING_PRICE_EFFECT * relative
            + LISTING_NOISE * rng.standard_normal(p.size)
        )
        views = np.round(
            rng.lognormal(np.log(LISTING_VIEWS_MEDIAN), LISTING_VIEWS_SIGMA, p.size)
        ).astype(np.int64)
        purchases = rng.binomial(views, conversion).astype(np.int64)
        parts.append(
            pl.DataFrame(
                {
                    "product_id": products.frame["product_id"].to_numpy()[featured],
                    "region": region,
                    "price": p,
                    "page_views": views,
                    "purchases": purchases,
                    "conversion_rate": np.round(purchases / views, 4),
                }
            )
        )
    return pl.concat(parts).sort("product_id", "region")


# --- Churn scores --------------------------------------------------------------------


def build_churn_scores(
    customers: pl.DataFrame, rng: np.random.Generator
) -> pl.DataFrame:
    """Build the churn model's scores for every Plus member, and what happened.

    The true risk rises with low satisfaction, late deliveries and support tickets.
    The model ranks members well but is overconfident: it stretches every
    member's log-odds away from the average by ``CHURN_OVERCONFIDENCE``, so its
    high scores are too high and its low scores too low.
    """
    plus = customers.filter(pl.col("plan") == PLAN_PLUS)

    def z(column: str) -> FloatArray:
        return _standardise(plus[column].to_numpy().astype(np.float64))

    risk = _standardise(
        -0.6 * z("satisfaction_score")
        + 0.35 * z("late_deliveries_12m")
        + 0.25 * z("support_tickets_12m")
        + CHURN_HIDDEN_NOISE * rng.standard_normal(plus.height)
    )
    true_logit = CHURN_LOGIT_MEAN + CHURN_LOGIT_SD * risk
    predicted = _sigmoid(
        CHURN_LOGIT_MEAN + CHURN_OVERCONFIDENCE * (true_logit - CHURN_LOGIT_MEAN)
    )
    churned = rng.random(plus.height) < _sigmoid(true_logit)
    return pl.DataFrame(
        {
            "customer_id": plus["customer_id"],
            "score_date": pl.Series([SCORE_DATE] * plus.height, dtype=pl.Date),
            "churn_probability": np.round(predicted, 4),
            "churned_90d": churned.astype(np.int64),
        }
    )


# --- Checkout test -------------------------------------------------------------------


def build_checkout_test(rng: np.random.Generator) -> pl.DataFrame:
    """Build an A/B/C checkout test whose variants differ only by chance.

    Every variant has the same true mean per device. To make the sample look
    convincing anyway, each cell's random draws are rescaled so that its sample
    mean hits a fixed target: B looks 9 % better than A. The spread is wide enough
    that the confidence intervals of all variants overlap.
    """
    variants: list[str] = []
    devices: list[str] = []
    values: list[FloatArray] = []
    low, high = CHECKOUT_CELL_SIZE
    for variant in VARIANTS:
        for device in DEVICES:
            size = int(rng.integers(low, high + 1))
            draw = rng.lognormal(np.log(DEVICE_MEAN[device]), CHECKOUT_SIGMA, size)
            target = DEVICE_MEAN[device] * VARIANT_SAMPLE_LIFT[variant]
            values.append(draw * target / draw.mean())
            variants += [variant] * size
            devices += [device] * size
    order = rng.permutation(len(variants))  # rows arrive in random order
    return pl.DataFrame(
        {
            "checkout_id": _ids("K", len(variants), 4),
            "variant": np.asarray(variants)[order],
            "device": np.asarray(devices)[order],
            "order_value": np.round(np.concatenate(values)[order], 2),
        }
    )


# --- Entry points --------------------------------------------------------------------


def build_tables(seed: int = SEED) -> dict[str, pl.DataFrame]:
    """Build every table of the showcase dataset in memory.

    Parameters
    ----------
    seed : int
        Root seed. Each table draws from its own child stream, so changing one
        table's generator leaves the random numbers of the others unchanged.

    Returns
    -------
    dict[str, polars.DataFrame]
        Table name to table, in the order they are written.
    """
    children = np.random.SeedSequence(seed).spawn(len(STREAMS))
    rng = {
        name: np.random.default_rng(child)
        for name, child in zip(STREAMS, children, strict=True)
    }
    products = build_products(rng["products"])
    base = build_customers(rng["customers"])
    orders = build_orders(base, products, rng["orders"])
    customers = finish_customers(base, orders, rng["customers"])
    return {
        "customers": customers,
        "products": products.frame,
        "orders": orders,
        "daily_metrics": build_daily_metrics(orders, rng["daily"]),
        "listings": build_listings(products, rng["listings"]),
        "churn_scores": build_churn_scores(customers, rng["churn"]),
        "checkout_test": build_checkout_test(rng["checkout"]),
    }


def main() -> None:
    """Write every table to ``<name>.csv`` next to this script."""
    for name, table in build_tables().items():
        table.write_csv(OUT_DIR / f"{name}.csv")
        print(f"{name}.csv: {table.height:,} rows")


if __name__ == "__main__":
    main()
