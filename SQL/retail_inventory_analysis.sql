/*
Retail Inventory Optimization Analytics

Assumed source tables:
  product(product_id, product_name, category, price_per_unit, supplier_id, reorder_point, lead_time)
  store(store_id, store_name, location)
  supplier(supplier_id, supplier_name, lead_time, contact_info)
  inventory(inventory_id, product_id, store_id, current_stock, last_restock_date, restock_quantity)
  sales(sale_id, product_id, date, quantity_sold, store_id, sales_amount)

Notes:
  - Date parsing syntax may vary by database. STR_TO_DATE is MySQL-style.
  - The source sales_amount is kept as raw input, but final business revenue should be
    calculated from units and price if source amounts are inconsistent.
*/

CREATE DATABASE IF NOT EXISTS retail_inventory;
USE retail_inventory;

-- 1. Source table checks
SELECT COUNT(*) AS product_rows FROM product;
SELECT COUNT(*) AS store_rows FROM store;
SELECT COUNT(*) AS supplier_rows FROM supplier;
SELECT COUNT(*) AS inventory_rows FROM inventory;
SELECT COUNT(*) AS sales_rows FROM sales;

-- 2. Inventory valuation by category
SELECT
    p.category,
    ROUND(SUM(i.current_stock * p.price_per_unit), 2) AS inventory_value,
    COUNT(*) AS product_store_rows
FROM inventory i
JOIN product p
    ON i.product_id = p.product_id
GROUP BY p.category
ORDER BY inventory_value DESC;

-- 3. Restock risk using source reorder point
SELECT
    st.store_name,
    p.product_name,
    p.category,
    i.current_stock,
    p.reorder_point,
    p.lead_time,
    p.reorder_point - i.current_stock AS stock_gap
FROM inventory i
JOIN product p
    ON i.product_id = p.product_id
JOIN store st
    ON i.store_id = st.store_id
WHERE i.current_stock <= p.reorder_point
ORDER BY stock_gap DESC;

-- 4. Product performance using modeled revenue and estimated COGS
WITH sales_enriched AS (
    SELECT
        s.sale_id,
        s.product_id,
        s.store_id,
        STR_TO_DATE(s.date, '%m-%d-%Y') AS sale_date,
        s.quantity_sold,
        p.product_name,
        p.category,
        p.price_per_unit,
        p.price_per_unit * 0.62 AS estimated_unit_cost,
        s.quantity_sold * p.price_per_unit AS modeled_revenue,
        s.quantity_sold * (p.price_per_unit - p.price_per_unit * 0.62) AS modeled_gross_profit
    FROM sales s
    JOIN product p
        ON s.product_id = p.product_id
)
SELECT
    product_id,
    product_name,
    category,
    SUM(quantity_sold) AS units_sold,
    ROUND(SUM(modeled_revenue), 2) AS revenue,
    ROUND(SUM(modeled_gross_profit), 2) AS gross_profit,
    ROUND(SUM(modeled_gross_profit) / NULLIF(SUM(modeled_revenue), 0) * 100, 2) AS gross_margin_pct
FROM sales_enriched
GROUP BY product_id, product_name, category
ORDER BY revenue DESC;

-- 5. Store-level performance
WITH sales_enriched AS (
    SELECT
        s.store_id,
        s.quantity_sold,
        p.price_per_unit,
        s.quantity_sold * p.price_per_unit AS modeled_revenue,
        s.quantity_sold * (p.price_per_unit - p.price_per_unit * 0.62) AS modeled_gross_profit
    FROM sales s
    JOIN product p
        ON s.product_id = p.product_id
)
SELECT
    st.store_name,
    st.location,
    SUM(se.quantity_sold) AS units_sold,
    ROUND(SUM(se.modeled_revenue), 2) AS revenue,
    ROUND(SUM(se.modeled_gross_profit), 2) AS gross_profit
FROM sales_enriched se
JOIN store st
    ON se.store_id = st.store_id
GROUP BY st.store_name, st.location
ORDER BY revenue DESC;

-- 6. Inventory turnover and days of supply by product-store
WITH demand AS (
    SELECT
        s.product_id,
        s.store_id,
        SUM(s.quantity_sold) AS annual_units_sold,
        SUM(s.quantity_sold) / 365.0 AS avg_daily_demand
    FROM sales s
    GROUP BY s.product_id, s.store_id
)
SELECT
    st.store_name,
    p.product_name,
    p.category,
    i.current_stock,
    COALESCE(d.annual_units_sold, 0) AS annual_units_sold,
    ROUND(i.current_stock * p.price_per_unit, 2) AS inventory_value,
    ROUND(COALESCE(d.annual_units_sold, 0) / NULLIF(i.current_stock, 0), 2) AS unit_turnover,
    ROUND(i.current_stock / NULLIF(d.avg_daily_demand, 0), 1) AS days_of_supply
FROM inventory i
JOIN product p
    ON i.product_id = p.product_id
JOIN store st
    ON i.store_id = st.store_id
LEFT JOIN demand d
    ON i.product_id = d.product_id
   AND i.store_id = d.store_id
ORDER BY days_of_supply DESC;

-- 7. Overstock and slow-moving product-store rows
WITH demand AS (
    SELECT
        s.product_id,
        s.store_id,
        SUM(s.quantity_sold) / 365.0 AS avg_daily_demand
    FROM sales s
    GROUP BY s.product_id, s.store_id
)
SELECT
    st.store_name,
    p.product_name,
    p.category,
    i.current_stock,
    ROUND(i.current_stock / NULLIF(d.avg_daily_demand, 0), 1) AS days_of_supply,
    ROUND(i.current_stock * p.price_per_unit, 2) AS inventory_value,
    CASE
        WHEN i.current_stock / NULLIF(d.avg_daily_demand, 0) > 120 THEN 'Overstock'
        WHEN COALESCE(d.avg_daily_demand, 0) = 0 THEN 'No demand'
        ELSE 'Monitor'
    END AS action_status
FROM inventory i
JOIN product p
    ON i.product_id = p.product_id
JOIN store st
    ON i.store_id = st.store_id
LEFT JOIN demand d
    ON i.product_id = d.product_id
   AND i.store_id = d.store_id
WHERE i.current_stock / NULLIF(d.avg_daily_demand, 0) > 120
   OR COALESCE(d.avg_daily_demand, 0) = 0
ORDER BY inventory_value DESC;

-- 8. Monthly seasonality
SELECT
    p.category,
    EXTRACT(MONTH FROM STR_TO_DATE(s.date, '%m-%d-%Y')) AS sales_month,
    SUM(s.quantity_sold) AS units_sold,
    ROUND(SUM(s.quantity_sold * p.price_per_unit), 2) AS revenue
FROM sales s
JOIN product p
    ON s.product_id = p.product_id
GROUP BY p.category, sales_month
ORDER BY p.category, sales_month;

-- 9. Supplier sales exposure
SELECT
    sup.supplier_name,
    COUNT(DISTINCT p.product_id) AS products_supplied,
    SUM(s.quantity_sold) AS units_sold,
    ROUND(SUM(s.quantity_sold * p.price_per_unit), 2) AS revenue_exposure
FROM supplier sup
JOIN product p
    ON sup.supplier_id = p.supplier_id
JOIN sales s
    ON p.product_id = s.product_id
GROUP BY sup.supplier_name
ORDER BY revenue_exposure DESC;

-- 10. Reorder recommendation using lead-time demand
WITH demand AS (
    SELECT
        s.product_id,
        s.store_id,
        SUM(s.quantity_sold) / 365.0 AS avg_daily_demand
    FROM sales s
    GROUP BY s.product_id, s.store_id
)
SELECT
    st.store_name,
    p.product_name,
    p.category,
    i.current_stock,
    p.lead_time,
    ROUND(COALESCE(d.avg_daily_demand, 0) * p.lead_time, 0) AS lead_time_demand,
    p.reorder_point AS current_reorder_point,
    CASE
        WHEN i.current_stock <= p.reorder_point THEN 'Create purchase order'
        WHEN i.current_stock / NULLIF(d.avg_daily_demand, 0) > 120 THEN 'Freeze reorder or transfer stock'
        ELSE 'Monitor'
    END AS recommendation
FROM inventory i
JOIN product p
    ON i.product_id = p.product_id
JOIN store st
    ON i.store_id = st.store_id
LEFT JOIN demand d
    ON i.product_id = d.product_id
   AND i.store_id = d.store_id
ORDER BY recommendation, current_stock;
