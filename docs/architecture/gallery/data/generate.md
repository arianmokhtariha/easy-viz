# Showcase data generator

Covers: gallery/data/generate.py

## Responsibilities
Build the Fernway showcase dataset (seven related tables with ten planted patterns)
deterministically, and write each table to `gallery/data/<table>.csv`. The business,
the tables and every pattern are described in the answer key,
[`gallery/data/INSIGHTS.md`](../../../../gallery/data/INSIGHTS.md); this page covers
how the script produces them.

## How it works
`uv run python gallery/data/generate.py` calls `main()`, which writes the tables
returned by `build_tables(seed=SEED)`. Building everything in memory takes well under
a second, so the test calls `build_tables()` directly.

**Random streams.** `build_tables` splits the seed with `numpy.random.SeedSequence`
into one child generator per stream (`STREAMS`: products, customers, orders, daily,
listings, churn, checkout). Changing how one table draws its numbers leaves the
random numbers of the other streams unchanged. Tables built *from* other tables
still change with them.

**Build order and data flow:**
1. `build_products`: the catalogue, plus each product's chance of being ordered.
   That chance is the category's target revenue share divided by the price, so every
   category reaches its share no matter how expensive it is (long tail).
2. `build_customers`: attributes, the engagement block, and three independent latent
   factors (engagement, spending, service) kept in the private `_Customers` record.
   Income is drawn per segment, and skipping the question depends on the income
   itself (missing not at random).
3. `build_orders`: `demand_shape` gives the relative demand of every day (weekly
   cycle, yearly wave, holiday bump, Black Friday weekend, the 15 % drop from
   2025-04-01). Daily order counts are Poisson draws around it. Each order slot then
   gets a customer, in proportion to `exp(SPEND_SIGMA x spending factor)` among
   customers already signed up (`_pick_customers`). `_anchor_slots` then gives every
   customer one slot in each year they were signed up, so the customer table is the
   active base. Products, quantities, the 12 % price rise, discounts, profit, the
   warehouse, gamma-distributed delivery times and the x100 `unit_price` typos are
   drawn per order.
4. `finish_customers`: adds the spending block (aggregated from 2025 orders, so it
   always agrees with them) and the service block (rounded log-normal counts that
   follow the service factor; returns and late deliveries capped at `orders_12m`).
5. `build_daily_metrics`: sums orders and revenue per day from `orders`. Sessions
   follow demand *without* the price-rise drop, so conversion falls after the rise.
6. `build_listings`: each regional storefront features the products around its price
   percentile; baseline conversion falls with the storefront's price level and rises
   with price inside it (Simpson's paradox).
7. `build_churn_scores`: a true churn risk from satisfaction, late deliveries and
   tickets; the prediction stretches the log-odds around the mean by
   `CHURN_OVERCONFIDENCE`.
8. `build_checkout_test`: identical true means; each cell's draws are rescaled to a
   fixed sample mean, so the variants look different but aren't.

Every strength is a named constant at the top of the script (dates, sizes, effect
sizes, noise levels), next to a comment saying which pattern it controls.

## Invariants
- Same seed, same tables: no clock, no unordered iteration, no unseeded randomness.
- The CSV files are the script's output and are never edited by hand.
  `tests/test_showcase_data.py` rebuilds the tables and compares them with the files
  (strings, integers and dates exactly; floats within `atol=0.011`).
- Aggregates agree with the orders: `customers.orders_12m`, `spend_12m` and
  `items_per_order` come from the 2025 orders; `daily_metrics.orders` and `revenue`
  are daily sums of `orders`. Returns and late deliveries never exceed `orders_12m`.
  Every order is on or after its customer's signup date.
- Every customer has at least one order in 2025, and one in every year they were
  signed up.
- `revenue` always uses the true price; only `unit_price` carries the typos.
- Every planted pattern has its rows in the summary table of `INSIGHTS.md`, with the
  value measured on the committed files. Changing a constant means re-running the
  script and updating the documented values and the prose that quotes them.

## Pitfalls
- **The checks run on the CSV files, not on the script.** After changing the script,
  re-run it before `pytest`; otherwise the reproducibility test fails on purpose.
- **`listings` has about 500 rows, not one per product and region.** Price and
  conversion are Pearson-correlated on raw prices, which range from $8 to $988. If
  every storefront listed most products, product price differences would swamp the
  regional ones, and the overall correlation would turn positive. Storefront
  assortments therefore overlap only partly (`STOREFRONT_WIDTH`).
- **Anchor orders exist in both years for a reason.** Anchoring only 2025 puts more
  small buyers into 2025 than 2024, which shifts the average order value and hides
  the price-rise step. `_anchor_slots` reassigns existing slots, so daily totals are
  unchanged.
- **Every sort that can meet ties is stable** (`kind="stable"` in numpy, a
  tie-breaking key in polars). numpy's default sort picks a CPU-specific routine
  that orders equal values differently, so list prices (many end in .99) ranked
  differently on the Linux CI runner and changed which products each storefront
  features.
- **The service counts are rounded log-normals, not Poisson.** Poisson noise on
  counts with a mean near 1 drowns the shared factor (within-block |r| fell to
  about 0.3).
- **The overconfidence pivots on the mean log-odds, not on 0.5.** Stretching around
  0.5 (`sigmoid(k x logit p)`) cannot make a top decile with a 60 % churn rate
  predict 90 %, because the stretch is weak near 0.5.
- **`plan` is `Standard`/`Plus`, never `None`.** pandas reads the text `None` as a
  missing value by default.
- **Black Friday dates are computed** (the day after the fourth Thursday of
  November), so changing `START` or `END` keeps the spike on the right day.
- **The pattern strengths are tuned for this seed.** Another seed keeps every
  mechanism (every sign holds), but sampling noise moves some measured strengths by
  a few tenths: on seeds 1-5 the lowest within-region r fell to 0.26 and the Black
  Friday ratio rose to 3.02. Re-measure every documented value, and check each
  pattern is still clearly visible, before committing a new seed.
- **The density used to count delivery-time peaks** uses a fixed bandwidth of 0.3
  days in the test. Delivery times are rounded to 0.1 days, and an automatic
  bandwidth narrower than that finds spurious peaks.
