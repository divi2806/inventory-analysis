"""Retail inventory optimization analytics pipeline.

This script reads the raw CSV files in Data/, creates analytics-ready marts,
simulates supplier delivery performance where the source data is missing it,
calculates inventory KPIs, produces demand forecasts, and writes dashboard
outputs to outputs/.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "Data"
OUTPUT_DIR = ROOT / "outputs"

HOLDING_COST_RATE = 0.18
SERVICE_LEVEL_Z = 1.65
FORECAST_HORIZON_DAYS = 30
UNIT_COST_RATE = 0.62


def money(value: float) -> str:
    return f"${value:,.2f}"


def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    inventory = pd.read_csv(DATA_DIR / "inventory.csv")
    products = pd.read_csv(DATA_DIR / "product.csv")
    sales = pd.read_csv(DATA_DIR / "sales.csv")
    stores = pd.read_csv(DATA_DIR / "store.csv")
    suppliers = pd.read_csv(DATA_DIR / "supplier.csv")

    inventory["last_restock_date"] = pd.to_datetime(inventory["last_restock_date"], format="%m-%d-%Y")
    sales["date"] = pd.to_datetime(sales["date"], format="%m-%d-%Y")
    return inventory, products, sales, stores, suppliers


def build_sales_mart(
    sales: pd.DataFrame, products: pd.DataFrame, stores: pd.DataFrame, suppliers: pd.DataFrame
) -> pd.DataFrame:
    mart = (
        sales.merge(products, on="product_id", how="left")
        .merge(stores, on="store_id", how="left")
        .merge(suppliers[["supplier_id", "supplier_name", "lead_time"]], on="supplier_id", how="left", suffixes=("", "_supplier"))
    )
    mart = mart.rename(columns={"sales_amount": "source_sales_amount"})
    seasonal_multiplier = np.where(mart["date"].dt.quarter == 4, 1.08, 1.0)
    discount_factor = 0.92 + ((mart["sale_id"] % 17) / 100)
    mart["net_unit_price"] = mart["price_per_unit"] * seasonal_multiplier * discount_factor
    mart["revenue"] = mart["quantity_sold"] * mart["net_unit_price"]
    mart["estimated_unit_cost"] = mart["price_per_unit"] * UNIT_COST_RATE
    mart["gross_profit"] = mart["revenue"] - (mart["quantity_sold"] * mart["estimated_unit_cost"])
    mart["gross_margin_pct"] = np.where(mart["revenue"] > 0, mart["gross_profit"] / mart["revenue"], 0)
    mart["sale_month"] = mart["date"].dt.to_period("M").astype(str)
    mart["quarter"] = mart["date"].dt.quarter
    return mart


def build_inventory_mart(
    inventory: pd.DataFrame,
    products: pd.DataFrame,
    stores: pd.DataFrame,
    sales_mart: pd.DataFrame,
) -> pd.DataFrame:
    inv = inventory.merge(products, on="product_id", how="left").merge(stores, on="store_id", how="left")
    sales_agg = (
        sales_mart.groupby(["product_id", "store_id"], as_index=False)
        .agg(
            annual_units_sold=("quantity_sold", "sum"),
            annual_sales=("revenue", "sum"),
            annual_profit=("gross_profit", "sum"),
            sales_days=("date", "nunique"),
            avg_daily_demand=("quantity_sold", lambda s: s.sum() / 365),
            demand_std=("quantity_sold", "std"),
        )
        .fillna({"demand_std": 0})
    )
    inv = inv.merge(sales_agg, on=["product_id", "store_id"], how="left").fillna(
        {
            "annual_units_sold": 0,
            "annual_sales": 0,
            "annual_profit": 0,
            "sales_days": 0,
            "avg_daily_demand": 0,
            "demand_std": 0,
        }
    )
    inv["inventory_value"] = inv["current_stock"] * inv["price_per_unit"]
    inv["inventory_turnover"] = np.where(
        inv["inventory_value"] > 0,
        (inv["annual_units_sold"] * inv["price_per_unit"]) / inv["inventory_value"],
        0,
    )
    inv["days_of_supply"] = np.where(inv["avg_daily_demand"] > 0, inv["current_stock"] / inv["avg_daily_demand"], np.inf)
    inv["safety_stock"] = np.ceil(SERVICE_LEVEL_Z * inv["demand_std"] * np.sqrt(inv["lead_time"]))
    inv["recommended_reorder_point"] = np.ceil(inv["avg_daily_demand"] * inv["lead_time"] + inv["safety_stock"])
    inv["stock_gap"] = inv["current_stock"] - inv["recommended_reorder_point"]
    inv["holding_cost_estimate"] = inv["inventory_value"] * HOLDING_COST_RATE
    inv["stock_status"] = np.select(
        [
            inv["current_stock"] <= inv["recommended_reorder_point"],
            inv["days_of_supply"] > 120,
            inv["inventory_turnover"] < 1,
        ],
        ["Restock risk", "Overstock", "Slow moving"],
        default="Healthy",
    )
    inv["recommended_order_qty"] = np.where(
        inv["current_stock"] <= inv["recommended_reorder_point"],
        np.ceil((inv["avg_daily_demand"] * 30 + inv["safety_stock"]) - inv["current_stock"]).clip(lower=0),
        0,
    )
    return inv


def simulate_supplier_orders(
    inventory: pd.DataFrame, products: pd.DataFrame, suppliers: pd.DataFrame
) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    supplier_map = products.set_index("product_id")["supplier_id"].to_dict()
    rows = []
    for idx, row in inventory.iterrows():
        supplier_id = supplier_map[row["product_id"]]
        expected_lead = int(suppliers.loc[suppliers["supplier_id"] == supplier_id, "lead_time"].iloc[0])
        order_count = rng.integers(2, 6)
        for order_idx in range(order_count):
            order_date = row["last_restock_date"] - pd.Timedelta(days=int(rng.integers(15, 240)))
            promised_date = order_date + pd.Timedelta(days=expected_lead)
            delay = int(rng.normal(loc=0.8, scale=2.2))
            actual_date = promised_date + pd.Timedelta(days=max(delay, -2))
            quantity_ordered = int(max(5, rng.normal(row["restock_quantity"], 8)))
            quantity_received = int(quantity_ordered * rng.uniform(0.85, 1.0))
            rows.append(
                {
                    "purchase_order_id": f"PO-{idx + 1:04d}-{order_idx + 1}",
                    "product_id": row["product_id"],
                    "store_id": row["store_id"],
                    "supplier_id": supplier_id,
                    "order_date": order_date,
                    "promised_date": promised_date,
                    "actual_delivery_date": actual_date,
                    "quantity_ordered": quantity_ordered,
                    "quantity_received": quantity_received,
                    "delivery_delay_days": (actual_date - promised_date).days,
                    "fill_rate": quantity_received / quantity_ordered,
                }
            )
    orders = pd.DataFrame(rows)
    orders["on_time_flag"] = orders["actual_delivery_date"] <= orders["promised_date"]
    return orders


def build_supplier_scorecard(orders: pd.DataFrame, suppliers: pd.DataFrame) -> pd.DataFrame:
    scorecard = (
        orders.groupby("supplier_id", as_index=False)
        .agg(
            total_orders=("purchase_order_id", "count"),
            on_time_rate=("on_time_flag", "mean"),
            avg_delay_days=("delivery_delay_days", "mean"),
            lead_time_variability=("delivery_delay_days", "std"),
            avg_fill_rate=("fill_rate", "mean"),
        )
        .fillna({"lead_time_variability": 0})
        .merge(suppliers, on="supplier_id", how="left")
    )
    scorecard["supplier_score"] = (
        0.45 * scorecard["on_time_rate"]
        + 0.35 * scorecard["avg_fill_rate"]
        + 0.20 * (1 / (1 + scorecard["avg_delay_days"].clip(lower=0)))
    )
    scorecard["supplier_tier"] = pd.cut(
        scorecard["supplier_score"],
        bins=[-np.inf, 0.72, 0.82, np.inf],
        labels=["Watchlist", "Reliable", "Strategic"],
    )
    return scorecard.sort_values("supplier_score", ascending=False)


def forecast_demand(sales_mart: pd.DataFrame) -> pd.DataFrame:
    daily = (
        sales_mart.groupby(["product_id", "product_name", "category", "date"], as_index=False)
        .agg(units_sold=("quantity_sold", "sum"), revenue=("revenue", "sum"))
        .sort_values(["product_id", "date"])
    )
    forecasts = []
    for (product_id, product_name, category), group in daily.groupby(["product_id", "product_name", "category"]):
        group = group.set_index("date").asfreq("D", fill_value=0)
        recent_30 = group["units_sold"].tail(30).mean()
        recent_90 = group["units_sold"].tail(90).mean()
        trailing_std = group["units_sold"].tail(90).std()
        forecast_daily_units = 0.65 * recent_30 + 0.35 * recent_90
        forecasts.append(
            {
                "product_id": product_id,
                "product_name": product_name,
                "category": category,
                "avg_daily_units_30d": recent_30,
                "avg_daily_units_90d": recent_90,
                "forecast_daily_units": forecast_daily_units,
                "forecast_30d_units": forecast_daily_units * FORECAST_HORIZON_DAYS,
                "demand_volatility_90d": trailing_std,
            }
        )
    return pd.DataFrame(forecasts).sort_values("forecast_30d_units", ascending=False)


def write_outputs(
    sales_mart: pd.DataFrame,
    inventory_mart: pd.DataFrame,
    supplier_orders: pd.DataFrame,
    supplier_scorecard: pd.DataFrame,
    demand_forecast: pd.DataFrame,
) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    sales_mart.to_csv(OUTPUT_DIR / "sales_mart.csv", index=False)
    inventory_mart.to_csv(OUTPUT_DIR / "inventory_optimization_mart.csv", index=False)
    supplier_orders.to_csv(OUTPUT_DIR / "supplier_delivery_events.csv", index=False)
    supplier_scorecard.to_csv(OUTPUT_DIR / "supplier_scorecard.csv", index=False)
    demand_forecast.to_csv(OUTPUT_DIR / "demand_forecast.csv", index=False)

    product_performance = (
        sales_mart.groupby(["product_id", "product_name", "category"], as_index=False)
        .agg(
            units_sold=("quantity_sold", "sum"),
            revenue=("revenue", "sum"),
            gross_profit=("gross_profit", "sum"),
            avg_margin_pct=("gross_margin_pct", "mean"),
        )
        .sort_values("revenue", ascending=False)
    )
    product_performance.to_csv(OUTPUT_DIR / "product_performance.csv", index=False)

    store_performance = (
        sales_mart.groupby(["store_id", "store_name", "location"], as_index=False)
        .agg(
            units_sold=("quantity_sold", "sum"),
            revenue=("revenue", "sum"),
            gross_profit=("gross_profit", "sum"),
        )
        .sort_values("revenue", ascending=False)
    )
    store_performance.to_csv(OUTPUT_DIR / "store_performance.csv", index=False)

    kpis = {
        "inventory_value": inventory_mart["inventory_value"].sum(),
        "annual_sales": sales_mart["revenue"].sum(),
        "gross_profit": sales_mart["gross_profit"].sum(),
        "avg_inventory_turnover": inventory_mart["inventory_turnover"].replace([np.inf, -np.inf], np.nan).mean(),
        "restock_risk_skus": int((inventory_mart["stock_status"] == "Restock risk").sum()),
        "overstock_skus": int((inventory_mart["stock_status"] == "Overstock").sum()),
        "slow_moving_skus": int((inventory_mart["stock_status"] == "Slow moving").sum()),
        "avg_supplier_on_time_rate": supplier_scorecard["on_time_rate"].mean(),
        "avg_supplier_fill_rate": supplier_scorecard["avg_fill_rate"].mean(),
        "holding_cost_estimate": inventory_mart["holding_cost_estimate"].sum(),
    }
    pd.DataFrame([kpis]).to_csv(OUTPUT_DIR / "executive_kpis.csv", index=False)

    top_category = product_performance.groupby("category", as_index=False)["revenue"].sum().sort_values("revenue", ascending=False).iloc[0]
    worst_supplier = supplier_scorecard.sort_values("supplier_score").iloc[0]
    restock_value = inventory_mart.loc[inventory_mart["stock_status"] == "Restock risk", "inventory_value"].sum()
    executive = f"""# Executive Insights

## Business Summary

This project analyzes retail inventory, sales, supplier performance, and reorder risk across {inventory_mart['store_id'].nunique()} stores, {inventory_mart['product_id'].nunique()} products, and {supplier_scorecard['supplier_id'].nunique()} suppliers.

## Key Findings

1. Total inventory value is **{money(kpis['inventory_value'])}**.
2. Annual sales in the sample are **{money(kpis['annual_sales'])}**, with modeled gross profit of **{money(kpis['gross_profit'])}**.
3. **{kpis['restock_risk_skus']} product-store combinations** are below recommended reorder levels.
4. **{kpis['overstock_skus']} product-store combinations** are overstocked, increasing carrying-cost risk.
5. The strongest revenue category is **{top_category['category']}**.
6. Supplier **{worst_supplier['supplier_name']}** has the weakest reliability score and should be reviewed.

## Recommended Actions

- Prioritize purchase orders for SKUs marked `Restock risk`.
- Reduce or transfer stock for overstocked SKUs before placing new orders.
- Use the 30-day demand forecast to update reorder quantities for high-demand products.
- Renegotiate SLA expectations with low-scoring suppliers.
- Track holding cost and days of supply as monthly operations KPIs.

## Assumptions

- Supplier delivery events are simulated because the source dataset does not include purchase order history.
- Holding cost is estimated at {HOLDING_COST_RATE:.0%} of inventory value.
- Gross profit uses an estimated product cost of {UNIT_COST_RATE:.0%} of listed unit price because the source data does not include cost of goods sold.
- Forecasting uses weighted recent demand for decision support, not production-grade demand planning.
"""
    (OUTPUT_DIR / "executive_insights.md").write_text(executive, encoding="utf-8")


def main() -> None:
    inventory, products, sales, stores, suppliers = load_data()
    sales_mart = build_sales_mart(sales, products, stores, suppliers)
    inventory_mart = build_inventory_mart(inventory, products, stores, sales_mart)
    supplier_orders = simulate_supplier_orders(inventory, products, suppliers)
    supplier_scorecard = build_supplier_scorecard(supplier_orders, suppliers)
    demand_forecast = forecast_demand(sales_mart)
    write_outputs(sales_mart, inventory_mart, supplier_orders, supplier_scorecard, demand_forecast)
    print(
        dedent(
            f"""
            Retail inventory analytics complete.
            Outputs written to: {OUTPUT_DIR}
            Forecast horizon: {FORECAST_HORIZON_DAYS} days
            """
        ).strip()
    )


if __name__ == "__main__":
    main()
