USE scms delivery dataset;
DROP TABLE IF EXISTS ods_order;
CREATE TABLE ods_order AS
SELECT
  CAST(ID AS UNSIGNED) AS id,
  NULLIF(TRIM(Project Code), '') AS project_code,
  NULLIF(TRIM(PQ #), '') AS pq_number,
  NULLIF(TRIM(PO / SO #), '') AS po_so_number,
  NULLIF(TRIM(ASN/DN #), '') AS asn_dn_number,
  NULLIF(TRIM(Managed By), '') AS managed_by
FROM order;
DROP TABLE IF EXISTS ods_order_detail;
CREATE TABLE ods_order_detail AS
SELECT
  CAST(ID AS UNSIGNED) AS id,
  CAST(Line Item Quantity AS DECIMAL(18,2)) AS line_item_quantity,
  CAST(Pack Price AS DECIMAL(18,4)) AS pack_price,
  CAST(Unit Price AS DECIMAL(18,4)) AS unit_price,
  CAST(Line Item Value AS DECIMAL(18,2)) AS line_item_value,
  NULLIF(TRIM(First Line Designation), '') AS first_line_designation
FROM order_detail;
DROP TABLE IF EXISTS ods_product;
CREATE TABLE ods_product AS
SELECT
  CAST(ID AS UNSIGNED) AS id,
  NULLIF(TRIM(Product Group), '') AS product_group,
  NULLIF(TRIM(Sub Classification), '') AS sub_classification,
  NULLIF(TRIM(Item Description), '') AS item_description,
  NULLIF(TRIM(Molecule/Test Type), '') AS molecule_test_type,
  NULLIF(TRIM(Brand), '') AS brand,
  NULLIF(TRIM(Dosage), '') AS dosage,
  NULLIF(TRIM(Dosage Form), '') AS dosage_form,
  CAST(Unit of Measure (Per Pack) AS DECIMAL(18,2)) AS unit_of_measure_per_pack
FROM product;
DROP TABLE IF EXISTS ods_vendor;
CREATE TABLE ods_vendor AS
SELECT
  CAST(ID AS UNSIGNED) AS id,
  NULLIF(TRIM(Vendor), '') AS vendor_name,
  NULLIF(TRIM(Manufacturing Site), '') AS manufacturing_site
FROM vendor;
DROP TABLE IF EXISTS ods_shipment;
CREATE TABLE ods_shipment AS
SELECT
  CAST(ID AS UNSIGNED) AS id,
  NULLIF(TRIM(Country), '') AS country,
  NULLIF(TRIM(Fulfill Via), '') AS fulfill_via,
  NULLIF(TRIM(Vendor INCO Term), '') AS vendor_inco_term,
  NULLIF(TRIM(Shipment Mode), '') AS shipment_mode,
  COALESCE(
    STR_TO_DATE(NULLIF(TRIM(PQ First Sent to Client Date), 'Date Not Captured'), '%e-%b-%y'),
    STR_TO_DATE(NULLIF(TRIM(PQ First Sent to Client Date), 'Date Not Captured'), '%c/%e/%y'),
    STR_TO_DATE(NULLIF(TRIM(PQ First Sent to Client Date), 'Date Not Captured'), '%Y/%c/%e')
  ) AS pq_first_sent_date,
  COALESCE(
    STR_TO_DATE(NULLIF(NULLIF(TRIM(PO Sent to Vendor Date), 'Date Not Captured'), 'N/A - From RDC'), '%e-%b-%y'),
    STR_TO_DATE(NULLIF(NULLIF(TRIM(PO Sent to Vendor Date), 'Date Not Captured'), 'N/A - From RDC'), '%c/%e/%y'),
    STR_TO_DATE(NULLIF(NULLIF(TRIM(PO Sent to Vendor Date), 'Date Not Captured'), 'N/A - From RDC'), '%Y/%c/%e')
  ) AS po_sent_date,
  COALESCE(
    STR_TO_DATE(NULLIF(TRIM(Scheduled Delivery Date), 'Date Not Captured'), '%e-%b-%y'),
    STR_TO_DATE(NULLIF(TRIM(Scheduled Delivery Date), 'Date Not Captured'), '%c/%e/%y'),
    STR_TO_DATE(NULLIF(TRIM(Scheduled Delivery Date), 'Date Not Captured'), '%Y/%c/%e')
  ) AS scheduled_delivery_date,
  COALESCE(
    STR_TO_DATE(NULLIF(TRIM(Delivered to Client Date), 'Date Not Captured'), '%e-%b-%y'),
    STR_TO_DATE(NULLIF(TRIM(Delivered to Client Date), 'Date Not Captured'), '%c/%e/%y'),
    STR_TO_DATE(NULLIF(TRIM(Delivered to Client Date), 'Date Not Captured'), '%Y/%c/%e')
  ) AS delivered_to_client_date,
  COALESCE(
    STR_TO_DATE(NULLIF(TRIM(Delivery Recorded Date), 'Date Not Captured'), '%e-%b-%y'),
    STR_TO_DATE(NULLIF(TRIM(Delivery Recorded Date), 'Date Not Captured'), '%c/%e/%y'),
    STR_TO_DATE(NULLIF(TRIM(Delivery Recorded Date), 'Date Not Captured'), '%Y/%c/%e')
  ) AS delivery_recorded_date,
  CAST(Weight (Kilograms) AS DECIMAL(18,2)) AS weight_kg,
  CAST(Freight Cost (USD) AS DECIMAL(18,2)) AS freight_cost_usd,
  CAST(NULLIF(TRIM(Line Item Insurance (USD)), '') AS DECIMAL(18,2)) AS insurance_cost_usd
FROM shipment;
DROP TABLE IF EXISTS check_ods_table_counts;
CREATE TABLE check_ods_table_counts AS
SELECT 'ods_order' AS table_name, COUNT() AS row_count, COUNT(DISTINCT id) AS distinct_id_count, COUNT() - COUNT(DISTINCT id) AS duplicate_id_count FROM ods_order
UNION ALL
SELECT 'ods_order_detail', COUNT(), COUNT(DISTINCT id), COUNT() - COUNT(DISTINCT id) FROM ods_order_detail
UNION ALL
SELECT 'ods_product', COUNT(), COUNT(DISTINCT id), COUNT() - COUNT(DISTINCT id) FROM ods_product
UNION ALL
SELECT 'ods_vendor', COUNT(), COUNT(DISTINCT id), COUNT() - COUNT(DISTINCT id) FROM ods_vendor
UNION ALL
SELECT 'ods_shipment', COUNT(), COUNT(DISTINCT id), COUNT() - COUNT(DISTINCT id) FROM ods_shipment;
DROP TABLE IF EXISTS agg_order;
CREATE TABLE agg_order AS
SELECT
  id,
  MIN(project_code) AS project_code,
  MIN(pq_number) AS pq_number,
  MIN(po_so_number) AS po_so_number,
  MIN(asn_dn_number) AS asn_dn_number,
  MIN(managed_by) AS managed_by
FROM ods_order
GROUP BY id;
DROP TABLE IF EXISTS agg_order_detail;
CREATE TABLE agg_order_detail AS
SELECT
  id,
  SUM(line_item_quantity) AS line_item_quantity,
  AVG(pack_price) AS pack_price,
  AVG(unit_price) AS unit_price,
  SUM(line_item_value) AS line_item_value,
  MIN(first_line_designation) AS first_line_designation
FROM ods_order_detail
GROUP BY id;
DROP TABLE IF EXISTS agg_product;
CREATE TABLE agg_product AS
SELECT
  id,
  COUNT(DISTINCT product_group) AS product_group_count,
  MIN(product_group) AS product_group,
  MIN(sub_classification) AS sub_classification,
  MIN(item_description) AS item_description,
  MIN(molecule_test_type) AS molecule_test_type,
  MIN(brand) AS brand,
  MIN(dosage) AS dosage,
  MIN(dosage_form) AS dosage_form,
  AVG(unit_of_measure_per_pack) AS unit_of_measure_per_pack
FROM ods_product
GROUP BY id;
DROP TABLE IF EXISTS agg_vendor;
CREATE TABLE agg_vendor AS
SELECT
  id,
  MIN(vendor_name) AS vendor_name,
  MIN(manufacturing_site) AS manufacturing_site
FROM ods_vendor
GROUP BY id;
DROP TABLE IF EXISTS wide_shipment_base;
CREATE TABLE wide_shipment_base AS
SELECT
  s.id AS shipment_id,
  o.project_code,
  o.pq_number,
  o.po_so_number,
  o.asn_dn_number,
  o.managed_by,
  p.product_group_count,
  p.product_group,
  p.sub_classification,
  p.item_description,
  p.molecule_test_type,
  p.brand,
  p.dosage,
  p.dosage_form,
  p.unit_of_measure_per_pack,
  v.vendor_name,
  v.manufacturing_site,
  od.line_item_quantity,
  od.pack_price,
  od.unit_price,
  od.line_item_value,
  od.first_line_designation,
  s.country,
  s.fulfill_via,
  s.vendor_inco_term,
  s.shipment_mode,
  s.pq_first_sent_date,
  s.po_sent_date,
  s.scheduled_delivery_date,
  s.delivered_to_client_date,
  s.delivery_recorded_date,
  s.weight_kg,
  s.freight_cost_usd,
  s.insurance_cost_usd,
  CASE WHEN s.scheduled_delivery_date IS NULL OR s.delivered_to_client_date IS NULL THEN 1 ELSE 0 END AS is_date_missing,
  DATEDIFF(s.delivered_to_client_date, s.scheduled_delivery_date) AS delay_days,
  CASE WHEN s.scheduled_delivery_date IS NOT NULL AND s.delivered_to_client_date IS NOT NULL AND DATEDIFF(s.delivered_to_client_date, s.scheduled_delivery_date) > 0 THEN 1 ELSE 0 END AS is_delayed,
  CASE WHEN s.weight_kg IS NULL OR s.weight_kg <= 0 THEN 1 ELSE 0 END AS is_weight_invalid,
  CASE WHEN s.weight_kg IS NOT NULL AND s.weight_kg > 0 THEN s.freight_cost_usd / s.weight_kg ELSE NULL END AS freight_per_kg,
  DATEDIFF(s.scheduled_delivery_date, s.po_sent_date) AS planned_lead_days,
  DATEDIFF(s.po_sent_date, s.pq_first_sent_date) AS pq_to_po_days
FROM ods_shipment s
LEFT JOIN agg_order o ON s.id = o.id
LEFT JOIN agg_product p ON s.id = p.id
LEFT JOIN agg_vendor v ON s.id = v.id
LEFT JOIN agg_order_detail od ON s.id = od.id;
DROP TABLE IF EXISTS threshold_global;
CREATE TABLE threshold_global AS
SELECT
  MIN(CASE WHEN rn >= CEIL(n * 0.75) THEN freight_per_kg END) AS freight_per_kg_global_p75,
  MIN(CASE WHEN rn >= CEIL(n * 0.80) THEN freight_per_kg END) AS freight_per_kg_global_p80,
  MIN(CASE WHEN rn >= CEIL(n * 0.90) THEN freight_per_kg END) AS freight_per_kg_global_p90
FROM (
  SELECT
    freight_per_kg,
    ROW_NUMBER() OVER (ORDER BY freight_per_kg) AS rn,
    COUNT(*) OVER () AS n
  FROM wide_shipment_base
  WHERE freight_per_kg IS NOT NULL
) x;
DROP TABLE IF EXISTS threshold_freight_cost_global;
CREATE TABLE threshold_freight_cost_global AS
SELECT
  MIN(CASE WHEN rn >= CEIL(n * 0.80) THEN freight_cost_usd END) AS freight_cost_global_p80
FROM (
  SELECT
    freight_cost_usd,
    ROW_NUMBER() OVER (ORDER BY freight_cost_usd) AS rn,
    COUNT(*) OVER () AS n
  FROM wide_shipment_base
  WHERE freight_cost_usd IS NOT NULL
) x;
DROP TABLE IF EXISTS threshold_mode;
CREATE TABLE threshold_mode AS
SELECT
  shipment_mode,
  MIN(CASE WHEN rn >= CEIL(n * 0.75) THEN freight_per_kg END) AS freight_per_kg_mode_p75,
  MIN(CASE WHEN rn >= CEIL(n * 0.80) THEN freight_per_kg END) AS freight_per_kg_mode_p80,
  MIN(CASE WHEN rn >= CEIL(n * 0.90) THEN freight_per_kg END) AS freight_per_kg_mode_p90
FROM (
  SELECT
    shipment_mode,
    freight_per_kg,
    ROW_NUMBER() OVER (PARTITION BY shipment_mode ORDER BY freight_per_kg) AS rn,
    COUNT(*) OVER (PARTITION BY shipment_mode) AS n
  FROM wide_shipment_base
  WHERE freight_per_kg IS NOT NULL
) x
GROUP BY shipment_mode;
DROP TABLE IF EXISTS threshold_mode_country;
CREATE TABLE threshold_mode_country AS
SELECT
  shipment_mode,
  country,
  CASE WHEN MAX(n) >= 30 THEN MIN(CASE WHEN rn >= CEIL(n * 0.80) THEN freight_per_kg END) ELSE NULL END AS freight_per_kg_mode_country_p80,
  MAX(n) AS group_order_count
FROM (
  SELECT
    shipment_mode,
    country,
    freight_per_kg,
    ROW_NUMBER() OVER (PARTITION BY shipment_mode, country ORDER BY freight_per_kg) AS rn,
    COUNT(*) OVER (PARTITION BY shipment_mode, country) AS n
  FROM wide_shipment_base
  WHERE freight_per_kg IS NOT NULL
) x
GROUP BY shipment_mode, country;
DROP TABLE IF EXISTS threshold_severe_delay;
CREATE TABLE threshold_severe_delay AS
SELECT
  MIN(CASE WHEN rn >= CEIL(n * 0.80) THEN delay_days END) AS severe_delay_p80_threshold
FROM (
  SELECT
    delay_days,
    ROW_NUMBER() OVER (ORDER BY delay_days) AS rn,
    COUNT(*) OVER () AS n
  FROM wide_shipment_base
  WHERE delay_days > 0
) x;
DROP TABLE IF EXISTS wide_shipment_risk;
CREATE TABLE wide_shipment_risk AS
SELECT
  y.,
  CASE
    WHEN y.is_cost_risk = 0 AND y.is_delay_risk = 0 THEN 'normal'
    WHEN y.is_cost_risk = 1 AND y.is_delay_risk = 0 THEN 'cost_risk_only'
    WHEN y.is_cost_risk = 0 AND y.is_delay_risk = 1 THEN 'delay_risk_only'
    WHEN y.is_cost_risk = 1 AND y.is_delay_risk = 1 THEN 'compound_high_risk'
    ELSE 'unclassified'
  END AS risk_segment
FROM (
  SELECT
    x.,
    CASE WHEN x.freight_per_kg IS NOT NULL AND x.freight_per_kg > x.freight_per_kg_mode_p80 THEN 1 ELSE 0 END AS is_cost_risk,
    x.is_delayed AS is_delay_risk,
    CASE WHEN x.freight_per_kg IS NOT NULL AND x.freight_per_kg > x.freight_per_kg_mode_p80 THEN 1 ELSE 0 END
      OR x.is_delayed AS is_high_risk,
    CASE WHEN x.freight_per_kg IS NOT NULL AND x.freight_per_kg > x.freight_per_kg_mode_p80 AND x.is_delayed = 1 THEN 1 ELSE 0 END AS is_compound_high_risk,
    CASE WHEN x.is_delayed = 1 AND x.delay_days > x.severe_delay_p80_threshold THEN 1 ELSE 0 END AS is_severe_delay
  FROM (
    SELECT
      b.*,
      g.freight_per_kg_global_p75,
      g.freight_per_kg_global_p80,
      g.freight_per_kg_global_p90,
      fc.freight_cost_global_p80,
      m.freight_per_kg_mode_p75,
      m.freight_per_kg_mode_p80,
      m.freight_per_kg_mode_p90,
      mc.freight_per_kg_mode_country_p80,
      mc.group_order_count AS mode_country_group_order_count,
      sd.severe_delay_p80_threshold,
      CASE WHEN b.freight_per_kg IS NOT NULL AND b.freight_per_kg > g.freight_per_kg_global_p75 THEN 1 ELSE 0 END AS cost_risk_global_p75,
      CASE WHEN b.freight_per_kg IS NOT NULL AND b.freight_per_kg > g.freight_per_kg_global_p80 THEN 1 ELSE 0 END AS cost_risk_global_p80,
      CASE WHEN b.freight_per_kg IS NOT NULL AND b.freight_per_kg > g.freight_per_kg_global_p90 THEN 1 ELSE 0 END AS cost_risk_global_p90,
      CASE WHEN b.freight_per_kg IS NOT NULL AND b.freight_per_kg > m.freight_per_kg_mode_p75 THEN 1 ELSE 0 END AS cost_risk_mode_p75,
      CASE WHEN b.freight_per_kg IS NOT NULL AND b.freight_per_kg > m.freight_per_kg_mode_p80 THEN 1 ELSE 0 END AS cost_risk_mode_p80,
      CASE WHEN b.freight_per_kg IS NOT NULL AND b.freight_per_kg > m.freight_per_kg_mode_p90 THEN 1 ELSE 0 END AS cost_risk_mode_p90,
      CASE WHEN b.freight_cost_usd IS NOT NULL AND b.freight_cost_usd > fc.freight_cost_global_p80 THEN 1 ELSE 0 END AS is_high_freight_global_p80,
      CASE WHEN mc.freight_per_kg_mode_country_p80 IS NOT NULL THEN 1 ELSE 0 END AS cost_risk_mode_country_available,
      CASE WHEN b.freight_per_kg IS NOT NULL AND mc.freight_per_kg_mode_country_p80 IS NOT NULL AND b.freight_per_kg > mc.freight_per_kg_mode_country_p80 THEN 1 ELSE 0 END AS is_cost_risk_mode_country_p80
    FROM wide_shipment_base b
    CROSS JOIN threshold_global g
    CROSS JOIN threshold_freight_cost_global fc
    CROSS JOIN threshold_severe_delay sd
    LEFT JOIN threshold_mode m ON b.shipment_mode <=> m.shipment_mode
    LEFT JOIN threshold_mode_country mc ON b.shipment_mode <=> mc.shipment_mode AND b.country <=> mc.country
  ) x
) y;
DROP TABLE IF EXISTS check_join_grain;
CREATE TABLE check_join_grain AS
SELECT 'ods_order' AS table_name, COUNT() AS row_count, COUNT(DISTINCT id) AS distinct_id_count, COUNT() - COUNT(DISTINCT id) AS duplicate_id_count FROM ods_order
UNION ALL
SELECT 'ods_order_detail', COUNT(), COUNT(DISTINCT id), COUNT() - COUNT(DISTINCT id) FROM ods_order_detail
UNION ALL
SELECT 'ods_product', COUNT(), COUNT(DISTINCT id), COUNT() - COUNT(DISTINCT id) FROM ods_product
UNION ALL
SELECT 'ods_vendor', COUNT(), COUNT(DISTINCT id), COUNT() - COUNT(DISTINCT id) FROM ods_vendor
UNION ALL
SELECT 'ods_shipment', COUNT(), COUNT(DISTINCT id), COUNT() - COUNT(DISTINCT id) FROM ods_shipment
UNION ALL
SELECT 'wide_shipment_risk', COUNT(), COUNT(DISTINCT shipment_id), COUNT() - COUNT(DISTINCT shipment_id) FROM wide_shipment_risk;
DROP TABLE IF EXISTS check_core_quality;
CREATE TABLE check_core_quality AS
SELECT
  COUNT() AS wide_rows,
  COUNT(DISTINCT shipment_id) AS distinct_shipment_id_count,
  COUNT() - COUNT(DISTINCT shipment_id) AS duplicate_shipment_id_count,
  SUM(is_high_risk) AS high_risk_count,
  ROUND(SUM(is_high_risk) / COUNT(*), 4) AS high_risk_rate,
  SUM(is_cost_risk) AS cost_risk_count,
  SUM(is_delay_risk) AS delay_risk_count,
  SUM(is_compound_high_risk) AS compound_high_risk_count,
  SUM(is_date_missing) AS date_missing_count,
  SUM(is_weight_invalid) AS invalid_weight_count
FROM wide_shipment_risk;
DROP TABLE IF EXISTS check_risk_segment_counts;
CREATE TABLE check_risk_segment_counts AS
SELECT
  risk_segment,
  COUNT() AS order_count,
  ROUND(COUNT() / (SELECT COUNT(*) FROM wide_shipment_risk), 4) AS order_rate,
  ROUND(SUM(freight_cost_usd), 2) AS freight_sum,
  ROUND(AVG(delay_days), 2) AS avg_delay_days
FROM wide_shipment_risk
GROUP BY risk_segment
ORDER BY order_count DESC;
DROP TABLE IF EXISTS check_invalid_weight_records;
CREATE TABLE check_invalid_weight_records AS
SELECT *
FROM wide_shipment_risk
WHERE is_weight_invalid = 1;
DROP TABLE IF EXISTS check_date_missing_records;
CREATE TABLE check_date_missing_records AS
SELECT *
FROM wide_shipment_risk
WHERE is_date_missing = 1;
DROP TABLE IF EXISTS risk_summary_by_country;
CREATE TABLE risk_summary_by_country AS
SELECT
  COALESCE(country, 'Unknown') AS dimension_value,
  COUNT() AS order_count,
  SUM(is_high_risk) AS high_risk_order_count,
  ROUND(SUM(is_high_risk) / COUNT(), 4) AS high_risk_rate,
  ROUND(SUM(freight_cost_usd), 2) AS total_freight,
  ROUND(SUM(CASE WHEN is_high_risk = 1 THEN freight_cost_usd ELSE 0 END), 2) AS high_risk_freight,
  ROUND(SUM(CASE WHEN is_high_risk = 1 THEN freight_cost_usd ELSE 0 END) / NULLIF((SELECT SUM(CASE WHEN is_high_risk = 1 THEN freight_cost_usd ELSE 0 END) FROM wide_shipment_risk), 0), 4) AS high_risk_freight_contribution_rate,
  ROUND(AVG(delay_days), 2) AS avg_delay_days,
  SUM(is_severe_delay) AS severe_delay_order_count,
  SUM(is_compound_high_risk) AS compound_high_risk_order_count,
  SUM(is_cost_risk) AS cost_risk_order_count,
  SUM(is_delay_risk) AS delay_risk_order_count
FROM wide_shipment_risk
GROUP BY COALESCE(country, 'Unknown')
ORDER BY high_risk_freight DESC, high_risk_order_count DESC;
DROP TABLE IF EXISTS risk_summary_by_vendor;
CREATE TABLE risk_summary_by_vendor AS
SELECT
  COALESCE(vendor_name, 'Unknown') AS dimension_value,
  COUNT() AS order_count,
  SUM(is_high_risk) AS high_risk_order_count,
  ROUND(SUM(is_high_risk) / COUNT(), 4) AS high_risk_rate,
  ROUND(SUM(freight_cost_usd), 2) AS total_freight,
  ROUND(SUM(CASE WHEN is_high_risk = 1 THEN freight_cost_usd ELSE 0 END), 2) AS high_risk_freight,
  ROUND(SUM(CASE WHEN is_high_risk = 1 THEN freight_cost_usd ELSE 0 END) / NULLIF((SELECT SUM(CASE WHEN is_high_risk = 1 THEN freight_cost_usd ELSE 0 END) FROM wide_shipment_risk), 0), 4) AS high_risk_freight_contribution_rate,
  ROUND(AVG(delay_days), 2) AS avg_delay_days,
  SUM(is_severe_delay) AS severe_delay_order_count,
  SUM(is_compound_high_risk) AS compound_high_risk_order_count,
  SUM(is_cost_risk) AS cost_risk_order_count,
  SUM(is_delay_risk) AS delay_risk_order_count
FROM wide_shipment_risk
GROUP BY COALESCE(vendor_name, 'Unknown')
ORDER BY high_risk_freight DESC, high_risk_order_count DESC;
DROP TABLE IF EXISTS risk_summary_by_shipment_mode;
CREATE TABLE risk_summary_by_shipment_mode AS
SELECT
  COALESCE(shipment_mode, 'Unknown') AS dimension_value,
  COUNT() AS order_count,
  SUM(is_high_risk) AS high_risk_order_count,
  ROUND(SUM(is_high_risk) / COUNT(), 4) AS high_risk_rate,
  ROUND(SUM(freight_cost_usd), 2) AS total_freight,
  ROUND(SUM(CASE WHEN is_high_risk = 1 THEN freight_cost_usd ELSE 0 END), 2) AS high_risk_freight,
  ROUND(SUM(CASE WHEN is_high_risk = 1 THEN freight_cost_usd ELSE 0 END) / NULLIF((SELECT SUM(CASE WHEN is_high_risk = 1 THEN freight_cost_usd ELSE 0 END) FROM wide_shipment_risk), 0), 4) AS high_risk_freight_contribution_rate,
  ROUND(AVG(delay_days), 2) AS avg_delay_days,
  SUM(is_severe_delay) AS severe_delay_order_count,
  SUM(is_compound_high_risk) AS compound_high_risk_order_count,
  SUM(is_cost_risk) AS cost_risk_order_count,
  SUM(is_delay_risk) AS delay_risk_order_count
FROM wide_shipment_risk
GROUP BY COALESCE(shipment_mode, 'Unknown')
ORDER BY high_risk_freight DESC, high_risk_order_count DESC;
DROP TABLE IF EXISTS risk_summary_by_product_group;
CREATE TABLE risk_summary_by_product_group AS
SELECT
  COALESCE(product_group, 'Unknown') AS dimension_value,
  COUNT() AS order_count,
  SUM(is_high_risk) AS high_risk_order_count,
  ROUND(SUM(is_high_risk) / COUNT(), 4) AS high_risk_rate,
  ROUND(SUM(freight_cost_usd), 2) AS total_freight,
  ROUND(SUM(CASE WHEN is_high_risk = 1 THEN freight_cost_usd ELSE 0 END), 2) AS high_risk_freight,
  ROUND(SUM(CASE WHEN is_high_risk = 1 THEN freight_cost_usd ELSE 0 END) / NULLIF((SELECT SUM(CASE WHEN is_high_risk = 1 THEN freight_cost_usd ELSE 0 END) FROM wide_shipment_risk), 0), 4) AS high_risk_freight_contribution_rate,
  ROUND(AVG(delay_days), 2) AS avg_delay_days,
  SUM(is_severe_delay) AS severe_delay_order_count,
  SUM(is_compound_high_risk) AS compound_high_risk_order_count,
  SUM(is_cost_risk) AS cost_risk_order_count,
  SUM(is_delay_risk) AS delay_risk_order_count
FROM wide_shipment_risk
GROUP BY COALESCE(product_group, 'Unknown')
ORDER BY high_risk_freight DESC, high_risk_order_count DESC;
DROP TABLE IF EXISTS risk_summary_by_country_shipment_mode;
CREATE TABLE risk_summary_by_country_shipment_mode AS
SELECT
  CONCAT(COALESCE(country, 'Unknown'), ' | ', COALESCE(shipment_mode, 'Unknown')) AS dimension_value,
  COUNT() AS order_count,
  SUM(is_high_risk) AS high_risk_order_count,
  ROUND(SUM(is_high_risk) / COUNT(), 4) AS high_risk_rate,
  ROUND(SUM(freight_cost_usd), 2) AS total_freight,
  ROUND(SUM(CASE WHEN is_high_risk = 1 THEN freight_cost_usd ELSE 0 END), 2) AS high_risk_freight,
  ROUND(SUM(CASE WHEN is_high_risk = 1 THEN freight_cost_usd ELSE 0 END) / NULLIF((SELECT SUM(CASE WHEN is_high_risk = 1 THEN freight_cost_usd ELSE 0 END) FROM wide_shipment_risk), 0), 4) AS high_risk_freight_contribution_rate,
  ROUND(AVG(delay_days), 2) AS avg_delay_days,
  SUM(is_severe_delay) AS severe_delay_order_count,
  SUM(is_compound_high_risk) AS compound_high_risk_order_count,
  SUM(is_cost_risk) AS cost_risk_order_count,
  SUM(is_delay_risk) AS delay_risk_order_count
FROM wide_shipment_risk
GROUP BY CONCAT(COALESCE(country, 'Unknown'), ' | ', COALESCE(shipment_mode, 'Unknown'))
ORDER BY high_risk_freight DESC, high_risk_order_count DESC;
DROP TABLE IF EXISTS pareto_country_high_risk_freight;
CREATE TABLE pareto_country_high_risk_freight AS
SELECT
  dimension_value,
  metric_value,
  ROUND(metric_value / NULLIF(SUM(metric_value) OVER (), 0), 4) AS contribution_rate,
  ROUND(SUM(metric_value) OVER (ORDER BY metric_value DESC) / NULLIF(SUM(metric_value) OVER (), 0), 4) AS cumulative_contribution_rate,
  CASE WHEN SUM(metric_value) OVER (ORDER BY metric_value DESC) / NULLIF(SUM(metric_value) OVER (), 0) <= 0.8 THEN 1 ELSE 0 END AS within_first_80_percent
FROM (
  SELECT COALESCE(country, 'Unknown') AS dimension_value, SUM(CASE WHEN is_high_risk = 1 THEN freight_cost_usd ELSE 0 END) AS metric_value
  FROM wide_shipment_risk
  GROUP BY COALESCE(country, 'Unknown')
) x
ORDER BY metric_value DESC;
DROP TABLE IF EXISTS pareto_country_high_risk_order_count;
CREATE TABLE pareto_country_high_risk_order_count AS
SELECT
  dimension_value,
  metric_value,
  ROUND(metric_value / NULLIF(SUM(metric_value) OVER (), 0), 4) AS contribution_rate,
  ROUND(SUM(metric_value) OVER (ORDER BY metric_value DESC) / NULLIF(SUM(metric_value) OVER (), 0), 4) AS cumulative_contribution_rate,
  CASE WHEN SUM(metric_value) OVER (ORDER BY metric_value DESC) / NULLIF(SUM(metric_value) OVER (), 0) <= 0.8 THEN 1 ELSE 0 END AS within_first_80_percent
FROM (
  SELECT COALESCE(country, 'Unknown') AS dimension_value, SUM(is_high_risk) AS metric_value
  FROM wide_shipment_risk
  GROUP BY COALESCE(country, 'Unknown')
) x
ORDER BY metric_value DESC;
DROP TABLE IF EXISTS pareto_country_compound_high_risk_order_count;
CREATE TABLE pareto_country_compound_high_risk_order_count AS
SELECT
  dimension_value,
  metric_value,
  ROUND(metric_value / NULLIF(SUM(metric_value) OVER (), 0), 4) AS contribution_rate,
  ROUND(SUM(metric_value) OVER (ORDER BY metric_value DESC) / NULLIF(SUM(metric_value) OVER (), 0), 4) AS cumulative_contribution_rate,
  CASE WHEN SUM(metric_value) OVER (ORDER BY metric_value DESC) / NULLIF(SUM(metric_value) OVER (), 0) <= 0.8 THEN 1 ELSE 0 END AS within_first_80_percent
FROM (
  SELECT COALESCE(country, 'Unknown') AS dimension_value, SUM(is_compound_high_risk) AS metric_value
  FROM wide_shipment_risk
  GROUP BY COALESCE(country, 'Unknown')
) x
ORDER BY metric_value DESC;
DROP TABLE IF EXISTS pareto_country_positive_delay_days;
CREATE TABLE pareto_country_positive_delay_days AS
SELECT
  dimension_value,
  metric_value,
  ROUND(metric_value / NULLIF(SUM(metric_value) OVER (), 0), 4) AS contribution_rate,
  ROUND(SUM(metric_value) OVER (ORDER BY metric_value DESC) / NULLIF(SUM(metric_value) OVER (), 0), 4) AS cumulative_contribution_rate,
  CASE WHEN SUM(metric_value) OVER (ORDER BY metric_value DESC) / NULLIF(SUM(metric_value) OVER (), 0) <= 0.8 THEN 1 ELSE 0 END AS within_first_80_percent
FROM (
  SELECT COALESCE(country, 'Unknown') AS dimension_value, SUM(CASE WHEN delay_days > 0 THEN delay_days ELSE 0 END) AS metric_value
  FROM wide_shipment_risk
  GROUP BY COALESCE(country, 'Unknown')
) x
ORDER BY metric_value DESC;