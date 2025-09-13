USE dept_emp_bitemporal_manual
GO

DECLARE @valid_date DATETIME2(7) = SYSUTCDATETIME();
DECLARE @tran_date DATETIME2(7) = SYSUTCDATETIME();

--SET @tran_date = '2021-01-15';
--SET @valid_date = '2021-01-15';

-- ============================================================
-- Pre-filter bi-temporal tables using CTEs
-- ============================================================
WITH 
	as_of_employee 
AS
(
    SELECT 
		*
    FROM 
		dbo.employee
    WHERE 
		@valid_date >= valid_from
	AND 
		@valid_date < valid_to
	AND 
		@tran_date >= tran_from
	AND 
		@tran_date < tran_to
),
	as_of_department 
AS
(
    SELECT 
		*
    FROM 
		dbo.department
    WHERE 
		@valid_date >= valid_from
	AND 
		@valid_date < valid_to
	AND 
		@tran_date >= tran_from
	AND 
		@tran_date < tran_to
)
-- ============================================================
-- Join filtered tables
-- ============================================================
SELECT
	@tran_date AS tran_date, 
	@valid_date AS valid_date,
    d.dept_hist_id,
    d.dept_name,
    e.emp_hist_id,
    e.emp_id,
    e.first_name,
    e.last_name,
    e.job_title,
    e.hire_date,
    e.term_date
FROM 
	as_of_department d
LEFT JOIN
	as_of_employee e
ON 
	e.dept_id = d.dept_id
WHERE 
	d.dept_id = 10
ORDER BY 
	d.dept_hist_id,
	e.emp_hist_id;

SELECT
	@tran_date AS tran_date, 
	@valid_date AS valid_date,
    d.dept_hist_id,
    d.dept_name,
    e.emp_hist_id,
    e.emp_id,
    e.first_name,
    e.last_name,
    e.job_title,
    e.hire_date,
    e.term_date
FROM 
	dbo.fn_as_of_department(@valid_date, @tran_date) d
LEFT JOIN
	dbo.fn_as_of_employee(@valid_date, @tran_date) e
ON 
	e.dept_id = d.dept_id
WHERE 
	d.dept_id = 10
ORDER BY 
	d.dept_hist_id,
	e.emp_hist_id;
GO
