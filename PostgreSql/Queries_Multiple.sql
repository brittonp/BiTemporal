-- ============================================================
-- Pre-filter bi-temporal tables using CTEs in PostgreSQL
-- ============================================================

WITH 
    params AS (
        SELECT 
            TIMESTAMP '2021-01-15' AS valid_date,
            TIMESTAMP '2021-01-15' AS tran_date
    ),
    as_of_employee AS (
        SELECT e.*
        FROM dbo.employee e, params p
        WHERE p.valid_date >= e.valid_from
          AND p.valid_date < e.valid_to
          AND p.tran_date  >= e.tran_from
          AND p.tran_date  < e.tran_to
    ),
    as_of_department AS (
        SELECT d.*
        FROM dbo.department d, params p
        WHERE p.valid_date >= d.valid_from
          AND p.valid_date < d.valid_to
          AND p.tran_date  >= d.tran_from
          AND p.tran_date  < d.tran_to
    )
-- ============================================================
-- Join filtered tables
-- ============================================================
SELECT
    p.tran_date, 
    p.valid_date,
    d.dept_hist_id,
    d.dept_name,
    e.emp_hist_id,
    e.emp_id,
    e.first_name,
    e.last_name,
    e.job_title,
    e.hire_date,
    e.term_date
FROM as_of_department d
LEFT JOIN as_of_employee e
       ON e.dept_id = d.dept_id
CROSS JOIN params p
WHERE d.dept_id = 10
ORDER BY d.dept_hist_id, e.emp_hist_id;


WITH 
    params AS (
        SELECT 
            TIMESTAMP '2021-01-15' AS valid_date,
            TIMESTAMP '2021-01-15' AS tran_date
    )
SELECT
	p.tran_date, 
	p.valid_date,
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
    params p
CROSS JOIN LATERAL 
	dbo.fn_as_of_department(p.valid_date, p.tran_date) d
LEFT JOIN LATERAL 
	dbo.fn_as_of_employee(p.valid_date, p.tran_date) e
ON 
	e.dept_id = d.dept_id
WHERE 
	d.dept_id = 10
ORDER BY 
	d.dept_hist_id,
	e.emp_hist_id;


