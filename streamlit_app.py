"""Streamlit dashboard for retail inventory optimization."""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "outputs"


st.set_page_config(
    page_title="Retail Inventory Optimization",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    """
    <style>
    :root {
        --border: #d8dee8;
        --muted: #5f6b7a;
        --surface: #ffffff;
        --surface-muted: #f7f8fa;
        --ink: #111827;
    }
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
    [data-testid="stMetric"] {
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 1rem;
        background: var(--surface);
    }
    [data-testid="stMetricLabel"] { color: var(--muted); }
    [data-testid="stMetricValue"] { color: var(--ink); }
    .subtle { color: var(--muted); font-size: 0.95rem; margin-top: -0.35rem; }
    .decision-note {
        border: 1px solid var(--border);
        background: var(--surface-muted);
        border-radius: 8px;
        padding: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def load_outputs() -> dict[str, pd.DataFrame]:
    files = {
        "kpis": "executive_kpis.csv",
        "inventory": "inventory_optimization_mart.csv",
        "products": "product_performance.csv",
        "stores": "store_performance.csv",
        "suppliers": "supplier_scorecard.csv",
        "forecast": "demand_forecast.csv",
        "sales": "sales_mart.csv",
    }
    missing = [name for name in files.values() if not (OUTPUT_DIR / name).exists()]
    if missing:
        st.error("Analysis outputs are missing. Run `python3 Python/advanced_inventory_analysis.py` and refresh.")
        st.stop()
    return {key: pd.read_csv(OUTPUT_DIR / filename) for key, filename in files.items()}


def fmt_money(value: float) -> str:
    return f"${value:,.0f}"


def fmt_num(value: float) -> str:
    return f"{value:,.0f}"


def fmt_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def bar_chart(df: pd.DataFrame, x: str, y: str, title: str, sort: str = "-y") -> alt.Chart:
    return (
        alt.Chart(df)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            x=alt.X(f"{x}:N", title=None, sort=sort, axis=alt.Axis(labelAngle=0)),
            y=alt.Y(f"{y}:Q", title=None),
            tooltip=[x, alt.Tooltip(y, format=",.2f")],
            color=alt.Color(f"{x}:N", legend=None),
        )
        .properties(title=title, height=310)
    )


try:
    data = load_outputs()
except Exception as exc:
    st.error("The dashboard could not load the analytics outputs.")
    st.exception(exc)
    st.stop()


inventory = data["inventory"]
products = data["products"]
stores = data["stores"]
suppliers = data["suppliers"]
forecast = data["forecast"]
sales = data["sales"]
kpis = data["kpis"].iloc[0]

st.title("Retail Inventory Optimization")
st.markdown(
    '<p class="subtle">Inventory health, reorder risk, supplier reliability, product demand, and profitability dashboard for retail operations.</p>',
    unsafe_allow_html=True,
)

st.sidebar.header("Filters")
categories = st.sidebar.multiselect(
    "Category",
    sorted(inventory["category"].dropna().unique()),
    default=sorted(inventory["category"].dropna().unique()),
)
stores_filter = st.sidebar.multiselect(
    "Store",
    sorted(inventory["store_name"].dropna().unique()),
    default=sorted(inventory["store_name"].dropna().unique()),
)
status_filter = st.sidebar.multiselect(
    "Inventory status",
    ["Healthy", "Restock risk", "Overstock", "Slow moving"],
    default=["Healthy", "Restock risk", "Overstock", "Slow moving"],
)

scoped_inventory = inventory[
    inventory["category"].isin(categories)
    & inventory["store_name"].isin(stores_filter)
    & inventory["stock_status"].isin(status_filter)
].copy()

if scoped_inventory.empty:
    st.warning("No inventory rows match the selected filters. Adjust the sidebar filters to continue.")
    st.stop()

inventory_value = scoped_inventory["inventory_value"].sum()
holding_cost = scoped_inventory["holding_cost_estimate"].sum()
restock_risk = int((scoped_inventory["stock_status"] == "Restock risk").sum())
overstock = int((scoped_inventory["stock_status"] == "Overstock").sum())
turnover = scoped_inventory["inventory_turnover"].replace([float("inf"), -float("inf")], pd.NA).dropna().mean()

metric_cols = st.columns(5)
metric_cols[0].metric("Inventory value", fmt_money(inventory_value))
metric_cols[1].metric("Annual sales", fmt_money(kpis["annual_sales"]))
metric_cols[2].metric("Gross profit", fmt_money(kpis["gross_profit"]))
metric_cols[3].metric("Restock risk SKUs", fmt_num(restock_risk))
metric_cols[4].metric("Avg turnover", f"{turnover:.2f}x")

st.divider()

overview_tab, inventory_tab, supplier_tab, forecast_tab, data_tab = st.tabs(
    ["Executive overview", "Inventory actions", "Supplier reliability", "Demand forecast", "Data quality"]
)

with overview_tab:
    c1, c2 = st.columns(2)
    status_summary = (
        scoped_inventory.groupby("stock_status", as_index=False)
        .agg(skus=("inventory_id", "count"), inventory_value=("inventory_value", "sum"))
        .sort_values("skus", ascending=False)
    )
    category_summary = (
        scoped_inventory.groupby("category", as_index=False)
        .agg(inventory_value=("inventory_value", "sum"), annual_sales=("annual_sales", "sum"))
        .sort_values("inventory_value", ascending=False)
    )
    with c1:
        st.altair_chart(bar_chart(status_summary, "stock_status", "skus", "SKU count by inventory status"), width="stretch")
    with c2:
        st.altair_chart(bar_chart(category_summary, "category", "inventory_value", "Inventory value by category"), width="stretch")

    monthly = (
        sales[sales["category"].isin(categories)]
        .groupby(["sale_month", "category"], as_index=False)
        .agg(revenue=("revenue", "sum"))
    )
    trend = (
        alt.Chart(monthly)
        .mark_line(point=True)
        .encode(
            x=alt.X("sale_month:N", title=None),
            y=alt.Y("revenue:Q", title="Revenue"),
            color=alt.Color("category:N", title="Category"),
            tooltip=["sale_month:N", "category:N", alt.Tooltip("revenue:Q", format=",.0f")],
        )
        .properties(title="Monthly revenue trend by category", height=320)
    )
    st.altair_chart(trend, width="stretch")

    st.markdown(
        f"""
        <div class="decision-note">
        <strong>Decision readout:</strong><br>
        Current filters cover <strong>{len(scoped_inventory):,}</strong> product-store combinations.
        The selected inventory has <strong>{fmt_money(inventory_value)}</strong> in stock value and
        <strong>{fmt_money(holding_cost)}</strong> in estimated annual carrying cost.
        Prioritize <strong>{restock_risk:,}</strong> restock-risk rows and review
        <strong>{overstock:,}</strong> overstock rows for transfer, markdown, or reorder freeze.
        </div>
        """,
        unsafe_allow_html=True,
    )

with inventory_tab:
    action_table = scoped_inventory.sort_values(
        ["stock_status", "recommended_order_qty", "inventory_value"],
        ascending=[False, False, False],
    )
    st.dataframe(
        action_table[
            [
                "store_name",
                "product_name",
                "category",
                "current_stock",
                "recommended_reorder_point",
                "recommended_order_qty",
                "days_of_supply",
                "inventory_turnover",
                "inventory_value",
                "stock_status",
            ]
        ],
        width="stretch",
        hide_index=True,
    )
    st.download_button(
        "Download inventory action table",
        action_table.to_csv(index=False),
        "inventory_action_table.csv",
        "text/csv",
    )

with supplier_tab:
    s1, s2, s3 = st.columns(3)
    s1.metric("Average on-time rate", fmt_pct(suppliers["on_time_rate"].mean()))
    s2.metric("Average fill rate", fmt_pct(suppliers["avg_fill_rate"].mean()))
    s3.metric("Watchlist suppliers", fmt_num((suppliers["supplier_tier"] == "Watchlist").sum()))

    supplier_chart = suppliers.sort_values("supplier_score", ascending=False).head(15)
    st.altair_chart(bar_chart(supplier_chart, "supplier_name", "supplier_score", "Supplier reliability score"), width="stretch")
    st.dataframe(
        suppliers[
            [
                "supplier_name",
                "supplier_tier",
                "total_orders",
                "on_time_rate",
                "avg_delay_days",
                "avg_fill_rate",
                "supplier_score",
            ]
        ],
        width="stretch",
        hide_index=True,
    )

with forecast_tab:
    selected_category_forecast = forecast[forecast["category"].isin(categories)].head(25)
    st.altair_chart(
        bar_chart(selected_category_forecast, "product_name", "forecast_30d_units", "Top 30-day demand forecast"),
        width="stretch",
    )
    st.dataframe(
        selected_category_forecast[
            [
                "product_name",
                "category",
                "avg_daily_units_30d",
                "avg_daily_units_90d",
                "forecast_30d_units",
                "demand_volatility_90d",
            ]
        ],
        width="stretch",
        hide_index=True,
    )
    st.info(
        "Forecasting uses weighted recent demand for decision support. For production demand planning, add promotions, price changes, holidays, and stockout-adjusted demand."
    )

with data_tab:
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Product-store rows", fmt_num(len(inventory)))
    d2.metric("Sales rows", fmt_num(len(sales)))
    d3.metric("Products", fmt_num(products["product_id"].nunique()))
    d4.metric("Suppliers", fmt_num(suppliers["supplier_id"].nunique()))

    st.warning(
        "Supplier delivery history and cost of goods sold were not present in the source data, so the project documents simulated supplier events and explicit cost assumptions."
    )
    st.dataframe(scoped_inventory.head(100), width="stretch", hide_index=True)
