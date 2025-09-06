USE DeptEmpBiTemporalManual;
GO

CREATE OR ALTER FUNCTION dbo.fnInfinity()
RETURNS DATETIME2(7)
AS
BEGIN
	RETURN '9999-12-31 23:59:59.9999999';
END
GO

-- Cleanup
IF OBJECT_ID('dbo.Employee', 'U') IS NOT NULL 
	DROP TABLE dbo.Employee;
IF OBJECT_ID('dbo.Department', 'U') IS NOT NULL 
	DROP TABLE dbo.Department;
IF OBJECT_ID('dbo.Department_Current', 'V') IS NOT NULL 
	DROP VIEW dbo.Department_Current;
GO

CREATE TABLE dbo.Department (
    DeptHistID  BIGINT IDENTITY PRIMARY KEY,   -- surrogate per version
    DeptID      INT NOT NULL,                  -- business key
    DeptName    NVARCHAR(200) NOT NULL,
    Location    NVARCHAR(200),
    ValidFrom   DATETIME2(7) NOT NULL,
    ValidTo     DATETIME2(7) NOT NULL,
    TranFrom    DATETIME2(7) NOT NULL,
    TranTo      DATETIME2(7) NOT NULL,
    CONSTRAINT UQ_Department_Version UNIQUE (DeptID, ValidFrom, TranFrom)
);
GO

CREATE VIEW dbo.Department_Current
AS
SELECT
	d.*
FROM
	dbo.Department d
WHERE 
	SYSUTCDATETIME() >= d.ValidFrom 
AND 
	SYSUTCDATETIME() < d.ValidTo
AND 
	SYSUTCDATETIME() >= d.TranFrom 
AND 
	SYSUTCDATETIME() < d.TranTo
GO

CREATE OR ALTER TRIGGER dbo.tr_Department_Update
ON dbo.Department
INSTEAD OF UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    -- Check if forbidden columns are being updated
    IF (UPDATE(TranFrom) OR UPDATE(TranTo) OR UPDATE(ValidTo))
    BEGIN
        THROW 50001, 'Updates to TranFrom, TranTo, or ValidTo are not allowed.', 1;
        ROLLBACK TRANSACTION;
        RETURN;
    END;

	-- Check mandatory columns are being updated
    IF NOT UPDATE(ValidFrom)
    BEGIN
        THROW 50002, 'A ValidFrom date is required.', 1;
        ROLLBACK TRANSACTION;
        RETURN;
    END;

    DECLARE @Now DATETIME2(7) = SYSUTCDATETIME();

    -- Insert a new old record with the known ValidTo date (from the new ValidFrom)...
    -- This is the backfill record to cover the valid period from the old records valid_from to the new records valid_from.
	-- So do not create a record if d.ValidFrom = i.ValidFrom
    INSERT INTO dbo.Department 
	(
		DeptID, 
		DeptName, 
		Location, 
		ValidFrom, 
		ValidTo, 
		TranFrom, 
		TranTo
	)
	SELECT
		d.DeptID,
		d.DeptName,
		d.Location,
		d.ValidFrom,
		i.ValidFrom,
		@Now,
		dbo.fnInfinity()
	FROM 
		deleted d 
	JOIN 
		inserted i 
	ON 
		d.DeptHistID = i.DeptHistID
	WHERE    
		i.ValidFrom >= d.ValidFrom AND i.ValidFrom < d.ValidTo
	AND
		d.TranTo = dbo.fnInfinity()
	AND
			d.ValidFrom != i.ValidFrom;

    -- Close transaction time on old record
	UPDATE dbo.Department
	SET 
		TranTo = @Now
	FROM 
		dbo.Department dpt
	JOIN 
		deleted d 
	ON 
		dpt.DeptHistID = d.DeptHistID
	JOIN 
		inserted i 
	ON 
		d.DeptHistID = i.DeptHistID
	WHERE 
		i.ValidFrom >= d.ValidFrom AND i.ValidFrom < d.ValidTo
	AND
		d.TranTo = dbo.fnInfinity();

    -- Insert new version
	INSERT INTO dbo.Department 
	(
		DeptID, 
		DeptName, 
		Location, 
		ValidFrom, 
		ValidTo, 
		TranFrom, 
		TranTo
	)
	SELECT
		i.DeptID,
		i.DeptName,
		i.Location,
		i.ValidFrom,
		i.ValidTo,
		@Now,
		dbo.fnInfinity()
	FROM
 		deleted d 
	JOIN 
		inserted i
	ON 
		d.DeptHistID = i.DeptHistID
	WHERE 
		i.ValidFrom >= d.ValidFrom AND i.ValidFrom < d.ValidTo
	AND
		i.TranTo = dbo.fnInfinity();

END
GO

CREATE OR ALTER PROCEDURE dbo.Get_Department 
	@DeptID      INT,
	@TranDate    DATETIME2(7) = NULL,
	@ValidDate   DATETIME2(7) = NULL
AS

	SET @ValidDate = ISNULL(@ValidDate, SYSUTCDATETIME());
	SET @TranDate = ISNULL(@TranDate, SYSUTCDATETIME());

	SELECT 
		@TranDate AS TranDate,
		@ValidDate AS ValidDate,
		d.*
	FROM 
		dbo.Department d
	WHERE
		DeptID = 10
	AND 
		@ValidDate >= d.ValidFrom AND @ValidDate < d.ValidTo
	AND 
		@TranDate >= d.TranFrom AND @TranDate < d.TranTo

RETURN;
GO


-- Seed some data
CREATE OR ALTER PROCEDURE dbo.Reset_Data
AS 
BEGIN
    SET NOCOUNT ON;

	DELETE FROM
		dbo.Department;

    -- Reset the identity so the next row inserted will start at 1
    DBCC CHECKIDENT ('dbo.Department', RESEED, 0);


	-- Initial recording on 1999-12-01 (DB thinks it is valid forever)
	INSERT INTO dbo.Department
	(
		DeptID, 
		DeptName, 
		Location, 
		ValidFrom, 
		ValidTo, 
		TranFrom, 
		TranTo
	)
	VALUES
	(
		10, 
		'Sales', 
		NULL,
		'2020-01-01', 
		dbo.fnInfinity(),   -- unknown end date
		'2019-12-01', 
		'2020-12-01'  -- superseded in 2020
	),
	(
		10, 
		'Sales', 
		NULL,
		'2020-01-01', 
		'2021-01-01',   -- now we know it ends here
		'2020-12-01', 
		dbo.fnInfinity()  -- current until another change
		),
	(
		10, 
		'Sales & Marketing', 
		NULL,
		'2021-01-01', 
		dbo.fnInfinity(),   -- no known end yet
		'2020-12-01', 
		'2021-12-01'  -- superseded in 2021
	),
	(
		10, 
		'Sales & Marketing', 
		NULL,
		'2021-01-01', 
		'2022-01-01',
		'2021-12-01', 
		dbo.fnInfinity()
	),
	(
		10, 
		'Sales & BizDev', 
		NULL,
		'2022-01-01', 
		dbo.fnInfinity(),
		'2021-12-01', 
		dbo.fnInfinity()
	),
	(
		20, 
		'Finance',
			NULL,
		'2019-01-01', 
		dbo.fnInfinity(),
		'2019-01-01', 
		dbo.fnInfinity()
	);
END;
GO

EXEC dbo.Reset_Data
GO
