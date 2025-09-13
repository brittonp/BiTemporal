USE dept_emp_bitemporal_manual;
GO

-- ============================================================
-- Update department name and valid_from for dept_id = 10
-- ============================================================
UPDATE dbo.department
SET
    dept_name = 'New Sales',
    valid_from = '2025-10-01'
WHERE 
    dept_id = 10;
GO

-- ============================================================
-- Select department history for dept_id = 10
-- ============================================================
SELECT
    d.dept_hist_id,
    d.dept_id,
    d.dept_name,
    d.location,
    d.valid_from,
    CASE
        WHEN d.valid_to = dbo.fn_infinity() THEN NULL
        ELSE d.valid_to
    END AS valid_to,
    d.tran_from,
    CASE
        WHEN d.tran_to = dbo.fn_infinity() THEN NULL
        ELSE d.tran_to
    END AS tran_to
FROM 
	dbo.department d
WHERE 
	d.dept_id = 10
ORDER BY 
	d.dept_hist_id;
GO

-- ============================================================
-- Revert department name for dept_id = 10 to 'Original Sales'
-- ============================================================
UPDATE dbo.department
SET
    dept_name = 'Original Sales',
    valid_from = '2020-06-01'
WHERE 
    dept_id = 10;
GO

UPDATE dbo.department
SET
    dept_name = 'Original Sales',
    valid_from = '2021-01-01'
WHERE 
    dept_id = 10;
GO

-- ============================================================
-- Select full department history for dept_id = 10
-- ============================================================
SELECT 
	*
FROM 
	dbo.department
WHERE 
	dept_id = 10
ORDER BY 
	dept_hist_id;
GO

-- ============================================================
-- Optional queries / testing department current view or getter procedure
-- Uncomment as needed
-- ============================================================

--SELECT * FROM dbo.vw_department_current;

--EXEC dbo.get_department @dept_id = 10;
--EXEC dbo.get_department @dept_id = 10, @tran_date = '2025-01-01', @valid_date = '2026-01-01';
--EXEC dbo.get_department @dept_id = 10, @tran_date = '2026-01-01', @valid_date = '2026-01-01';
--EXEC dbo.get_department @dept_id = 10, @tran_date = '2026-01-01', @valid_date = '2023-01-01';
--EXEC dbo.get_department @dept_id = 10, @tran_date = '2026-01-01', @valid_date = '2021-09-01';
--EXEC dbo.get_department @dept_id = 10, @tran_date = '2025-01-01', @valid_date = '2021-09-01';
GO

-- ============================================================
-- Check current UTC datetime
-- ============================================================
SELECT SYSUTCDATETIME();
GO