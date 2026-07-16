# Executive Insights

## Business Summary

This project analyzes retail inventory, sales, supplier performance, and reorder risk across 4 stores, 100 products, and 20 suppliers.

## Key Findings

1. Total inventory value is **$5,122,057.97**.
2. Annual sales in the sample are **$2,753,675.77**, with modeled gross profit of **$1,082,533.42**.
3. **286 product-store combinations** are below recommended reorder levels.
4. **667 product-store combinations** are overstocked, increasing carrying-cost risk.
5. The strongest revenue category is **Groceries**.
6. Supplier **Mahesh** has the weakest reliability score and should be reviewed.

## Recommended Actions

- Prioritize purchase orders for SKUs marked `Restock risk`.
- Reduce or transfer stock for overstocked SKUs before placing new orders.
- Use the 30-day demand forecast to update reorder quantities for high-demand products.
- Renegotiate SLA expectations with low-scoring suppliers.
- Track holding cost and days of supply as monthly operations KPIs.

## Assumptions

- Supplier delivery events are simulated because the source dataset does not include purchase order history.
- Holding cost is estimated at 18% of inventory value.
- Gross profit uses an estimated product cost of 62% of listed unit price because the source data does not include cost of goods sold.
- Forecasting uses weighted recent demand for decision support, not production-grade demand planning.
