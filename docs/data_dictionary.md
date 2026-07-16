# Data Dictionary

## Source Tables

### `Data/product.csv`

| Column | Description |
|---|---|
| `product_id` | Product identifier |
| `product_name` | Product name |
| `category` | Product category |
| `price_per_unit` | Listed unit price |
| `supplier_id` | Supplier identifier |
| `reorder_point` | Source reorder point |
| `lead_time` | Expected lead time in days |

### `Data/store.csv`

| Column | Description |
|---|---|
| `store_id` | Store identifier |
| `store_name` | Store name |
| `location` | Store city/region |

### `Data/supplier.csv`

| Column | Description |
|---|---|
| `supplier_id` | Supplier identifier |
| `supplier_name` | Supplier name |
| `lead_time` | Supplier expected lead time |
| `contact_info` | Supplier contact email |

### `Data/inventory.csv`

| Column | Description |
|---|---|
| `inventory_id` | Product-store inventory row identifier |
| `product_id` | Product identifier |
| `store_id` | Store identifier |
| `current_stock` | Current on-hand units |
| `last_restock_date` | Last restock date |
| `restock_quantity` | Most recent restock quantity |

### `Data/sales.csv`

| Column | Description |
|---|---|
| `sale_id` | Sales transaction identifier |
| `product_id` | Product identifier |
| `date` | Sale date |
| `quantity_sold` | Units sold |
| `store_id` | Store identifier |
| `sales_amount` | Source transaction amount |

## Generated Outputs

| File | Description |
|---|---|
| `outputs/sales_mart.csv` | Sales enriched with product, store, supplier, revenue, and margin |
| `outputs/inventory_optimization_mart.csv` | Product-store inventory KPIs and reorder recommendations |
| `outputs/supplier_delivery_events.csv` | Simulated purchase-order delivery events |
| `outputs/supplier_scorecard.csv` | Supplier reliability metrics |
| `outputs/demand_forecast.csv` | 30-day demand forecast by product |
| `outputs/product_performance.csv` | Product revenue, units, and profit |
| `outputs/store_performance.csv` | Store revenue, units, and profit |
| `outputs/executive_kpis.csv` | One-row executive KPI summary |
| `outputs/executive_insights.md` | Business summary and recommendations |
