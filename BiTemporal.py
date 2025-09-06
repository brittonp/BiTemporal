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

APP_TITLE = "Bi-Temporal Example - Department"
CONNECTION_STRING = (
    "mssql+pyodbc://PAUL-LAPTOP/DeptEmpBiTemporalManual"
    "?driver=ODBC+Driver+17+for+SQL+Server"
    "&trusted_connection=yes"
)

class SqlCommands(Enum):
    FETCH = """
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
	        END TranTo,
	        CASE
		        WHEN d.TranTo = dbo.fnInfinity() THEN 'Current'
		        ELSE 'Historical'
	        END RecordStatus
        FROM 
	        dbo.Department d
        WHERE
	        DeptID = 10
        ORDER BY 
	        DeptHistID
        """
    RESET = "EXEC dbo.Reset_Data"
    UPDATE1 = """
        UPDATE	
            dbo.Department
        SET
	        DeptName = 'New Sales',
	        ValidFrom = '2025-10-01'
        WHERE 
	        DeptID = 10
    """
    UPDATE2 = """
        UPDATE	
            dbo.Department
        SET
	        DeptName = 'Original Sales',
	        ValidFrom = '2020-06-01'
        WHERE 
	        DeptID = 10
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
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)

        for col in columns:
            self.heading(col, text=col)
            self.column(col, width=120)

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
        self.df = df.copy()

    # --- Select a row by value in the first column ---
    def select_row(self, history_id):
        for i, item_id in enumerate(self.get_children()):
            row_values = self.item(item_id, 'values')
            is_even = i % 2 == 0
            if int(row_values[0]) == history_id:
                # Apply combined tag for selected row
                tag = 'selected_even' if is_even else 'selected_odd'
            else:
                # Keep normal banding for unselected rows
                tag = 'evenrow' if is_even else 'oddrow'
            self.item(item_id, tags=(tag,))

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

def on_motion(event):
    if event.inaxes and event.guiEvent:
        x, y = event.xdata, event.ydata
        # Convert x from Matplotlib float to datetime
        x_dt = mdates.num2date(x)
        y_dt = mdates.num2date(y)
        tooltip.showtip(f"Transaction: {y_dt:%d-%b-%Y}\nValid: {x_dt:%d-%b-%Y}",
                        event.guiEvent.x_root,
                        event.guiEvent.y_root)
        
        tree.select_row(-1)
        for rect in event.inaxes.patches:
            contains, _ = rect.contains(event)
            if contains:
                tree.select_row(rect.histid)
                break
    else:
        tooltip.hidetip()

# --- Display chart ---
def display_chart(ax, df):
    ax.clear()
    color_palette = [
        "#1f77b4","#ff7f0e","#2ca02c","#d62728","#9467bd",
        "#8c564b","#e377c2","#7f7f7f","#bcbd22","#17becf"
    ]

    for idx, row in df.iterrows():
        valid_to = row['ValidTo'] if pd.notnull(row['ValidTo']) else pd.Timestamp.today() + pd.Timedelta(weeks=52)
        tran_to  = row['TranTo']  if pd.notnull(row['TranTo']) else pd.Timestamp.today() + pd.Timedelta(weeks=52)

        x_start = mdates.date2num(row['ValidFrom'])
        x_end   = mdates.date2num(valid_to)
        y_start = mdates.date2num(row['TranFrom'])
        y_end   = mdates.date2num(tran_to)

        width  = x_end - x_start
        height = y_end - y_start
        color = color_palette[idx % len(color_palette)]

        rect = Rectangle((x_start, y_start), width, height, facecolor=color, edgecolor=color, alpha=0.4)
        rect.histid = row['DeptHistID']
        ax.add_patch(rect)
        ax.text(x_start, y_start, f"{row['DeptHistID']}-{row['DeptName']}", verticalalignment='bottom', fontsize=8)

    ax.set_xlabel("Valid Date (As Of)")
    ax.set_ylabel("Transaction Date (Recorded)")
    ax.set_title(APP_TITLE)

    ax.xaxis_date()
    ax.yaxis_date()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax.yaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax.tick_params(axis='x', labelsize=8)
    ax.tick_params(axis='y', labelsize=8)

    ax.set_xlim(mdates.date2num(df['ValidFrom'].min() - pd.Timedelta(weeks=52)),
                mdates.date2num(pd.Timestamp.today() + pd.Timedelta(weeks=52)))
    ax.set_ylim(mdates.date2num(df['TranFrom'].min() - pd.Timedelta(weeks=52)),
                mdates.date2num(pd.Timestamp.today() + pd.Timedelta(weeks=52)))

    # Horizontal line for today
    now = mdates.date2num(pd.Timestamp.now())
    y_value = now
    ax.axhline(y=y_value, color="red", linestyle="--", linewidth=1)
    ax.text(
        x=mdates.date2num(df['ValidFrom'].min() - pd.Timedelta(weeks=52)), 
        y=y_value, 
        s="Today",
        va="center", ha="right", color="red"
    )
    # Vertical line for today
    x_value = now
    ax.axvline(x=x_value, color="red", linestyle="--", linewidth=1)
    ax.text(
        x=x_value,
        y=mdates.date2num(df['TranFrom'].min() - pd.Timedelta(weeks=52)),
        s="Today",
        va="top", ha="center", color="red"
    )

# --- Plotting function ---
def plot_data():
    df = engine.sql_fetch(SqlCommands.FETCH.value)
    display_chart(ax_chart, df)
    tree.display_table(df)

    canvas.draw()

def data_change(action):
    engine.sql_execute(action)
    plot_data()

engine = DataEngine(CONNECTION_STRING)

# --- Tkinter setup ---
root = tk.Tk()
root.title(APP_TITLE)
root.geometry("1200x700")

root.rowconfigure(0, weight=1)
root.columnconfigure(0, weight=1)

# --- PanedWindow (horizontal splitter) ---
paned = tk.PanedWindow(root, orient=tk.VERTICAL, sashrelief=tk.RAISED, sashwidth=8, bg="gray")
paned.grid(row=0, column=0, sticky="nsew")

# --- Top frame for chart ---
frame_chart = tk.Frame(paned)
paned.add(frame_chart, stretch="always")

fig, ax_chart = plt.subplots(figsize=(12, 4))
canvas = FigureCanvasTkAgg(fig, master=frame_chart)
canvas_widget = canvas.get_tk_widget()
canvas_widget.pack(fill="both", expand=True, padx=0, pady=0)

# Add the Matplotlib toolbar
toolbar = NavigationToolbar2Tk(canvas, frame_chart)
toolbar.update()
canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

# Connect motion event
canvas.mpl_connect("motion_notify_event", on_motion)

# --- Bottom frame for table ---
frame_table = tk.Frame(paned)
paned.add(frame_table, stretch="always")

frame_table.rowconfigure(0, weight=1)
frame_table.columnconfigure(0, weight=1)

columns = ["DeptHistID","DeptID","DeptName","Location","ValidFrom","ValidTo","TranFrom","TranTo","RecordStatus"]
tree = TableTreeview(frame_table, columns=columns, show="headings")

# --- Bottom button frame ---
frame_buttons = tk.Frame(root)
frame_buttons.grid(row=1, column=0, sticky="ew")

tk.Button(frame_buttons, text="Reset", command=lambda: [btnUpdate1.config(state="active"), btnUpdate2.config(state="active"), data_change(SqlCommands.RESET.value)]).pack(side=tk.LEFT,padx=5, pady=5)

btnUpdate1 = tk.Button(frame_buttons, text="Update #1", command=lambda: [btnUpdate1.config(state="disabled"), data_change(SqlCommands.UPDATE1.value)])
btnUpdate1.pack(side=tk.LEFT, padx=5, pady=5)
BtnToolTip(btnUpdate1,SqlCommands.UPDATE1.value)

btnUpdate2 = tk.Button(frame_buttons, text="Update #2", command=lambda: [btnUpdate2.config(state="disabled"), data_change(SqlCommands.UPDATE2.value )])
btnUpdate2.pack(side=tk.LEFT, padx=5, pady=5)
BtnToolTip(btnUpdate2,SqlCommands.UPDATE2.value)

tk.Button(frame_buttons, text="Refresh", command=plot_data).pack(side=tk.RIGHT, padx=5, pady=5)

# Create tooltip object
tooltip = Tooltip(root)

# --- Initial plot ---
plot_data()

root.mainloop()