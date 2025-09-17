from turtle import title
import pyodbc
import pandas as pd
import matplotlib
matplotlib.use("TkAgg")  # ensure TkAgg backend for Tkinter embedding
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import tkinter as tk
from tkinter import ttk, messagebox
from sqlalchemy import create_engine, text
from enum import Enum
import json
from datetime import datetime
from sqlalchemy.orm import keyfunc_mapping
import os
from dotenv import load_dotenv
from PIL import Image, ImageTk

APP_TITLE = "Bi-Temporal Example"

class DbProduct(Enum): 
    SQLSERVER = "SqlServer"
    POSTGRESQL = "PostgreSql"

load_dotenv()  # loads .env into environment
DB_PRODUCT=os.getenv("DB_PRODUCT")
user = os.getenv("DB_USER")
password = os.getenv("DB_PASSWORD")
host = os.getenv("DB_HOST")
port = os.getenv("DB_PORT")
db_name = os.getenv("DB_NAME")
driver=os.getenv("DB_DRIVER")

if DB_PRODUCT == DbProduct.POSTGRESQL.value:
    CONNECTION_STRING = f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db_name}"
else: # Defaults to 'SqlServer'
    CONNECTION_STRING = f"mssql+pyodbc://{host}/{db_name}?driver={driver}&trusted_connection=yes"

DEPT_COLUMNS = ["dept_hist_id","dept_id","dept_name","location","valid_from","valid_to","tran_from","tran_to"]
EMP_COLUMNS = ["emp_hist_id","emp_id","dept_id", "first_name","last_name","job_title","hire_date","term_date","valid_from","valid_to","tran_from","tran_to"]

class SqlCommands(Enum):    
    RESET = "CALL dbo.reset_data()" if DB_PRODUCT == DbProduct.POSTGRESQL.value else "EXEC dbo.reset_data"
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
    UPDATE3 = """
        UPDATE	
            dbo.Employee
        SET
	        job_title = 'Lead Sales Rep',
	        valid_from = '2025-10-01'
        WHERE 
	        emp_id = 100
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
        self.row_map = {}

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

            iid = self.insert("", tk.END, values=values, tags=(banding_tag,))
            self.row_map[i] = iid

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
                self.see(self.row_map[i])
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

import tkinter as tk

import tkinter as tk

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

        # Create tooltip window first
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)  # no window decorations

        # Tooltip label
        label = tk.Label(
            tw,
            text=self.text,
            justify="left",
            background="#ffffe0",
            relief="solid",
            borderwidth=1,
            font=("tahoma", 8, "normal")
        )
        label.pack(ipadx=1, ipady=1)

        # Update geometry to get label size
        tw.update_idletasks()
        tip_width = tw.winfo_width()
        tip_height = tw.winfo_height()

        # Parent window geometry
        parent = self.widget.winfo_toplevel()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pwidth = parent.winfo_width()
        pheight = parent.winfo_height()

        # Default position: below the widget
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5

        # Clamp within parent window horizontally
        if x + tip_width > px + pwidth:
            x = px + pwidth - tip_width - 5  # shift left

        if x < px:
            x = px + 5  # shift right

        # Clamp within parent window vertically
        if y + tip_height > py + pheight:
            # Show above the widget if below would overflow
            y = self.widget.winfo_rooty() - tip_height - 5

        if y < py:
            y = py + 5  # prevent going above parent

        tw.wm_geometry(f"+{x}+{y}")

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
            ax.text(x_start, y_start, "\n".join(str(row[i]) for i in labels), verticalalignment='bottom', fontsize=8)

        ax.set_xlabel("Valid Date")
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

class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.engine = DataEngine(CONNECTION_STRING)

        self.title(APP_TITLE)
        self.geometry("1700x800")

        # Configure the main grid layout
        self.grid_rowconfigure(1, weight=1)  # Body expands vertically
        self.grid_columnconfigure(0, weight=1)  # Expand horizontally

        # Create tooltip object
        self.tooltip = Tooltip(self)

        # Create frames
        self.create_header()
        self.create_body()
        self.create_footer()

        self.bind_all("<<ChartMotion>>", self.handle_chart_motion)

        # --- Initial plot ---
        self.plot_data()

    def create_header(self):
        header_frame = ttk.Frame(self, padding=5)
        header_frame.grid(row=0, column=0, sticky="ew")  # Sticks east-west
        header_frame.grid_columnconfigure(0, weight=1)

        header_label = ttk.Label(header_frame, text=APP_TITLE, anchor="w", font=("Arial", 14, "bold"))
        header_label.grid(row=0, column=0, sticky="ew")

        # --- Right-aligned PNG info icon ---
        png_file = "info_icon.png"  # Path to your pre-made PNG file

        image = Image.open(png_file)
        # Resize if necessary (optional)
        image = image.resize((24, 24), Image.Resampling.LANCZOS)
        tk_image = ImageTk.PhotoImage(image)

        info_icon_label = tk.Label(header_frame, image=tk_image, cursor="hand2")
        info_icon_label.image = tk_image  # Keep reference
        info_icon_label.grid(row=0, column=1, sticky="e", padx=5)
        BtnToolTip(info_icon_label,f"You are currently connected\nto a {DB_PRODUCT} database")

    def create_body(self):
        body_frame = ttk.Frame(self, padding=5, relief="ridge")
        body_frame.grid(row=1, column=0, sticky="nsew")  # Fill remaining space
        body_frame.grid_rowconfigure(0, weight=1)
        body_frame.grid_columnconfigure(0, weight=1)

        # --- Main PanedWindow (verical splitter) ---
        paned = tk.PanedWindow(body_frame, orient=tk.VERTICAL, sashrelief=tk.RAISED, sashwidth=8, bg="lightgray")
        paned.grid(row=0, column=0, sticky="nsew")

        # --- Chart PanedWindow (horizontal split) ---
        chart_paned = tk.PanedWindow(paned, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashwidth=6, bg="lightgray")
        paned.add(chart_paned, stretch="always")

        # --- Department Chart Frame ---
        department_chart_frame = tk.Frame(chart_paned)
        department_chart_frame.rowconfigure(0, weight=1)  # canvas row
        department_chart_frame.rowconfigure(1, weight=0)  # toolbar row
        department_chart_frame.columnconfigure(0, weight=1)
        self.department_chart = Chart(department_chart_frame, self.tooltip, 'Department', 'dept_hist_id', ['dept_hist_id', 'dept_name'])
        chart_paned.add(department_chart_frame, stretch="always")

        # --- Employee Chart Frame ---
        employee_chart_frame = tk.Frame(chart_paned)
        employee_chart_frame.rowconfigure(0, weight=1)  # canvas row
        employee_chart_frame.rowconfigure(1, weight=0)  # toolbar row
        employee_chart_frame.columnconfigure(0, weight=1)
        self.employee_chart = Chart(employee_chart_frame, self.tooltip, 'Employee', 'emp_hist_id', ['emp_hist_id', 'last_name', 'job_title'])
        chart_paned.add(employee_chart_frame, stretch="always")

        # --- Department Table Frame ---
        department_table_frame = tk.Frame(paned)
        department_table_frame.rowconfigure(0, weight=1)
        department_table_frame.columnconfigure(0, weight=1)
        self.department_table = TableContainer(department_table_frame, "Department bi-temporal table", DEPT_COLUMNS)
        paned.add(department_table_frame, stretch="always")

        # --- Employee Table Frame ---
        employee_table_frame = tk.Frame(paned)
        employee_table_frame.rowconfigure(0, weight=1)
        employee_table_frame.columnconfigure(0, weight=1)
        self.employee_table = TableContainer(employee_table_frame, "Employee bi-temporal table", EMP_COLUMNS)
        paned.add(employee_table_frame, stretch="always")

    def create_footer(self):
        footer_frame = ttk.Frame(self, padding=5)
        footer_frame.grid(row=2, column=0, sticky="ew")
        footer_frame.grid_columnconfigure((0, 1), weight=1)

        # --- Create all buttons ---
        reset_btn = tk.Button(footer_frame, text="Reset")
        update1_btn = tk.Button(footer_frame, text="Update #1")
        update2_btn = tk.Button(footer_frame, text="Update #2")
        update3_btn = tk.Button(footer_frame, text="Update #3")
        refresh_btn = tk.Button(footer_frame, text="Refresh")

        # --- Pack buttons ---
        reset_btn.pack(side=tk.LEFT, padx=5, pady=5)
        update1_btn.pack(side=tk.LEFT, padx=5, pady=5)
        update2_btn.pack(side=tk.LEFT, padx=5, pady=5)
        update3_btn.pack(side=tk.LEFT, padx=5, pady=5)
        refresh_btn.pack(side=tk.RIGHT, padx=5, pady=5)

        # --- Assign commands ---
        reset_btn.config(command=lambda: [
            update1_btn.config(state="active"),
            update2_btn.config(state="active"),
            update3_btn.config(state="active"),
            self.data_change(SqlCommands.RESET.value)
        ])
        update1_btn.config(command=lambda: [
            update1_btn.config(state="disabled"),
            self.data_change(SqlCommands.UPDATE1.value)
        ])
        update2_btn.config(command=lambda: [
            update2_btn.config(state="disabled"),
            self.data_change(SqlCommands.UPDATE2.value)
        ])
        update3_btn.config(command=lambda: [
            update3_btn.config(state="disabled"),
            self.data_change(SqlCommands.UPDATE3.value)
        ])
        refresh_btn.config(command=self.plot_data)

        # --- Tooltips ---
        BtnToolTip(reset_btn, "Reset the database data and refresh the charts and tables")
        BtnToolTip(update1_btn, SqlCommands.UPDATE1.value)
        BtnToolTip(update2_btn, SqlCommands.UPDATE2.value)
        BtnToolTip(update3_btn, SqlCommands.UPDATE3.value)
        BtnToolTip(refresh_btn, "Refresh the charts and tables from the database")


    # --- Plotting function ---
    def plot_data(self):
        dfDept = self.engine.sql_fetch(SqlCommands.FETCH_DEPT.value)
        dfEmp = self.engine.sql_fetch(SqlCommands.FETCH_EMP.value)

        self.department_chart.display_chart(dfDept)
        self.employee_chart.display_chart(dfEmp)

        self.department_table.tree.display_table(dfDept)
        self.employee_table.tree.display_table(dfEmp)

    def data_change(self, action):
        self.engine.sql_execute(action)
        self.plot_data()

    # --- Handler for <<Chart Motion>> ---
    def handle_chart_motion(self, event):
        dates = getattr(event.widget, "_last_payload", None)
        if dates:
            trans_dt = datetime.fromisoformat(dates['trans_dt'])
            valid_dt = datetime.fromisoformat(dates['valid_dt'])
            self.department_table.tree.select_row("dept_hist_id", trans_dt, valid_dt)
            self.employee_table.tree.select_row("emp_hist_id", trans_dt, valid_dt)

if __name__ == "__main__":
    app = App()
    app.mainloop()