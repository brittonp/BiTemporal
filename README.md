# Project Title: BiTemporal

A Python app to represent an example bi-temporal data set in a chart.

## Motivation

The concept of bi-temporal data—managing and interpreting both the transaction date (when data was recorded in the system) and the valid date (when the data is considered accurate in the real world)—can often be abstract and difficult to explain in theory alone. To make this easier to understand, I created a simple Python application that sources an example set of Department data from a SQL Server table and represents it visually.

By plotting the data with the transaction date on the y-axis and the valid date on the x-axis, the chart provides a clear way to see how these two dimensions interact over time. The goal is not to build a production-ready tool, but rather to offer an approachable, visual illustration of bi-temporal concepts for learning, teaching, or discussion.

![Example Bi-Temporal Chart](./Screenshot.png)

## Setup

### Database

The example sources data from a local a SqlServer Database. I have provided a [Create.sql](./SqlServer/Create.sql) which:

* Creates a table __department__ to store the bi-temporal data
* Creates a view __vw_department_current__ to return valid Departments effective of the current system date
* Creates a trigger __tr_department_update__ which manages the transaction process when an attribute of the Department is updated
* Creates a procedure to __get_department__ which return Departments for a specific transaction and valid date
* Creates and executes a procedure __reset_data__ which re-intialises the example's seed data

A further file [Queries.sql](./SqlServer/Queries.sql) contains some example update statements, queries and example procedure calls, although the app itself provides all the necessary database interaction for this example.

### Python App
The Python app requires the the connection string to be modified to point to your database instance:

```python
CONNECTION_STRING = (
    "mssql+pyodbc://[your-server]/[your-database]"
    "?driver=ODBC+Driver+17+for+SQL+Server"
    "&trusted_connection=yes"
)
```

## How to use the app
On first running the app you will see the chart reflecting the initial seed data for Department 10 (the seed data).

There are two buttons with predefined __UPDATE__ statements to modify Department 10's title from a specific effective date. On performing the updates the affect will be shown in the chart and the table (which is the contents of the __department__ database table for Department 10).

To re-intialise the data click __Reset__.

## License

This project is licensed under the MIT License – see the [LICENSE](./LICENSE) file for details.