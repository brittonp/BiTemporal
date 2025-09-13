from turtle import title
import pyodbc
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import tkinter as tk
from tkinter import ttk
from sqlalchemy import create_engine, text
from enum import Enum
import json
from datetime import datetime
from sqlalchemy.orm import keyfunc_mapping

APP_TITLE = "Bi-Temporal Example"
CONNECTION_STRING = (
    "mssql+pyodbc://PAUL-LAPTOP/dept_emp_bitemporal_manual"
    "?driver=ODBC+Driver+17+for+SQL+Server"
    "&trusted_connection=yes"
)
DEPT_COLUMNS = ["dept_hist_id","dept_id","dept_name","location","valid_from","valid_to","tran_from","tran_to"]
EMP_COLUMNS = ["emp_hist_id","emp_id","dept_id", "first_name","last_name","job_title","hire_date","term_date","valid_from","valid_to","tran_from","tran_to"]

class SqlCommands(Enum):
    FETCH_DEPT = """
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
            END AS tran_to,
	        CASE
		        WHEN d.tran_to = dbo.fn_infinity() THEN 'Current'
		        ELSE 'Historical'
	        END record_status
        FROM 
	        dbo.department d
        WHERE 
	        d.dept_id = 10
        ORDER BY 
	        d.dept_hist_id
        """
    FETCH_EMP = """
        SELECT
            e.emp_hist_id,
            e.emp_id,
            e.dept_id,
            e.first_name,
            e.last_name,
            e.job_title,
            e.hire_date,
            e.term_date,
            e.valid_from,
            CASE
                WHEN e.valid_to = dbo.fn_infinity() THEN NULL
                ELSE e.valid_to
            END AS valid_to,
            e.tran_from,
            CASE
                WHEN e.tran_to = dbo.fn_infinity() THEN NULL
                ELSE e.tran_to
            END AS tran_to,
	        CASE
		        WHEN e.tran_to = dbo.fn_infinity() THEN 'Current'
		        ELSE 'Historical'
	        END record_status
        FROM 
	        dbo.employee e
        WHERE 
	        e.dept_id = 10
        ORDER BY 
	        e.emp_hist_id
        """
    RESET = "EXEC dbo.reset_data"
    UPDATE1 = """
        UPDATE	
            dbo.department
        SET
	        dept_name = 'New Sales',
	        valid_from = '2025-10-01'
        WHERE 
	        dept_id = 10
    """
    UPDATE2 = """
        UPDATE	
            dbo.Department
        SET
	        dept_name = 'Original Sales',
	        valid_from = '2020-06-01'
        WHERE 
	        dept_id = 10
    """

class DataEngine:
    def __init__(self, connection_string):
        self._engine = create_engine(connection_string)

    def sql_execute(self, sql):
        with self._engine.connect() as conn:
            conn.execute(text(sql))
            conn.commit() 

    # --- Fetch data ---
    def sql_fetch(self, sql):
        df = pd.read_sql(sql, self._engine)
        return df

class TableTreeview(ttk.Treeview):
    def __init__(self, master=None, columns=None, **kwargs):
        # Create a frame to hold Treeview + scrollbar
        super().__init__(master, columns=columns, **kwargs)

        for col in columns:
            self.heading(col, text=col)
            self.column(col, width=100)

        self.columns = columns

        scrollbar = ttk.Scrollbar(master, orient="vertical", command=self.yview)
        self.configure(yscroll=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.grid(row=0, column=0, sticky="nsew")

        # Configure row tag colors
        self.tag_configure('oddrow', background='white')
        self.tag_configure('evenrow', background='#f0f0ff')
        self.tag_configure('selected_odd', background='#42f56c')
        self.tag_configure('selected_even', background='#42f56c')

    # --- Display table with row banding ---
    def display_table(self, df):

        self.df = df

        # Clear existing rows
        for row in self.get_children():
            self.delete(row)

        # Insert new rows with alternating colors
        for i, row in enumerate(df.itertuples(index=False)):
            banding_tag = 'evenrow' if i % 2 == 0 else 'oddrow'

            # Convert row tuple to list to modify values
            values = list(row)

            # Loop over columns and replace NaT only if column is datetime
            for j, col_name in enumerate(df.columns):
                if pd.api.types.is_datetime64_any_dtype(df[col_name]):
                    if pd.isna(values[j]):
                        values[j] = "-"  # custom replacement text

            self.insert("", tk.END, values=values, tags=(banding_tag,))

        # keep a copy for next comparison
        #self.df = df.copy()

    def select_row(self, index, trans_dt, valid_dt):

        df = self.df

        # Convert DataFrame columns to naive datetime
        df["tran_from"] = pd.to_datetime(df["tran_from"], errors="coerce").dt.tz_localize(None)
        df["tran_to"]   = pd.to_datetime(df["tran_to"], errors="coerce").dt.tz_localize(None)
        df["valid_from"]= pd.to_datetime(df["valid_from"], errors="coerce").dt.tz_localize(None)
        df["valid_to"]  = pd.to_datetime(df["valid_to"], errors="coerce").dt.tz_localize(None)

        # Convert input datetimes to naive as well
        if hasattr(trans_dt, "tzinfo") and trans_dt.tzinfo is not None:
            trans_dt = trans_dt.replace(tzinfo=None)
        if hasattr(valid_dt, "tzinfo") and valid_dt.tzinfo is not None:
            valid_dt = valid_dt.replace(tzinfo=None)

        # Find the history_id(s) that match the date criteria in the DataFrame
        mask = (df["tran_from"] <= trans_dt) & ((df["tran_to"] > trans_dt) | df["tran_to"].isna()) & \
               (df["valid_from"] <= valid_dt) & ((df["valid_to"] > valid_dt) | df["valid_to"].isna())

        matching_ids = df.loc[mask, index].tolist()  # or emp_hist_id for employee table

        # Loop through Treeview items
        for i, item_id in enumerate(self.get_children()):
            row_values = self.item(item_id, "values")
            is_even = i % 2 == 0

            if int(row_values[0]) in matching_ids:
                tag = "selected_even" if is_even else "selected_odd"
            else:
                tag = "evenrow" if is_even else "oddrow"

            self.item(item_id, tags=(tag,))

class TableContainer:
    def __init__(self, parent, title, columns):
        self.parent = parent
        self.title = title
        self.columns = columns 
        
        frame = tk.Frame(parent)
        frame.rowconfigure(0, weight=0) # title row
        frame.columnconfigure(0, weight=1) # treeview row
        frame.rowconfigure(1, weight=1)

        # Title
        label = ttk.Label(frame, text=title, anchor="w", font=("Arial", 12, "bold"))
        label.grid(row=0, column=0, sticky="ew", pady=5, padx=5)

        # Table
        table_frame = tk.Frame(frame)
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        tree = TableTreeview(table_frame, columns, show="headings")
        self.tree = tree

        # Attach tree to table_frame
        tree.grid(row=0, column=0, sticky="nsew")

        # Attach table_frame to frame
        table_frame.grid(row=1, column=0, sticky="nsew") 

        # Attach to the frame to parent
        frame.grid(row=0, column=0, sticky="nsew")


class BtnToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None

        widget.bind("<Enter>", self.show_tip)
        widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.tip_window or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)   # no window decorations
        tw.wm_geometry(f"+{x}+{y}")

        label = tk.Label(
            tw,
            text=self.text,
            justify="left",
            background="#ffffe0",
            relief="solid",
            borderwidth=1,
            font=("tahoma", 8, "normal")
        )
        label.pack(ipadx=1)

    def hide_tip(self, event=None):
        tw = self.tip_window
        self.tip_window = None
        if tw:
            tw.destroy()

class Tooltip:
    def __init__(self, widget):
        self.widget = widget
        self.tipwindow = None
        self.label = None

    def showtip(self, text, x, y):
        """Create tooltip if needed, then update position + text"""
        if not self.tipwindow:
            self.tipwindow = tw = tk.Toplevel(self.widget)
            tw.wm_overrideredirect(True)  # No window decorations
            self.label = tk.Label(
                tw,
                text=text,
                background="#ffffe0",
                relief="solid",
                borderwidth=1,
                font=("tahoma", "8", "normal"),
                anchor="w",      # anchor text to the west (left)
                justify="left"   # left-align multi-line text
            )
            self.label.pack(ipadx=2)
        else:
            self.label.config(text=text)
        # Move tooltip near cursor
        self.tipwindow.wm_geometry(f"+{x+20}+{y+20}")

    def hidetip(self):
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None
            self.label = None

class Chart:
    def __init__(self, parent, tooltip, title, key, labels):
        self.parent = parent
        self.tooltip = tooltip
        self.title = title
        self.key = key 
        self.labels = labels

        fig, ax = plt.subplots(figsize=(12, 6)) 
        fig.subplots_adjust(bottom=0.15, top=0.85)

        self.ax = ax
        canvas = FigureCanvasTkAgg(fig, master=parent)
        self.canvas = canvas
        canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        toolbar = NavigationToolbar2Tk(canvas, parent, pack_toolbar=False)
        toolbar.update()
        toolbar.grid(row=1, column=0, sticky="ew")

        # Connect motion event
        canvas.mpl_connect("motion_notify_event", self.on_motion)

    # --- Display chart ---
    def display_chart(self, df):
        ax = self.ax
        title = self.title
        key = self.key
        labels = self.labels
        canvas = self.canvas

        ax.clear()
        color_palette = [
            "#1f77b4","#ff7f0e","#2ca02c","#d62728","#9467bd",
            "#8c564b","#e377c2","#7f7f7f","#bcbd22","#17becf"
        ]

        for idx, row in df.iterrows():
            valid_to = row['valid_to'] if pd.notnull(row['valid_to']) else pd.Timestamp.today() + pd.Timedelta(weeks=52)
            tran_to  = row['tran_to']  if pd.notnull(row['tran_to']) else pd.Timestamp.today() + pd.Timedelta(weeks=52)

            x_start = mdates.date2num(row['valid_from'])
            x_end   = mdates.date2num(valid_to)
            y_start = mdates.date2num(row['tran_from'])
            y_end   = mdates.date2num(tran_to)

            width  = x_end - x_start
            height = y_end - y_start
            color = color_palette[idx % len(color_palette)]

            rect = Rectangle((x_start, y_start), width, height, facecolor=color, edgecolor=color, alpha=0.4)
            rect.histid = row[key]
            ax.add_patch(rect)
            ax.text(x_start, y_start, "-".join(str(row[i]) for i in labels), verticalalignment='bottom', fontsize=8)

        ax.set_xlabel("Valid Date (As Of)")
        ax.set_ylabel("Transaction Date (Recorded)")
        ax.set_title(title)

        ax.xaxis_date()
        ax.yaxis_date()
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        ax.yaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        ax.tick_params(axis='x', labelsize=8)
        ax.tick_params(axis='y', labelsize=8)

        ax.set_xlim(mdates.date2num(df['valid_from'].min() - pd.Timedelta(weeks=52)),
                    mdates.date2num(pd.Timestamp.today() + pd.Timedelta(weeks=52)))
        ax.set_ylim(mdates.date2num(df['tran_from'].min() - pd.Timedelta(weeks=52)),
                    mdates.date2num(pd.Timestamp.today() + pd.Timedelta(weeks=52)))

        # Horizontal line for today
        now = mdates.date2num(pd.Timestamp.now())
        y_value = now
        ax.axhline(y=y_value, color="red", linestyle="--", linewidth=1)
        ax.text(
            x=mdates.date2num(df['valid_from'].min() - pd.Timedelta(weeks=52)), 
            y=y_value, 
            s="Today",
            va="center", ha="right", color="red"
        )
        # Vertical line for today
        x_value = now
        ax.axvline(x=x_value, color="red", linestyle="--", linewidth=1)
        ax.text(
            x=x_value,
            y=mdates.date2num(df['tran_from'].min() - pd.Timedelta(weeks=52)),
            s="Today",
            va="top", ha="center", color="red"
        )

        # Create crosshair lines once
        self.vline = ax.axvline(color="gray", lw=0.8, ls="--", alpha=0.6)
        self.hline = ax.axhline(color="gray", lw=0.8, ls="--", alpha=0.6)

        canvas.draw()

    def on_motion(self, event):
        if event.inaxes and event.guiEvent:
            x, y = event.xdata, event.ydata

            # Move crosshairs
            self.vline.set_xdata([x, x])
            self.hline.set_ydata([y, y])

            # Redraw canvas efficiently
            self.ax.figure.canvas.draw_idle()

            # Convert values to datetime for tooltip
            valid_dt = mdates.num2date(x)
            trans_dt = mdates.num2date(y)

            self.tooltip.showtip(
                f"Transaction: {trans_dt:%d-%b-%Y}\nValid: {valid_dt:%d-%b-%Y}",
                event.guiEvent.x_root,
                event.guiEvent.y_root,
            )

            # Propagate to parent
            self.parent._last_payload = {
                "trans_dt": trans_dt.isoformat(),
                "valid_dt": valid_dt.isoformat(),
                "series": "DateDimension",
            }
            self.parent.event_generate("<<ChartMotion>>", when="tail")

        else:
            self.tooltip.hidetip()
            # Move crosshairs outside of view instead of clearing them
            self.vline.set_xdata([float("nan"), float("nan")])
            self.hline.set_ydata([float("nan"), float("nan")])
            self.ax.figure.canvas.draw_idle()

# --- Plotting function ---
def plot_data():
    dfDept = engine.sql_fetch(SqlCommands.FETCH_DEPT.value)
    dfEmp = engine.sql_fetch(SqlCommands.FETCH_EMP.value)

    department_chart.display_chart(dfDept)
    employee_chart.display_chart(dfEmp)

    department_table.tree.display_table(dfDept)
    employee_table.tree.display_table(dfEmp)

def data_change(action):
    engine.sql_execute(action)
    plot_data()

# --- Handler for <<Chart Motion>> ---
def handle_chart_motion(event):
    dates = getattr(event.widget, "_last_payload", None)
    if dates:
        trans_dt = datetime.fromisoformat(dates['trans_dt'])
        valid_dt = datetime.fromisoformat(dates['valid_dt'])
        department_table.tree.select_row("dept_hist_id", trans_dt, valid_dt)
        employee_table.tree.select_row("emp_hist_id", trans_dt, valid_dt)

# --- Main ---
engine = DataEngine(CONNECTION_STRING)

# --- Tkinter setup ---
root = tk.Tk()
root.title(APP_TITLE)
root.geometry("1700x800")
root.rowconfigure(0, weight=1)
root.columnconfigure(0, weight=1)

# Create tooltip object
tooltip = Tooltip(root)

# --- Main PanedWindow (verical splitter) ---
paned = tk.PanedWindow(root, orient=tk.VERTICAL, sashrelief=tk.RAISED, sashwidth=8, bg="lightgray")
paned.grid(row=0, column=0, sticky="nsew")

# --- Chart PanedWindow (horizontal split) ---
chart_paned = tk.PanedWindow(paned, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashwidth=6, bg="lightgray")
paned.add(chart_paned, stretch="always")

# --- Department Chart Frame ---
department_chart_frame = tk.Frame(chart_paned, width=100)
department_chart_frame.rowconfigure(0, weight=1)  # canvas row
department_chart_frame.rowconfigure(1, weight=0)  # toolbar row
department_chart_frame.columnconfigure(0, weight=1)
department_chart = Chart(department_chart_frame, tooltip, 'Department', 'dept_hist_id', ['dept_hist_id', 'dept_name'])
chart_paned.add(department_chart_frame, stretch="always")

# --- Employee Chart Frame ---
employee_chart_frame = tk.Frame(chart_paned, width=100)
employee_chart_frame.rowconfigure(0, weight=1)  # canvas row
employee_chart_frame.rowconfigure(1, weight=0)  # toolbar row
employee_chart_frame.columnconfigure(0, weight=1)
employee_chart = Chart(employee_chart_frame, tooltip, 'Employee', 'emp_hist_id', ['emp_hist_id', 'last_name'])
chart_paned.add(employee_chart_frame, stretch="always")

# --- Department Table Frame ---
department_table_frame = tk.Frame(paned)
department_table_frame.rowconfigure(0, weight=0)
department_table_frame.columnconfigure(0, weight=1)
department_table = TableContainer(department_table_frame, "Department bi-temporal table", DEPT_COLUMNS)
paned.add(department_table_frame)

# --- Employee Table Frame ---
employee_table_frame = tk.Frame(paned)
employee_table_frame.rowconfigure(0, weight=0)
employee_table_frame.columnconfigure(0, weight=1)
employee_table = TableContainer(employee_table_frame, "Employee bi-temporal table", EMP_COLUMNS)
paned.add(employee_table_frame)

# --- Button frame ---
toolbar_frame = tk.Frame(root)
toolbar_frame.grid(row=1, column=0, sticky="ew")

tk.Button(toolbar_frame, text="Reset", command=lambda: [btnUpdate1.config(state="active"), btnUpdate2.config(state="active"), data_change(SqlCommands.RESET.value)]).pack(side=tk.LEFT,padx=5, pady=5)

btnUpdate1 = tk.Button(toolbar_frame, text="Update #1", command=lambda: [btnUpdate1.config(state="disabled"), data_change(SqlCommands.UPDATE1.value)])
btnUpdate1.pack(side=tk.LEFT, padx=5, pady=5)
BtnToolTip(btnUpdate1,SqlCommands.UPDATE1.value)

btnUpdate2 = tk.Button(toolbar_frame, text="Update #2", command=lambda: [btnUpdate2.config(state="disabled"), data_change(SqlCommands.UPDATE2.value )])
btnUpdate2.pack(side=tk.LEFT, padx=5, pady=5)
BtnToolTip(btnUpdate2,SqlCommands.UPDATE2.value)

tk.Button(toolbar_frame, text="Refresh", command=plot_data).pack(side=tk.RIGHT, padx=5, pady=5)

root.bind_all("<<ChartMotion>>", handle_chart_motion)

# --- Initial plot ---
plot_data()

root.mainloop()
