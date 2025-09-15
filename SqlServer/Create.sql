USE dept_emp_bitemporal;
GO

-- ============================================================
-- Utility function
-- ============================================================
CREATE OR ALTER FUNCTION dbo.fn_infinity()
RETURNS DATETIME2(7)
AS
BEGIN
    RETURN '9999-12-31 23:59:59.9999999';
END;
GO

-- ============================================================
-- Cleanup
-- ============================================================
IF OBJECT_ID('dbo.employee', 'U') IS NOT NULL 
    DROP TABLE dbo.employee;
IF OBJECT_ID('dbo.department', 'U') IS NOT NULL 
    DROP TABLE dbo.department;
IF OBJECT_ID('dbo.department_master', 'U') IS NOT NULL 
    DROP TABLE dbo.department_master;
IF OBJECT_ID('dbo.vw_department_current', 'V') IS NOT NULL 
    DROP VIEW dbo.vw_department_current;
GO

-- ============================================================
-- Department Master Table
-- ============================================================
CREATE TABLE dbo.department_master (
    dept_id INT PRIMARY KEY,
    created_ts DATETIME2(7) NOT NULL DEFAULT SYSUTCDATETIME()
);
GO

-- ============================================================
-- Department History Table
-- ============================================================
CREATE TABLE dbo.department (
    dept_hist_id BIGINT IDENTITY PRIMARY KEY,
    dept_id      INT NOT NULL,
    dept_name    NVARCHAR(200) NOT NULL,
    location     NVARCHAR(200),
    valid_from   DATETIME2(7) NOT NULL,
    valid_to     DATETIME2(7) NOT NULL,
    tran_from    DATETIME2(7) NOT NULL,
    tran_to      DATETIME2(7) NOT NULL,
    CONSTRAINT uq_department_version UNIQUE (dept_id, valid_from, tran_from),
    CONSTRAINT fk_department_master FOREIGN KEY (dept_id) REFERENCES dbo.department_master(dept_id)
);
GO

-- ============================================================
-- Employee History Table
-- ============================================================
CREATE TABLE dbo.employee (
    emp_hist_id  BIGINT IDENTITY PRIMARY KEY,
    emp_id       INT NOT NULL,
    dept_id      INT NOT NULL,
    first_name   NVARCHAR(100) NOT NULL,
    last_name    NVARCHAR(100) NOT NULL,
    job_title    NVARCHAR(200),
    hire_date    DATE NOT NULL,
    term_date    DATE NULL,
    valid_from   DATETIME2(7) NOT NULL,
    valid_to     DATETIME2(7) NOT NULL,
    tran_from    DATETIME2(7) NOT NULL,
    tran_to      DATETIME2(7) NOT NULL,
    CONSTRAINT uq_employee_version UNIQUE (emp_id, valid_from, tran_from),
    CONSTRAINT fk_employee_department FOREIGN KEY (dept_id) REFERENCES dbo.department_master(dept_id)
);
GO

-- ============================================================
-- Current Department View
-- ============================================================
CREATE VIEW dbo.vw_department_current
AS
SELECT d.*
FROM dbo.department d
WHERE SYSUTCDATETIME() >= d.valid_from 
  AND SYSUTCDATETIME() < d.valid_to
  AND SYSUTCDATETIME() >= d.tran_from 
  AND SYSUTCDATETIME() < d.tran_to;
GO

-- ============================================================
-- Department Update Trigger
-- ============================================================
CREATE OR ALTER TRIGGER 
	dbo.tr_department_update
ON 
	dbo.department
INSTEAD OF UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    IF (UPDATE(tran_from) OR UPDATE(tran_to) OR UPDATE(valid_to))
    BEGIN
        THROW 50001, 'Updates to tran_from, tran_to, or valid_to are not allowed.', 1;
        ROLLBACK TRANSACTION;
        RETURN;
    END;

    IF NOT UPDATE(valid_from)
    BEGIN
        THROW 50002, 'A valid_from date is required.', 1;
        ROLLBACK TRANSACTION;
        RETURN;
    END;

    DECLARE @now DATETIME2(7) = SYSUTCDATETIME();

    -- Backfill record
    INSERT INTO 
		dbo.department 
	(
        dept_id, 
		dept_name, 
		location,
        valid_from, 
		valid_to, 
		tran_from, 
		tran_to
    )
    SELECT
        d.dept_id,
        d.dept_name,
        d.location,
        d.valid_from,
        i.valid_from,
        @now,
        dbo.fn_infinity()
    FROM 
		deleted d
    JOIN 
		inserted i 
	ON 
		d.dept_hist_id = i.dept_hist_id
    WHERE 
		i.valid_from >= d.valid_from 
	AND 
		i.valid_from < d.valid_to
    AND 
		d.tran_to = dbo.fn_infinity()
    AND 
		d.valid_from != i.valid_from;

    -- Close old version
    UPDATE 
		dbo.Department
    SET 
		tran_to = @now
    FROM 
		dbo.department dpt
    JOIN 
		deleted d 
	ON 
		dpt.dept_hist_id = d.dept_hist_id
    JOIN 
		inserted i 
	ON 
		d.dept_hist_id = i.dept_hist_id
    WHERE 
		i.valid_from >= d.valid_from 
	AND 
		i.valid_from < d.valid_to
    AND 
		d.tran_to = dbo.fn_infinity();

    -- Insert new version
    INSERT INTO 
		dbo.department 
	(
        dept_id, 
		dept_name, 
		location,
        valid_from, 
		valid_to, 
		tran_from, 
		tran_to
    )
    SELECT
        i.dept_id,
        i.dept_name,
        i.location,
        i.valid_from,
        i.valid_to,
        @now,
        dbo.fn_infinity()
    FROM 
		deleted d
    JOIN 
		inserted i 
	ON 
		d.dept_hist_id = i.dept_hist_id
    WHERE 
		i.valid_from >= d.valid_from 
	AND 
		i.valid_from < d.valid_to
    AND 
		i.tran_to = dbo.fn_infinity();
END;
GO

-- ============================================================
-- Department Getter Procedure
-- ============================================================
CREATE OR ALTER PROCEDURE 
	dbo.get_department
    @dept_id    INT,
    @tran_date  DATETIME2(7) = NULL,
    @valid_date DATETIME2(7) = NULL
AS
BEGIN
    SET @valid_date = ISNULL(@valid_date, SYSUTCDATETIME());
    SET @tran_date = ISNULL(@tran_date, SYSUTCDATETIME());

    SELECT 
        @tran_date AS tran_date,
        @valid_date AS valid_date,
        d.*
    FROM 
		dbo.department d
    WHERE 
		d.dept_id = @dept_id
    AND 
		@valid_date >= d.valid_from 
	AND 
		@valid_date < d.valid_to
    AND 
		@tran_date >= d.tran_from 
	AND 
		@tran_date < d.tran_to;
END;
GO

-- ============================================================
-- Reset Data Procedure
-- ============================================================
CREATE OR ALTER PROCEDURE 
	dbo.reset_data
AS 
BEGIN
    SET NOCOUNT ON;

    DELETE FROM dbo.employee;
    DELETE FROM dbo.department;
    DELETE FROM dbo.department_master;

    DBCC CHECKIDENT ('dbo.department', RESEED, 0);
    DBCC CHECKIDENT ('dbo.employee', RESEED, 0);

    -- Seed department master
    INSERT INTO 
		dbo.department_master (dept_id)
    VALUES 
		(10),
		(20);

    -- Seed department history
    INSERT INTO 
		dbo.department
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
		(10, 'Sales', NULL, '2020-01-01', dbo.fn_infinity(), '2019-12-01', '2020-12-01'),
		(10, 'Sales', NULL, '2020-01-01', '2021-01-01', '2020-12-01', dbo.fn_infinity()),
		(10, 'Sales & Marketing', NULL, '2021-01-01', dbo.fn_infinity(), '2020-12-01', '2021-12-01'),
		(10, 'Sales & Marketing', NULL, '2021-01-01', '2022-01-01', '2021-12-01', dbo.fn_infinity()),
		(10, 'Sales & BizDev', NULL, '2022-01-01', dbo.fn_infinity(), '2021-12-01', dbo.fn_infinity()),
		(20, 'Finance', NULL, '2019-01-01', dbo.fn_infinity(), '2019-01-01', dbo.fn_infinity());

    -- Seed employee history
    INSERT INTO 
		dbo.employee
    (
		emp_id, 
		dept_id, 
		first_name, 
		last_name, 
		job_title, 
		hire_date, 
		valid_from, 
		valid_to, 
		tran_from, 
		tran_to
	)
    VALUES
    (100, 10, 'Alice', 'Smith', 'Sales Rep', '2017-01-01', '2020-01-01', dbo.fn_infinity(), '2019-12-01', '2021-02-01'),
    (100, 10, 'Alice', 'Smith', 'Sales Rep', '2017-01-01', '2020-01-01', '2021-01-01', '2021-02-01', dbo.fn_infinity()),
    (100, 10, 'Alice', 'Smith-Jones', 'Sales Rep', '2017-01-01', '2021-01-01', dbo.fn_infinity(), '2021-02-01', dbo.fn_infinity()),
    (101, 20, 'Bob', 'Jones', 'Accountant', '2018-01-01', '2019-03-01', dbo.fn_infinity(), '2019-12-01', dbo.fn_infinity());
END;
GO

-- Seed data
EXEC dbo.reset_data;
GO

-- Extended functionality 
CREATE OR ALTER FUNCTION dbo.fn_as_of_employee
(
    @valid_date DATETIME2(7),
    @tran_date  DATETIME2(7)
)
RETURNS TABLE
AS
RETURN
(
    SELECT *
    FROM dbo.employee
    WHERE @valid_date >= valid_from
      AND @valid_date < valid_to
      AND @tran_date >= tran_from
      AND @tran_date < tran_to
);
GO

CREATE OR ALTER FUNCTION dbo.fn_as_of_department
(
    @valid_date DATETIME2(7),
    @tran_date  DATETIME2(7)
)
RETURNS TABLE
AS
RETURN
(
    SELECT *
    FROM dbo.department
    WHERE @valid_date >= valid_from
      AND @valid_date < valid_to
      AND @tran_date >= tran_from
      AND @tran_date < tran_to
);
GO
