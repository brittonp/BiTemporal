-- ============================================================
-- Cleanup
-- ============================================================
DROP SCHEMA dbo CASCADE;

-- ============================================================
-- Create dbo schema 
-- ============================================================
CREATE SCHEMA dbo;

-- ============================================================
-- Utility function
-- ============================================================
CREATE OR REPLACE FUNCTION dbo.fn_infinity()
RETURNS TIMESTAMP WITH TIME ZONE
LANGUAGE SQL
AS $$
    SELECT '9999-12-31 23:59:59.999999'::timestamptz;
$$;

-- ============================================================
-- Department Master Table
-- ============================================================
CREATE TABLE dbo.department_master (
    dept_id     INT PRIMARY KEY,
    created_ts  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- Department History Table
-- ============================================================
CREATE TABLE dbo.department (
    dept_hist_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dept_id      INT NOT NULL,
    dept_name    VARCHAR(200) NOT NULL,
    location     VARCHAR(200),
    valid_from   TIMESTAMP WITH TIME ZONE NOT NULL,
    valid_to     TIMESTAMP WITH TIME ZONE NOT NULL,
    tran_from    TIMESTAMP WITH TIME ZONE NOT NULL,
    tran_to      TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT uq_department_version UNIQUE (dept_id, valid_from, tran_from),
    CONSTRAINT fk_department_master FOREIGN KEY (dept_id) 
        REFERENCES dbo.department_master(dept_id)
);

-- ============================================================
-- Current Department View
-- ============================================================
CREATE VIEW dbo.vw_department_current
AS
SELECT 
	d.*
FROM 
	dbo.department d
WHERE 
	NOW() >= d.valid_from 
AND 
	NOW() < d.valid_to
AND 
	NOW() >= d.tran_from 
AND 
	NOW() < d.tran_to;

-- ============================================================
-- Employee History Table
-- ============================================================
CREATE TABLE dbo.employee (
    emp_hist_id  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    emp_id       INT NOT NULL,
    dept_id      INT NOT NULL,
    first_name   VARCHAR(100) NOT NULL,
    last_name    VARCHAR(100) NOT NULL,
    job_title    VARCHAR(200),
    hire_date    DATE NOT NULL,
    term_date    DATE,
    valid_from   TIMESTAMP WITH TIME ZONE NOT NULL,
    valid_to     TIMESTAMP WITH TIME ZONE NOT NULL,
    tran_from    TIMESTAMP WITH TIME ZONE NOT NULL,
    tran_to      TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT uq_employee_version UNIQUE (emp_id, valid_from, tran_from),
    CONSTRAINT fk_employee_department FOREIGN KEY (dept_id) 
        REFERENCES dbo.department_master(dept_id)
);


-- ============================================================
-- Reset Data Procedure (schema-qualified)
-- ============================================================
CREATE OR REPLACE PROCEDURE dbo.reset_data()
LANGUAGE plpgsql
AS $$
BEGIN
    -- Delete all data
    DELETE FROM dbo.employee;
    DELETE FROM dbo.department;
    DELETE FROM dbo.department_master;

    -- Reset identity columns (auto-increment sequences)
    ALTER SEQUENCE dbo.department_dept_hist_id_seq RESTART WITH 1;
    ALTER SEQUENCE dbo.employee_emp_hist_id_seq RESTART WITH 1;

    -- Seed department master
    INSERT INTO dbo.department_master (dept_id)
    VALUES (10), (20);

    -- Seed department history
    INSERT INTO dbo.department
        (dept_id, dept_name, location, valid_from, valid_to, tran_from, tran_to)
    VALUES
        (10, 'Sales', NULL, '2020-01-01'::timestamptz, dbo.fn_infinity(), '2019-12-01'::timestamptz, '2020-12-01'::timestamptz),
        (10, 'Sales', NULL, '2020-01-01'::timestamptz, '2021-01-01'::timestamptz, '2020-12-01'::timestamptz, dbo.fn_infinity()),
        (10, 'Sales & Marketing', NULL, '2021-01-01'::timestamptz, dbo.fn_infinity(), '2020-12-01'::timestamptz, '2021-12-01'::timestamptz),
        (10, 'Sales & Marketing', NULL, '2021-01-01'::timestamptz, '2022-01-01'::timestamptz, '2021-12-01'::timestamptz, dbo.fn_infinity()),
        (10, 'Sales & BizDev', NULL, '2022-01-01'::timestamptz, dbo.fn_infinity(), '2021-12-01'::timestamptz, dbo.fn_infinity()),
        (20, 'Finance', NULL, '2019-01-01'::timestamptz, dbo.fn_infinity(), '2019-01-01'::timestamptz, dbo.fn_infinity());

    -- Seed employee history
    INSERT INTO dbo.employee
        (emp_id, dept_id, first_name, last_name, job_title, hire_date, valid_from, valid_to, tran_from, tran_to)
    VALUES
        (100, 10, 'Alice', 'Smith', 'Sales Rep', '2017-01-01'::date, '2020-01-01'::timestamptz, dbo.fn_infinity(), '2019-12-01'::timestamptz, '2021-02-01'::timestamptz),
        (100, 10, 'Alice', 'Smith', 'Sales Rep', '2017-01-01'::date, '2020-01-01'::timestamptz, '2021-01-01'::timestamptz, '2021-02-01'::timestamptz, dbo.fn_infinity()),
        (100, 10, 'Alice', 'Smith-Jones', 'Sales Rep', '2017-01-01'::date, '2021-01-01'::timestamptz, dbo.fn_infinity(), '2021-02-01'::timestamptz, dbo.fn_infinity()),
        (101, 20, 'Bob', 'Jones', 'Accountant', '2018-01-01'::date, '2019-03-01'::timestamptz, dbo.fn_infinity(), '2019-12-01'::timestamptz, dbo.fn_infinity());
END;
$$;

-- Execute the procedure
CALL dbo.reset_data();

-- ============================================================
-- Department Update Trigger 
-- ============================================================
CREATE OR REPLACE FUNCTION dbo.tr_department_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    now_ts TIMESTAMP := NOW();
	affect_dept_hist_id BIGINT;
BEGIN

    -- Disallow updates to dept_id, tran_from, tran_to & valid_to
    IF 
		NEW.dept_id <> OLD.dept_id 
	OR
		NEW.tran_from <> OLD.tran_from 
	OR
		NEW.tran_to <> OLD.tran_to 
	OR	
       	NEW.valid_to  <> OLD.valid_to 
   THEN
        RAISE EXCEPTION 'Updates to tran_from or valid_to are not allowed.';
    END IF;

	-- 1. Find the dept_hist_id to be affected
	SELECT
		d.dept_hist_id
	INTO
		affect_dept_hist_id
    FROM 
		dbo.department d
    WHERE
		OLD.dept_hist_id = d.dept_hist_id
	AND
		NEW.dept_hist_id = OLD.dept_hist_id
    AND 
		NEW.valid_from >= OLD.valid_from 
	AND 
		NEW.valid_from < OLD.valid_to
    AND 
		OLD.tran_to = dbo.fn_infinity();

    -- 2. Only affect the relevant history row, ignore others
	IF affect_dept_hist_id IS NULL THEN
		RETURN NULL;
	ELSE

	    -- 3.a Backfill old version if needed
	    IF 
			NEW.valid_from > OLD.valid_from 
		AND 
			NEW.valid_from < OLD.valid_to 
		THEN
	        INSERT INTO dbo.department 
			(
	            dept_id, 
				dept_name, 
				location,
	            valid_from, 
				valid_to, 
				tran_from, 
				tran_to
	        )
	        VALUES 
			(
	            OLD.dept_id,
	            OLD.dept_name,
	            OLD.location,
	            OLD.valid_from,
	            NEW.valid_from,
	            now_ts,
	            dbo.fn_infinity()
	        );
	    END IF;

	    -- 3.b Insert the new version
	    INSERT INTO dbo.department 
		(
			dept_id, 
			dept_name, 
			location,
			valid_from, 
			valid_to, 
			tran_from, 
			tran_to
	    )
	    VALUES 
		(
	        NEW.dept_id,
	        NEW.dept_name,
	        NEW.location,
	        NEW.valid_from,
	        NEW.valid_to,
	        now_ts,
	        dbo.fn_infinity()
	    );
	
	    -- 3.c Close the old version
		NEW.dept_name = OLD.dept_name;
		NEW.location = OLD.location;
		NEW.valid_from = OLD.valid_from;		
		NEW.tran_to = now_ts;
		
    	RETURN NEW;
	END IF;
		
END;
$$;

CREATE TRIGGER tr_department_update
BEFORE UPDATE ON dbo.department
FOR EACH ROW
EXECUTE FUNCTION dbo.tr_department_update();

