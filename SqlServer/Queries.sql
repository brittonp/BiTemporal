USE DeptEmpBiTemporalManual;
GO

UPDATE
	dbo.Department
SET
	DeptName = 'New Sales',
	ValidFrom = '2025-10-01'
WHERE 
	DeptID = 10
;

SELECT
	d.DeptHistID, 
	d.DeptID, 
	d.DeptName, 
	d.Location, 
	d.ValidFrom, 
	CASE
		WHEN d.ValidTo = dbo.fnInfinity() THEN NULL
		ELSE d.ValidTo
	END ValidTo,
	d.TranFrom, 
	CASE
		WHEN d.TranTo = dbo.fnInfinity() THEN NULL
		ELSE d.TranTo
	END TranTo
FROM 
	dbo.Department d
WHERE
	DeptID = 10
ORDER BY 
	DeptHistID
;


UPDATE
	dbo.Department
SET
	DeptName = 'Original Sales',
	ValidFrom = '2020-06-01'
WHERE 
	DeptID = 10
;

UPDATE
	dbo.Department
SET
	DeptName = 'Original Sales',
	ValidFrom = '2021-01-02'
WHERE 
	DeptID = 10
;


SELECT
	*
FROM 
	dbo.Department
WHERE
	DeptID = 10
ORDER BY 
	DeptHistID
;

--SELECT
--	*
--FROM
--	dbo.Department_Current
--;

--EXEC dbo.Get_Department 10;
--GO

--EXEC dbo.Get_Department 10, '2025-01-01', '2026-01-01';

--EXEC dbo.Get_Department 10,'2026-01-01', '2026-01-01';

--EXEC dbo.Get_Department 10,'2026-01-01', '2023-01-01';

--EXEC dbo.Get_Department 10,'2026-01-01', '2021-09-01';

--EXEC dbo.Get_Department 10,'2025-01-01', '2021-09-01';





SELECT SYSUTCDATETIME();