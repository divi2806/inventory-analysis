# Methodology

## 1. Business Framing

The project is framed as a retail operations analytics problem. The goal is to reduce stockout risk, reduce excess stock, improve supplier management, and support reorder decisions.

## 2. Data Modeling

The model uses:

- Products
- Stores
- Suppliers
- Inventory
- Sales
- Simulated supplier delivery events

The main unit of inventory analysis is a product-store combination.

## 3. Revenue And Margin

The source `sales_amount` values are retained as source data but are not used as final business revenue because they are inconsistent with unit quantity and product price.

The pipeline creates modeled revenue:

```text
revenue = quantity_sold * net_unit_price
```

Gross profit uses:

```text
estimated_unit_cost = price_per_unit * 62%
gross_profit = revenue - quantity_sold * estimated_unit_cost
```

This makes the profitability layer explicit and interview-defensible.

## 4. Inventory Optimization

The script calculates:

- Inventory value
- Average daily demand
- Demand variability
- Days of supply
- Inventory turnover
- Safety stock
- Recommended reorder point
- Recommended order quantity
- Holding cost estimate

Inventory status logic:

```text
Restock risk: current stock <= recommended reorder point
Overstock: days of supply > 120
Slow moving: inventory turnover < 1
Healthy: none of the above
```

## 5. Supplier Reliability

The source data does not include delivery history, so the project simulates purchase order events using existing supplier lead times and inventory restock patterns.

Supplier score uses:

```text
45% on-time rate
35% fill rate
20% delay efficiency
```

Supplier tiers:

- Strategic
- Reliable
- Watchlist

## 6. Forecasting

The project uses weighted recent demand:

```text
forecast_daily_units = 65% * 30-day average + 35% * 90-day average
forecast_30d_units = forecast_daily_units * 30
```

This is intentionally described as decision support, not a production-grade forecasting model.

## 7. Limitations

- Synthetic data
- Simulated supplier delivery events
- Estimated COGS and holding cost
- No promotions, holidays, stockout-adjusted demand, or external seasonality variables

## 8. Production Improvements

To make this production-grade, add:

- Real purchase order and delivery history
- Actual cost of goods sold
- Promotion calendar
- Holiday calendar
- Stockout-adjusted lost demand
- Lead-time confidence intervals
- Forecast accuracy backtesting
- Store transfer optimization
