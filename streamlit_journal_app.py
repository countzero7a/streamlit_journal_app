import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, time
import matplotlib.pyplot as plt

######## CONFIGURATION #########
FOCUS_OPTIONS = [
    ("Time Log", [
        ("Name", "text", ""),
        ("Time Range", "text", ""),
        ("Energy", "select", ["Very Low", "Low", "Medium", "High", "Very High"]),
        ("Focus Level", "select", ["Very Low", "Low", "Medium", "High", "Very High"]),
        ("Notes", "text_area", "")
    ]),
    ("Expense Log", [
        ("Items", "text", ""),
        ("Category", "select", ["Food", "Transport", "Bills", "Health", "Fun", "Other"]),
        ("Amount", "number", 0.0),
        ("Emotion Before", "select", [
            "😊 Happy", "😐 Okay", "😞 Sad", "😠 Angry", "😌 Calm", "🤩 Excited", "😔 Tired", "Other"
        ]),
        ("Emotion After", "select", [
            "😊 Happy", "😐 Okay", "😞 Sad", "😠 Angry", "😌 Calm", "🤩 Excited", "😔 Tired", "Other"
        ]),
        ("Need vs Want (1-5)", "slider", (1, 5, 3)),
        ("Notes", "text_area", "")
    ]),
    ("Stress Log", [
        ("Trigger", "text", ""),
        ("Stress (0-10)", "slider", (0, 10, 5)),
        ("Negative Thought", "text_area", ""),
        ("Reframe", "text_area", ""),
        ("Mood After", "select", [
            "😊 Happy", "😐 Okay", "😞 Sad", "😠 Angry", "😌 Calm", "🤩 Excited", "😔 Tired", "Other"
        ])
    ]),
    ("Eating Log", [
        ("Meal", "text", ""),
        ("Food Items", "text_area", ""),
        ("Hunger (0-10)", "slider", (0, 10, 5)),
        ("Stress (0-10)", "slider", (0, 10, 5)),
        ("Craving (0-10)", "slider", (0, 10, 5)),
        ("Mood Before", "select", [
            "😊 Happy", "😐 Okay", "😞 Sad", "😠 Angry", "😌 Calm", "🤩 Excited", "😔 Tired", "Other"
        ]),
        ("Mood After", "select", [
            "😊 Happy", "😐 Okay", "😞 Sad", "😠 Angry", "😌 Calm", "🤩 Excited", "😔 Tired", "Other"
        ]),
        ("Notes", "text_area", "")
    ])
]

FOCUS_NAMES = [x[0] for x in FOCUS_OPTIONS]
FOCUS_FIELDS = sorted(list(set([field for _, field_list in FOCUS_OPTIONS for field, *_ in field_list])))
GENERAL_COLUMNS = ["DateTime", "Mood", "Focus"]
ALL_COLUMNS = GENERAL_COLUMNS + FOCUS_FIELDS

def load_data():
    try:
        df = pd.read_csv("journal_entries.csv")
        if "DateTime" not in df.columns and "Date" in df.columns:
            df = df.rename(columns={"Date": "DateTime"})
        df["DateTime"] = pd.to_datetime(df["DateTime"], errors="coerce")
        # Remove duplicated columns and fix order
        cols_seen = set()
        cols_unique = []
        for c in ALL_COLUMNS:
            if c not in cols_seen:
                cols_unique.append(c)
                cols_seen.add(c)
        for col in cols_unique:
            if col not in df.columns:
                df[col] = ""
        df = df[cols_unique]
        return df
    except FileNotFoundError:
        return pd.DataFrame(columns=ALL_COLUMNS)

def save_data(df):
    df.to_csv("journal_entries.csv", index=False)

def build_focus_fields(focus, session_key="", default_values=None):
    results = {}
    for option_focus, fields in FOCUS_OPTIONS:
        if option_focus == focus:
            for field_name, field_type, *args in fields:
                key = f"{session_key}_{field_name}"
                default = default_values.get(field_name, "") if default_values else None
                if field_type == "text":
                    results[field_name] = st.text_input(field_name, value=default or "")
                elif field_type == "text_area":
                    results[field_name] = st.text_area(field_name, value=default or "", height=60)
                elif field_type == "select":
                    options = args[0]
                    idx = 0
                    if default and default in options:
                        idx = options.index(default)
                    results[field_name] = st.selectbox(field_name, options, index=idx, key=key)
                elif field_type == "slider":
                    rng = args[0]
                    val = int(default) if default not in [None, ""] else rng[2]
                    results[field_name] = st.slider(field_name, rng[0], rng[1], val, key=key)
                elif field_type == "number":
                    results[field_name] = st.number_input(field_name, value=float(default) if default not in [None, ""] else args[0], key=key)
            break
    return results

def add_entry(df, dt, mood, focus, focus_fields):
    to_add = {col: "" for col in ALL_COLUMNS}
    to_add["DateTime"] = pd.to_datetime(dt)
    to_add["Mood"] = mood
    to_add["Focus"] = focus
    for k, v in focus_fields.items():
        to_add[k] = v
    df = pd.concat([df, pd.DataFrame([to_add])], ignore_index=True)
    return df

def edit_entry(df, idx, mood, focus, focus_fields):
    df.at[idx, "Mood"] = mood
    df.at[idx, "Focus"] = focus
    for k, v in focus_fields.items():
        df.at[idx, k] = v
    return df

def delete_entry(df, idx):
    return df.drop(idx).reset_index(drop=True)

# Mood choices
MOOD_CHOICES = [
    "😊 Happy", "😐 Okay", "😞 Sad", "😠 Angry", 
    "😌 Calm", "🤩 Excited", "😔 Tired", "Other"
]

st.set_page_config(page_title="Daily Journal", layout="centered")
st.title("📔 My Daily Journal")
df = load_data()
if not df.empty and not pd.api.types.is_datetime64_any_dtype(df["DateTime"]):
    df["DateTime"] = pd.to_datetime(df["DateTime"], errors="coerce")

tab1, tab2, tab3, tab4 = st.tabs(["New Entry", "My Journal", "Summaries", "Graphs"])

### 1. NEW ENTRY ###
with tab1:
    st.subheader("Write a New Entry")
    today = datetime.now()
    entry_date = st.date_input("Date", today)
    entry_time = st.time_input("Time", today.time())
    entry_datetime = datetime.combine(entry_date, entry_time)
    mood = st.selectbox("How do you feel today? (Pick one)", MOOD_CHOICES)
    focus = st.selectbox("Focus", [x.title() for x in FOCUS_NAMES])
    true_focus = " ".join(word.capitalize() for word in focus.split())
    focus_fields = build_focus_fields(true_focus, session_key="new", default_values={})
    if st.button("Save Entry", key="save_new"):
        already = False
        if not df.empty:
            already = (df["DateTime"].dt.strftime("%Y-%m-%d %H:%M") == entry_datetime.strftime("%Y-%m-%d %H:%M")).any()
        if already:
            st.error(f"Entry for {entry_datetime.strftime('%Y-%m-%d %H:%M')} exists - edit it in 'My Journal'.")
        else:
            df = add_entry(df, entry_datetime, mood, true_focus, focus_fields)
            save_data(df)
            st.success("Entry saved! 🎉")
            st.rerun()

### 2. JOURNAL ###
with tab2:
    st.subheader("View & Manage Your Journal")
    if df.empty:
        st.info("No journal entries yet.")
    else:
        df = df.sort_values("DateTime", ascending=False).reset_index(drop=True)
        date_options = df["DateTime"].dt.strftime("%Y-%m-%d %H:%M").tolist()
        selected = st.selectbox("Select entry:", date_options, key="pick_date")
        sel_index = df[df["DateTime"].dt.strftime("%Y-%m-%d %H:%M") == selected].index[0]
        st.write(f"**Date & Time:** {df.at[sel_index, 'DateTime'].strftime('%Y-%m-%d %H:%M')}")
        st.write(f"**Mood:** {df.at[sel_index, 'Mood']}")
        st.write(f"**Focus:** {df.at[sel_index, 'Focus']}")
        st.markdown("#### Entry Details:")
        this_focus = df.at[sel_index, "Focus"]
        fields = [f for f in FOCUS_OPTIONS if f[0] == this_focus]
        if fields:
            for field_name, _, *_ in fields[0][1]:
                value = df.at[sel_index, field_name]
                st.write(f"**{field_name}:** {value}")
        st.markdown("---")
        with st.expander("✏️ Edit this entry"):
            edit_mood = st.selectbox("Edit Mood", MOOD_CHOICES, index=MOOD_CHOICES.index(df.at[sel_index, "Mood"]), key=f"edit_mood_{sel_index}")
            edit_focus = st.selectbox("Edit Focus", [x.title() for x in FOCUS_NAMES], index=FOCUS_NAMES.index(this_focus), key=f"edit_focus_{sel_index}")
            edit_focus = " ".join(word.capitalize() for word in edit_focus.split())
            defaults = {field: df.at[sel_index, field] for _, fields in FOCUS_OPTIONS if _ == edit_focus for field, *_ in fields}
            edit_fields = build_focus_fields(edit_focus, session_key=f"edit_{sel_index}", default_values=defaults)
            if st.button("Save changes", key=f'edit_btn_{sel_index}'):
                df = edit_entry(df, sel_index, edit_mood, edit_focus, edit_fields)
                save_data(df)
                st.success("Entry updated!")
                st.rerun()
        if st.button("❌ Delete this entry", key=f'del_{sel_index}'):
            df = delete_entry(df, sel_index)
            save_data(df)
            st.warning("Entry deleted.")
            st.rerun()
        st.markdown("### Journal Timeline")
        timeline = df[["DateTime", "Mood", "Focus"]].copy()
        timeline_display = timeline.rename(
            columns={"DateTime": "Date & Time", "Mood": "Mood", "Focus": "Focus"}
        )
        timeline_display["Date & Time"] = timeline_display["Date & Time"].dt.strftime("%Y-%m-%d %H:%M")
        st.dataframe(timeline_display, use_container_width=True, hide_index=True)

### 3. SUMMARIES TAB ###
with tab3:
    st.subheader("Journal Summaries")
    period_type = st.selectbox(
        "Summary Period",
        ["Day", "Week", "Month", "Quarter", "Semester", "Year"],
        key="sel_period"
    )
    if period_type == "Day":
        summary_date = st.date_input("Date for summary", datetime.now().date(), key="summary_date")
        mask = (df["DateTime"].dt.date == summary_date)
    elif period_type == "Week":
        week_start = st.date_input("Week start", datetime.now().date(), key="week_start")
        week_end = week_start + pd.Timedelta(days=6)
        mask = (df["DateTime"].dt.date >= week_start) & (df["DateTime"].dt.date <= week_end)
    elif period_type == "Month":
        years = sorted(df["DateTime"].dt.year.dropna().unique())
        if not years: years = [datetime.now().year]
        yr = st.selectbox("Year", years, key="mo_y")
        mo = st.selectbox("Month", list(range(1,13)), format_func=lambda x: datetime(2000, x, 1).strftime("%B"), key="mo_mo")
        first = datetime(yr, mo, 1)
        last = (first + pd.offsets.MonthEnd(1)).date()
        mask = (df["DateTime"].dt.date >= first.date()) & (df["DateTime"].dt.date <= last)
    elif period_type == "Quarter":
        years = sorted(df["DateTime"].dt.year.dropna().unique())
        if not years: years = [datetime.now().year]
        yr = st.selectbox("Year", years, key="q_y")
        q = st.selectbox("Quarter", [1,2,3,4], key="q_q")
        q_month = (q-1)*3+1
        first = datetime(yr, q_month, 1)
        last = (first + pd.offsets.MonthEnd(3)).date()
        mask = (df["DateTime"].dt.date >= first.date()) & (df["DateTime"].dt.date <= last)
    elif period_type == "Semester":
        years = sorted(df["DateTime"].dt.year.dropna().unique())
        if not years: years = [datetime.now().year]
        yr = st.selectbox("Year", years, key="s_y")
        sem = st.selectbox("Semester", [1,2], key="s_s")
        start_month = 1 if sem == 1 else 7
        first = datetime(yr, start_month, 1)
        last = (first + pd.offsets.MonthEnd(6)).date()
        mask = (df["DateTime"].dt.date >= first.date()) & (df["DateTime"].dt.date <= last)
    elif period_type == "Year":
        years = sorted(df["DateTime"].dt.year.dropna().unique())
        if not years: years = [datetime.now().year]
        yr = st.selectbox("Year", years, key="y_y")
        first = datetime(yr, 1, 1)
        last = datetime(yr, 12, 31)
        mask = (df["DateTime"].dt.date >= first.date()) & (df["DateTime"].dt.date <= last.date())
    else:
        mask = pd.Series([False]*len(df))
    dfp = df[mask].copy()
    df_exp = dfp[dfp["Focus"] == "Expense Log"]
    with st.container():
        total_eur = pd.to_numeric(df_exp["Amount"], errors="coerce").sum()
        st.metric("Total EUR (Expenses)", f"{total_eur:.2f} €")
    df_stress = dfp[dfp["Focus"].isin(["Stress Log", "Eating Log"])]
    stress_vals = []
    if "Stress (0-10)" in df_stress.columns:
        stress_vals += pd.to_numeric(df_stress["Stress (0-10)"], errors="coerce").dropna().tolist()
    avg_stress = np.nan
    if stress_vals:
        avg_stress = np.mean(stress_vals)
    st.metric("Average Stress", "-" if np.isnan(avg_stress) else f"{avg_stress:.2f} / 10")
    df_eating = dfp[dfp["Focus"] == "Eating Log"]
    meals_count = df_eating["Meal"].dropna().apply(lambda x: str(x).strip() != "").sum()
    st.metric("Meal Entries", meals_count)
    avg_craving = pd.to_numeric(df_eating["Craving (0-10)"], errors="coerce").mean(skipna=True)
    st.metric("Average Craving", "-" if np.isnan(avg_craving) else f"{avg_craving:.2f} / 10")
    df_time = dfp[dfp["Focus"] == "Time Log"]
    energy_map = {"Very Low":1, "Low":2, "Medium":3, "High":4, "Very High":5}
    if not df_time.empty and "Energy" in df_time.columns:
        energies = df_time["Energy"].map(energy_map)
        avg_energy = energies.mean(skipna=True)
        avg_energy_str = "-" if np.isnan(avg_energy) else f"{avg_energy:.2f} / 5"
    else:
        avg_energy_str = "-"
    st.metric("Average Energy", avg_energy_str)

### 4. GRAPHS TAB ###
with tab4:
    st.subheader("Trends & Visualizations")
    log_types = ["Time Log", "Expense Log", "Stress Log", "Eating Log"]
    selected_logs = st.multiselect(
        "Select which logs to show graphs for:", 
        options=log_types, 
        default=log_types
    )
    df_vis = df[df["Focus"].isin(selected_logs)].copy()
    if df_vis.empty:
        st.info("No data for selected logs and period.")
    else:
        df_vis["Date"] = df_vis["DateTime"].dt.date

        # EXPENSE LOG: Expenses Over Time
        if "Expense Log" in selected_logs:
            df_exp = df_vis[df_vis["Focus"] == "Expense Log"].copy()
            if not df_exp.empty:
                df_exp["Amount"] = pd.to_numeric(df_exp["Amount"], errors="coerce")
                by_date = df_exp.groupby("Date")["Amount"].sum()
                st.markdown("#### Expenses Over Time (€)")
                st.bar_chart(by_date)

        # STRESS LOG & EATING LOG: Stress Over Time
        plot_stress_types = []
        if "Stress Log" in selected_logs:
            plot_stress_types.append("Stress Log")
        if "Eating Log" in selected_logs:
            plot_stress_types.append("Eating Log")
        if plot_stress_types:
            df_stress = df_vis[df_vis["Focus"].isin(plot_stress_types)].copy()
            df_stress["Stress (0-10)"] = pd.to_numeric(df_stress["Stress (0-10)"], errors="coerce")
            if not df_stress.empty:
                st.markdown(f"#### Stress Over Time ({' & '.join(plot_stress_types)})")
                stress_by_date = df_stress.groupby(["Date", "Focus"])["Stress (0-10)"].mean().unstack()
                st.line_chart(stress_by_date)

        # EATING LOG: Craving Over Time
        if "Eating Log" in selected_logs:
            df_eat = df_vis[df_vis["Focus"] == "Eating Log"].copy()
            if not df_eat.empty:
                df_eat["Craving (0-10)"] = pd.to_numeric(df_eat["Craving (0-10)"], errors="coerce")
                craving_by_date = df_eat.groupby("Date")["Craving (0-10)"].mean()
                st.markdown("#### Craving Over Time (Eating Log)")
                st.line_chart(craving_by_date)
                # Meals per day
                meals_by_date = df_eat["Meal"].dropna().groupby(df_eat["Date"]).count()
                st.markdown("#### Number of Meals Over Time")
                st.bar_chart(meals_by_date)

        # TIME LOG: Energy Over Time
        if "Time Log" in selected_logs:
            df_t = df_vis[df_vis["Focus"] == "Time Log"].copy()
            if not df_t.empty:
                energy_map = {"Very Low":1, "Low":2, "Medium":3, "High":4, "Very High":5}
                df_t["Energy Num"] = df_t["Energy"].map(energy_map)
                energy_by_date = df_t.groupby("Date")["Energy Num"].mean()
                st.markdown("#### Average Energy Over Time (Time Log, 1=Very Low...5=Very High)")
                st.line_chart(energy_by_date)

        st.info("Plots show daily metrics based on selected log types.")

st.markdown("---")
st.caption("Your journal data is stored only on your local device (journal_entries.csv).")