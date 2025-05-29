
import streamlit as st
import pandas as pd

st.set_page_config(page_title="Task Allocator", layout="wide")

def allocate_tasks(team_df, tasks_df):
    allocation = []
    team_df = team_df.sort_values(by="speed", ascending=False).copy()
    tasks_df = tasks_df.sort_values(by=["priority", "difficulty"], ascending=[False, False]).copy()

    # Allocate FZ and DY tasks first
    special_tasks = tasks_df[tasks_df['priority'].isin(['fz', 'dy'])].copy()
    regular_tasks = tasks_df[~tasks_df['priority'].isin(['fz', 'dy'])].copy()

    team_zones = {}
    for i, (_, tm) in enumerate(team_df.iterrows()):
        team_zones[tm['name']] = []

    for _, task in special_tasks.iterrows():
        for i, (_, tm) in enumerate(team_df.iterrows()):
            allocated_time = sum(t['time'] for t in allocation if t['name'] == tm['name'])
            if allocated_time + task['time'] <= 300 * tm['speed']:
                allocation.append({**task, "name": tm['name']})
                break

    # Assign zones evenly
    remaining_team = list(team_df['name'])
    zones = regular_tasks['zone'].unique()
    zone_assignment = {zone: [] for zone in zones}
    for i, tm in enumerate(remaining_team):
        zone = zones[i % len(zones)]
        zone_assignment[zone].append(tm)

    for zone, members in zone_assignment.items():
        zone_tasks = regular_tasks[regular_tasks['zone'] == zone].copy()
        for _, task in zone_tasks.iterrows():
            assigned = False
            for tm_name in members:
                tm_speed = float(team_df[team_df['name'] == tm_name]['speed'].values[0])
                allocated_time = sum(t['time'] for t in allocation if t['name'] == tm_name)
                if task['difficulty'] >= 4 and tm_speed < 1 and len([t for t in allocation if t['name'] == tm_name]) == 0:
                    continue
                if allocated_time + task['time'] <= 300 * tm_speed:
                    allocation.append({**task, "name": tm_name})
                    assigned = True
                    break

    allocated_df = pd.DataFrame(allocation)
    return allocated_df

st.title("Stocktake Task Allocator")

team_file = st.file_uploader("Upload Team CSV", type=["csv"], key="team")
task_file = st.file_uploader("Upload Tasks CSV", type=["csv"], key="tasks")

if team_file and task_file:
    team_df = pd.read_csv(team_file)
    task_df = pd.read_csv(task_file)

    if "speed" not in team_df.columns or "name" not in team_df.columns:
        st.error("Team file must have 'name' and 'speed' columns.")
    elif not all(col in task_df.columns for col in ['id', 'time', 'priority', 'difficulty', 'zone']):
        st.error("Tasks file must have 'id', 'time', 'priority', 'difficulty', and 'zone' columns.")
    else:
        allocated_df = allocate_tasks(team_df, task_df)
        st.success("Tasks Allocated")
        st.dataframe(allocated_df)

        csv_output = allocated_df.to_csv(index=False).encode('utf-8')
        st.download_button("Download Allocation CSV", csv_output, "allocation.csv", "text/csv")
