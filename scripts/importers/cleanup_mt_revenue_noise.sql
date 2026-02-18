-- One-time cleanup for legacy MT importer noise rows.
-- Usage:
--   sqlite3 data/leads.db < scripts/importers/cleanup_mt_revenue_noise.sql

.headers on
.mode column

SELECT 'pre_delete_count' AS metric, COUNT(*) AS value
FROM registries
WHERE registry_source = 'mt_revenue'
  AND (
    LOWER(COALESCE(business_name, '')) LIKE '%informational purposes%'
    OR LOWER(COALESCE(business_name, '')) LIKE 'page % of %'
    OR LOWER(COALESCE(business_name, '')) LIKE '%revenue.mt.gov%'
    OR LOWER(COALESCE(business_name, '')) LIKE '%montana relay%'
    OR LOWER(COALESCE(business_name, '')) LIKE '%governor%'
    OR LOWER(COALESCE(business_name, '')) LIKE '%director%'
    OR LOWER(COALESCE(business_name, '')) LIKE '%cannabis control division%'
    OR LOWER(COALESCE(business_name, '')) LIKE '%licensee%name%city%location%name%phone%'
  );

DELETE FROM registries
WHERE registry_source = 'mt_revenue'
  AND (
    LOWER(COALESCE(business_name, '')) LIKE '%informational purposes%'
    OR LOWER(COALESCE(business_name, '')) LIKE 'page % of %'
    OR LOWER(COALESCE(business_name, '')) LIKE '%revenue.mt.gov%'
    OR LOWER(COALESCE(business_name, '')) LIKE '%montana relay%'
    OR LOWER(COALESCE(business_name, '')) LIKE '%governor%'
    OR LOWER(COALESCE(business_name, '')) LIKE '%director%'
    OR LOWER(COALESCE(business_name, '')) LIKE '%cannabis control division%'
    OR LOWER(COALESCE(business_name, '')) LIKE '%licensee%name%city%location%name%phone%'
  );

SELECT changes() AS deleted_rows;

SELECT 'post_delete_count' AS metric, COUNT(*) AS value
FROM registries
WHERE registry_source = 'mt_revenue'
  AND (
    LOWER(COALESCE(business_name, '')) LIKE '%informational purposes%'
    OR LOWER(COALESCE(business_name, '')) LIKE 'page % of %'
    OR LOWER(COALESCE(business_name, '')) LIKE '%revenue.mt.gov%'
    OR LOWER(COALESCE(business_name, '')) LIKE '%montana relay%'
    OR LOWER(COALESCE(business_name, '')) LIKE '%governor%'
    OR LOWER(COALESCE(business_name, '')) LIKE '%director%'
    OR LOWER(COALESCE(business_name, '')) LIKE '%cannabis control division%'
    OR LOWER(COALESCE(business_name, '')) LIKE '%licensee%name%city%location%name%phone%'
  );
