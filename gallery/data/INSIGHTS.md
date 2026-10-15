# Fernway showcase dataset: the answer key

Fernway is a fictional online retailer of home and lifestyle goods: furniture,
kitchenware, bedding, lighting and smaller decor. Customers can buy a paid membership,
**Fernway Plus**, which gives free shipping and member prices. The dataset covers two
years of the business, from 2024-01-01 to 2025-12-31, in seven tables that join on
their keys and agree with each other.

Eleven patterns are hidden in the data on purpose. Each one is the kind of thing a
default chart misses, and each one is revealed by a specific easy-viz chart and
option. This page lists them all: where each pattern is, how it was made, how strong it
is, and how to find it.

The tables are built by [`generate.py`](generate.py) from one fixed seed, so every
run gives the same files. Never edit the CSV files by hand: change the generator and
re-run `uv run python gallery/data/generate.py`. `tests/test_showcase_data.py` checks
every row of the summary below against the committed CSV files, and checks that the
files are exactly what the generator produces.

The first ten patterns were the starting set; the rest arrive with the plot
functions whose options reveal them. The dataset grows one plot
function at a time: each port adds the patterns its options and scenarios need, so
every notebook has a real story to tell.

## Summary

The test reads this table. Each row is one measurement on the committed CSV files.
The documented value is rounded to 2 decimals; counts are exact. The section of each
pattern defines its metrics precisely.

| ID | Pattern | Table | Metric | Documented value |
|---|---|---|---|---|
| `simpson-overall-r` | 1. Simpson's paradox | listings | Pearson r of price and conversion_rate, all rows | -0.42 |
| `simpson-min-within-region-r` | 1. Simpson's paradox | listings | Lowest Pearson r of price and conversion_rate within one region | 0.58 |
| `pareto-top20-profit-share` | 2. Profit concentration | orders | Share of total profit from the top 20 % of customers | 0.75 |
| `delivery-modes-overall` | 3. Hidden bimodality | orders | Peaks in the density of delivery_days, all orders | 2 |
| `delivery-modes-max-within-warehouse` | 3. Hidden bimodality | orders | Most peaks in the density of delivery_days within one warehouse | 1 |
| `delivery-median-north-hub` | 3. Hidden bimodality | orders | Median delivery_days, North hub | 1.90 |
| `delivery-median-south-hub` | 3. Hidden bimodality | orders | Median delivery_days, South hub | 5.40 |
| `season-weekday-ratio` | 4. Seasonality and a break | daily_metrics | Mean daily orders, busiest weekday over quietest | 1.19 |
| `season-peak-vs-summer-ratio` | 4. Seasonality and a break | daily_metrics | Mean daily orders, Nov-Dec over Jun-Aug | 1.56 |
| `season-black-friday-ratio` | 4. Seasonality and a break | daily_metrics | Orders on Black Friday over the mean of the 28 days before | 2.67 |
| `break-pre-orders-ratio` | 4. Seasonality and a break | daily_metrics | Mean daily orders, Jan-Mar 2025 over Jan-Mar 2024 | 1.01 |
| `break-post-orders-ratio` | 4. Seasonality and a break | daily_metrics | Mean daily orders, Apr-Oct 2025 over Apr-Oct 2024 | 0.85 |
| `break-post-aov-ratio` | 4. Seasonality and a break | daily_metrics | Average order value, Apr-Oct 2025 over Apr-Oct 2024 | 1.11 |
| `longtail-top3-revenue-share` | 5. Long-tail categories | orders, products | Revenue share of the 3 biggest categories | 0.54 |
| `longtail-categories-below-2pct` | 5. Long-tail categories | orders, products | Categories with less than 2 % of revenue | 9 |
| `blocks-median-within-abs-r` | 6. Correlated blocks | customers | Median abs. Pearson r of column pairs inside a block | 0.67 |
| `blocks-min-within-abs-r` | 6. Correlated blocks | customers | Lowest abs. Pearson r of a column pair inside a block | 0.57 |
| `blocks-max-between-abs-r` | 6. Correlated blocks | customers | Highest abs. Pearson r of a column pair from two blocks | 0.05 |
| `mnar-student-income-missing` | 7. Missing not at random | customers | Share of Students with no annual_income | 0.69 |
| `mnar-max-other-income-missing` | 7. Missing not at random | customers | Highest share with no annual_income in another segment | 0.04 |
| `typo-unit-price-share-pct` | 8. Data-entry outliers | orders | Percent of orders whose unit_price was typed x100 | 0.28 |
| `churn-auc` | 9. Overconfident churn model | churn_scores | Area under the ROC curve of churn_probability | 0.78 |
| `churn-top-decile-predicted` | 9. Overconfident churn model | churn_scores | Mean churn_probability, top 10 % of scores | 0.90 |
| `churn-top-decile-actual` | 9. Overconfident churn model | churn_scores | Share who actually churned, top 10 % of scores | 0.60 |
| `checkout-max-lift` | 10. Differences that aren't real | checkout_test | Highest variant mean over lowest, minus 1 | 0.09 |
| `checkout-anova-p` | 10. Differences that aren't real | checkout_test | One-way ANOVA p-value of order_value by variant | 0.62 |
| `checkout-cis-overlap` | 10. Differences that aren't real | checkout_test | 1 if the 95 % bootstrap intervals of all variant means overlap | 1 |
| `smallgroups-office-weekend-rank` | 11. Small groups at the top of a ranking | orders, products | Rank of Office by mean order revenue, Black Friday weekend 2025 | 2 |
| `smallgroups-office-weekend-orders` | 11. Small groups at the top of a ranking | orders, products | Office orders, Black Friday weekend 2025 | 3 |
| `smallgroups-weekend-categories-below-30` | 11. Small groups at the top of a ranking | orders, products | Categories with fewer than 30 orders, Black Friday weekend 2025 | 13 |

## The business and its tables

All tables are tidy: one row per thing, one column per fact, as a SQL query would
return them. Dates are ISO (`2025-04-01`), money is in dollars with 2 decimals, rates
are fractions between 0 and 1 with 4 decimals, and a missing value is an empty field.

**`customers`**: one row per customer, 4,000 rows. The table is the *active* customer
base: everyone in it ordered at least once in 2025, and once in every year they were
signed up. Customers who lapsed before 2025 are not in the dataset.
- `customer_id` (`C00001` ...), `signup_date` (2021 to 2025), `region` (North, South,
  East, West), `segment` (Consumer, Student, Small business), `acquisition_channel`
  (Organic search, Paid social, Referral, Email, Marketplace), `age`
- `annual_income`: self-reported, in dollars; empty when the customer skipped the
  question
- `plan`: `Standard` or `Plus`, the membership on 2025-09-30 (the day the churn model
  scored members)
- engagement over the last 12 months: `sessions_per_month`, `pages_per_session`,
  `app_opens_per_month`, `email_click_rate`
- spending in 2025: `orders_12m`, `spend_12m` (revenue), `items_per_order` (mean
  quantity). These are computed from `orders`, so they always agree with it.
- service in 2025: `support_tickets_12m`, `returns_12m`, `late_deliveries_12m`,
  `satisfaction_score` (1 to 10). Returns and late deliveries never exceed
  `orders_12m`.

**`products`**: one row per product, 300 rows. `product_id` (`P0001` ...),
`product_name`, `category` (18 categories), `unit_cost`, `list_price`. `list_price`
is the current price: on 2025-04-01 every price rose 12 %, so orders before that day
were charged `list_price` / 1.12.

**`orders`**: one row per order, 29,812 rows. Each order holds one product line.
`order_id` (`O000001` ...), `order_date`, `customer_id`, `product_id`, `warehouse`
(North hub or South hub), `quantity`, `unit_price` (the price before discount),
`discount` (a fraction), `revenue`, `profit`, `delivery_days` (1 decimal).
- `revenue` = `quantity` x price x (1 - `discount`), always with the true price.
- `profit` = `revenue` - `quantity` x `unit_cost`, minus the shipping Fernway pays for
  Plus members ($6 per order).

**`daily_metrics`**: one row per day, 731 rows (2024 is a leap year). `date`,
`sessions` (site visits), `orders`, `revenue`, `conversion_rate` (orders / sessions),
`avg_order_value` (revenue / orders). `orders` and `revenue` are the daily totals of
the `orders` table.

**`listings`**: one row per product featured in a regional web storefront, 514 rows,
for Q4 2025. `product_id`, `region`, `price` (the product's `list_price`),
`page_views`, `purchases` (made from that product page), `conversion_rate`
(purchases / page views). Each storefront features only part of the catalogue: most
products appear in one or two regions, and six products in none. Purchases come from the product page only,
so they are not a subset of `orders` you can reconcile.

**`churn_scores`**: one row per Plus member, 1,465 rows. `customer_id`, `score_date`
(2025-09-30), `churn_probability` (the model's prediction), `churned_90d` (1 if the
member cancelled in the 90 days after scoring).

**`checkout_test`**: one row per checkout in an A/B/C test of the checkout page, 333
rows. `checkout_id` (`K0001` ...), `variant` (A, B, C), `device` (Desktop, Mobile),
`order_value`. These checkouts are a separate experiment and are not in `orders`.

**How the tables join**

| From | Key | To |
|---|---|---|
| `orders` | `customer_id` | `customers` |
| `orders` | `product_id` | `products` |
| `orders.order_date` | date | `daily_metrics.date` |
| `listings` | `product_id` | `products` |
| `churn_scores` | `customer_id` | `customers` (Plus members only) |

## 1. Simpson's paradox: price and conversion

**Where:** `listings`, columns `price`, `conversion_rate` and `region`.

**Mechanism:** each regional storefront features the products around its own price
level. The South storefront is the value range (median price $28), then East ($44),
North ($78) and West, the premium range ($161). Pricier storefronts convert worse:
mean conversion is 9.25 % in the South, 5.55 % in the East, 2.99 % in the North and
1.47 % in the West. Inside each storefront it runs the other way: the pricier products
convert *better*, because shoppers who reach them are the ones who came for them.

**Strength:** over all 514 rows, price and conversion correlate at r = -0.42. Within
every region the correlation is positive, between 0.58 (West) and 0.75 (South).

**How to reveal it:** a plain scatter of `price` against `conversion_rate` with one
trendline says "expensive products convert worse", and that conclusion is wrong.
Split by region (`color="region"`) with a trendline per group, it shows four upward
lines, each sitting lower as the region gets pricier. A log x axis spreads out the
cheap regions.

## 2. Profit concentration

**Where:** `orders`, profit summed per `customer_id` over both years.

**Mechanism:** customers differ a lot in how often they order (a log-normal spread
of order frequency), and big spenders also buy more items per order (up to 6).

**Strength:** the top 20 % of customers by total profit (800 of the 4,000) bring 75 %
of all profit. Six customers lose Fernway money overall: small Plus members whose
free shipping costs more than their margin.

**How to reveal it:** a Pareto chart of profit per customer, with a cutoff at 80 % of
profit, shows how few customers it takes. A plain bar chart of 4,000 customers shows
nothing.

## 3. Hidden bimodality: two warehouses

**Where:** `orders`, columns `delivery_days` and `warehouse`.

**Mechanism:** orders ship from two warehouses. The North hub delivers in about 2
days (mean 2.0, sd 0.6); the South hub in about 5.5 days (mean 5.5, sd 1.0).
Customers in the North and East are served by the North hub, the South and West by
the South hub, each 90 % of the time (the rest ships from the other hub when stock
runs out). Inside each warehouse the delivery time has a single peak.

**Strength:** a density estimate of all delivery times (Gaussian kernel, bandwidth
0.3 days, peaks below 5 % of the highest ignored) has 2 peaks; within each warehouse
it has 1. The medians are 1.9 days (North hub) and 5.4 days (South hub). The overall
mean, 3.6 days, is a delivery time almost no order actually has.

**How to reveal it:** a histogram of `delivery_days` with a KDE curve shows two humps.
Adding `color="warehouse"` to the distribution plot splits them into two clean
single-peaked shapes, which explains the humps.

## 4. Seasonality and a structural break after a price rise

**Where:** `daily_metrics` (and so `orders`): `orders`, `sessions`,
`conversion_rate`, `avg_order_value`.

**Mechanism:** daily demand is a product of four seasonal parts plus one break:
- a weekly cycle: Sunday and Monday are the busiest days, Saturday the quietest
- a yearly wave: low in early summer, high in December
- a Christmas-season bump through November and December
- the Black Friday weekend: demand x2.6 on Black Friday, x2.0 on Cyber Monday, with
  20-30 % discounts
- **the break:** on 2025-04-01 every price rose 12 %. From that day, daily orders are
  15 % lower. Site traffic does not change, so the conversion rate falls, while each
  order is worth more.

**Strength:**
- The busiest weekday averages 1.19 times the orders of the quietest.
- November-December averages 1.56 times the daily orders of June-August.
- Black Friday brings 2.67 times the daily orders of the four weeks before it.
- Before the rise nothing changed: January-March 2025 has 1.01 times the daily orders
  of January-March 2024.
- After it, April-October 2025 has 0.85 times the daily orders of April-October 2024
  (33.1 against 39.0 a day), on the same traffic (about 1,390 sessions a day in both
  years). Conversion falls from 2.80 % to 2.37 %.
- The average order value rises 1.11 times over the same months ($127.64 to
  $141.31).

Comparing the same months of both years removes the seasonality, which is why the
metrics use these windows.

**How to reveal it:** the raw daily `orders` line is a noisy zigzag. A 7-day rolling
average removes the weekly cycle and shows the yearly wave and
the Black Friday spikes; a 28-day rolling average with a reference line at
2025-04-01 shows the step down in orders, the step down in `conversion_rate` and the
step up in `avg_order_value`.

## 5. Long-tail product categories

**Where:** `orders` joined to `products`, revenue summed by `category`.

**Mechanism:** each category is given a target revenue share, and each product is
ordered with a probability of its share divided by its price, so expensive and cheap
categories both land on their target.

**Strength:** Furniture (22 %), Kitchen (18 %) and Bedding (14 %) bring 54 % of
revenue. Nine of the 18 categories each bring less than 2 %: Tableware, Textiles,
Wall art, Office, Candles, Plants, Kids, Pet and Gifts. Together they make about 10 %.

**How to reveal it:** a bar chart of all 18 categories ends in a row of slivers that
are hard to read. Keeping the six largest (`top_n=6`) and folding the rest into one
"Other" bar is the honest summary of the tail.

## 6. Correlated variable blocks

**Where:** `customers`: the engagement, spending and service columns.

**Mechanism:** three independent hidden factors drive the customer columns:
engagement (`sessions_per_month`, `pages_per_session`, `app_opens_per_month`,
`email_click_rate`), spending (`orders_12m`, `spend_12m`, `items_per_order`) and
service problems (`support_tickets_12m`, `returns_12m`, `late_deliveries_12m`, and
`satisfaction_score`, which falls as problems rise). Every column follows its own
block's factor, plus noise.

**Strength:** inside a block, column pairs correlate with a median |r| of 0.67, and
never below 0.57. Between blocks, no pair goes above |r| = 0.05.

**How to reveal it:** a correlation heatmap of these 11 columns in table order looks
like a patchwork. With cluster ordering, the columns regroup into three bright
squares on the diagonal, with the negative satisfaction column inside the service
square.

## 7. Missing not at random: income

**Where:** `customers.annual_income`, split by `segment`.

**Mechanism:** whether a customer answers the income question depends on the income
itself: the lower it is, the more likely they skip it (a smooth curve centred on
$21,000). Students earn the least, so they skip most often.

**Strength:** 69 % of Students have no income, against 4 % of Consumers and 1 % of
Small business customers (12 % overall). Because the low incomes are the ones that
are missing, the incomes you can see are biased upwards: the observed Student median
is about $23,000, while Student incomes were drawn around a median of $17,000. No
summary of the column alone can show this.

**How to reveal it:** a missing-values chart of `customers` shows that only
`annual_income` has gaps; split by `segment`, it shows that the gaps sit almost
entirely in one segment. That is the cue not to fill them with an average.

## 8. Data-entry outliers: prices typed in cents

**Where:** `orders.unit_price`.

**Mechanism:** in about 0.3 % of orders the price was typed in cents instead of
dollars, so `unit_price` is 100 times too high. The billing system computed `revenue`
from the right price, so revenue is correct on every row.

**Strength:** 84 of the 29,812 orders (0.28 %). On those rows `unit_price` is
100 times `revenue` / (`quantity` x (1 - `discount`)), up to the rounding of revenue
to cents.

**How to reveal it:** a box plot of `unit_price` by category on a linear axis is
squashed flat by a few points in the thousands of dollars (up to about $40,000).
With a log y axis, the typos form a separate band exactly two orders of magnitude
above each box.

## 9. An overconfident churn model

**Where:** `churn_scores`, joined to `customers` for the drivers.

**Mechanism:** each Plus member has a true churn risk that rises with low
satisfaction, late deliveries and support tickets (plus causes the data doesn't
record). Whether they churned is drawn from that true risk. The model ranks members
correctly but is overconfident: it pushes every member's log-odds twice as far from
the average as they really are, so its high scores are too high and its low scores
too low.

**Strength:** the model separates churners well, with an AUC of 0.78. But the 10 %
of members with the highest scores have a mean predicted churn of 0.90, while 0.60 of
them actually churned. At the other end, the lowest decile predicts 0.4 % and sees
2.7 %. On average the model predicts 26 % churn against an actual 20 %. Churners have
a mean satisfaction of 6.2 against 7.5 for members who stayed.

**How to reveal it:** an ROC curve alone says the model is good. A calibration curve
shows the S-shaped gap: the curve sits below the diagonal at high scores and above it
at low scores. A threshold sweep shows what that means for a retention campaign:
the 305 members scored 0.5 or more were each given at least a 50 % chance of leaving
(0.77 on average), yet only 49 % of them churned, and they include only half of all
churners (148 of 297).

## 10. Differences that look real but aren't

**Where:** `checkout_test`, `order_value` by `variant` (and `device`).

**Mechanism:** all three variants have the same true mean order value ($92 on
desktop, $68 on mobile). To make the sample look convincing anyway, each
variant-device cell's random draws were rescaled to hit a fixed sample mean: B is
10 % above A in both devices, C 4 %.

**Strength:** the variant means are A $80.31, B $87.51 and C $83.89, so B looks 9 %
better than A. But order values vary a lot (from $15 to $462), and each variant has
only about 110 checkouts. The 95 % bootstrap intervals of the means overlap for every
pair (A $71.6 to $89.7, B $76.7 to $100.0, C $73.9 to $94.4; 4,000 resamples, seed
0), and a one-way ANOVA gives p = 0.62.

**How to reveal it:** a bar chart of mean order value per variant crowns B.
Bars by variant and device with bootstrap confidence intervals show
error bars that overlap everywhere: there is no winner to ship.

## 11. Small groups at the top of a ranking

**Where:** `orders` joined to `products`, Black Friday to Cyber Monday 2025
(2025-11-28 to 2025-12-01), mean `revenue` per order by `category`.

**Mechanism:** not planted on its own: it follows from patterns 4 and 5. The weekend
is short, and the long-tail categories (pattern 5) get only a handful of orders in
it, so their means rest on very few orders and swing far from the norm.

**Strength:** the weekend has 399 orders. Office ranks second of 18 categories by
mean order revenue ($224.90), ahead of Rugs, on 3 orders. 13 of the 18 categories
have fewer than 30 orders that weekend; Furniture, first, has 17.

**How to reveal it:** a bar chart of mean order revenue per category, sorted by value,
puts Office near the top and invites a conclusion. With the small-group flag
(`min_n=30`), most of the ranking is hatched, and Office's 3 orders show in the
labels (`show_n=True`); bootstrap intervals show how little the top of the ranking
is worth.
