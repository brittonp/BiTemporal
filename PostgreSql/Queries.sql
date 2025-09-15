-- ============================================================
-- Update department name and valid_from for dept_id = 10
-- ============================================================
UPDATE dbo.department
SET
    dept_name = 'New Sales2',
    valid_from = '2025-10-01'
WHERE 
    dept_id = 10;

-- ============================================================
-- Revert department name for dept_id = 10 to 'Original Sales'
-- ============================================================
UPDATE dbo.department
SET
    dept_name = 'Original Sales',
    valid_from = '2020-01-01'
WHERE 
    dept_id = 30;

-- ============================================================
-- Select department history for dept_id = 10
-- ============================================================
SELECT
    d.*
FROM 
	dbo.department d
WHERE 
	d.dept_id = 10
ORDER BY 
	d.dept_hist_id;

    