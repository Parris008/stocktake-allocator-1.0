
import streamlit as st
import pandas as pd
import time
import firebase_admin
from firebase_admin import credentials, firestore
from collections import Counter, defaultdict

import os
import json
firebase_cert = json.loads(os.environ["FIREBASE_CREDENTIALS"])
cred = credentials.Certificate(firebase_cert)
try: firebase_admin.get_app()
except ValueError: firebase_admin.initialize_app(cred)
st.session_state.firebase_app = True

db = firestore.client()

st.set_page_config(page_title="Task Allocator + Tracker (Firebase)", layout="wide")
st.title("Task Allocator and Team Tracker (Firebase Edition)")

view_mode = st.radio("Select View", ["Lead View", "Team Member View"])

if "task_state" not in st.session_state:
    st.session_state.task_state = {}

if view_mode == "Lead View":
    st.header("Lead View: Allocate Tasks")

    task_file = st.file_uploader("Upload tasks.csv", type="csv")
    team_file = st.file_uploader("Upload team.csv", type="csv")

    if task_file and team_file:
        tasks_df = pd.read_csv(task_file)
        team_df = pd.read_csv(team_file)

        tasks_df.columns = tasks_df.columns.str.strip().str.lower()
        team_df.columns = team_df.columns.str.strip().str.lower()

        def priority_key(row):
            priority = str(row.get('priority', '')).strip().lower()
            if priority == 'fz':
                return (0, row.get('zone', ''), -row.get('difficulty', 0))
            elif priority == 'dy':
                return (1, row.get('zone', ''), -row.get('difficulty', 0))
            else:
                priority_rank = {'high': 2, 'medium': 3, 'low': 4}
                return (priority_rank.get(priority, 5), row.get('zone', ''), -row.get('difficulty', 0))

        tasks_df["sort_key"] = tasks_df.apply(priority_key, axis=1)
        tasks_sorted = tasks_df.sort_values("sort_key").drop(columns="sort_key").to_dict("records")

        team = team_df.to_dict("records")
        for member in team:
            member["assigned"] = []
            member["used_time"] = 0
            member["locked_zone"] = None

        zone_remaining_tasks = defaultdict(int)
        for task in tasks_sorted:
            pr = str(task["priority"]).lower()
            if pr not in ["fz", "dy"]:
                zone_remaining_tasks[task["zone"]] += 1

        non_fz_dy_zones = sorted(zone_remaining_tasks)
        zone_cycle = iter(non_fz_dy_zones)
        unassigned_tasks = []

        for doc in db.collection("allocations").stream():
            db.collection("allocations").document(doc.id).delete()

        for task in tasks_sorted:
            best_fit = None
            min_used_time = float("inf")
            task_id = task.get("id")
            task_time = task.get("time", 0)
            task_zone = task.get("zone", "")
            task_difficulty = task.get("difficulty", 0)
            task_priority = str(task.get("priority", "")).strip().lower()

            for member in team:
                speed = member.get("speed", 1.0)
                adjusted_time = task_time / speed if speed else 0
                if member["used_time"] + adjusted_time <= 300:
                    if task_priority not in ["fz", "dy"]:
                        if not member["locked_zone"]:
                            try:
                                next_zone = next(zone_cycle)
                            except StopIteration:
                                zone_cycle = iter(non_fz_dy_zones)
                                next_zone = next(zone_cycle)
                            member["locked_zone"] = next_zone
                        if member["locked_zone"] != task_zone:
                            if zone_remaining_tasks[member["locked_zone"]] > 0:
                                continue
                            else:
                                member["locked_zone"] = task_zone
                        if len(member["assigned"]) == 0 and speed < 1.0 and task_difficulty >= 4:
                            continue

                    if member["used_time"] < min_used_time:
                        best_fit = member
                        min_used_time = member["used_time"]

            if best_fit:
                adjusted_time = task_time / best_fit["speed"] if best_fit["speed"] else 0
                task_data = {
                    "team_member": best_fit["name"],
                    "task_id": task_id,
                    "base_time": task_time,
                    "adjusted_time": round(adjusted_time, 1),
                    "priority": task.get("priority", ""),
                    "difficulty": task_difficulty,
                    "zone": task_zone,
                    "started": False,
                    "completed": False,
                    "start_time": None,
                    "complete_time": None,
                }
                db.collection("allocations").add(task_data)
                best_fit["used_time"] += adjusted_time
                if task_priority not in ["fz", "dy"]:
                    zone_remaining_tasks[task_zone] -= 1
            else:
                unassigned_tasks.append(task)

        st.success("Tasks allocated and stored in Firebase.")
        if unassigned_tasks:
            st.markdown("### Unassigned Tasks")
            st.dataframe(pd.DataFrame(unassigned_tasks)[["id", "time", "priority", "difficulty", "zone"]])

elif view_mode == "Team Member View":
    st.header("Team Member View")

    allocations = db.collection("allocations").stream()
    records = [doc.to_dict() | {"doc_id": doc.id} for doc in allocations]

    if not records:
        st.warning("No tasks allocated yet.")
    else:
        df = pd.DataFrame(records)
        df.columns = df.columns.str.strip().str.lower()
        team_members = df["team_member"].unique().tolist()
        selected_member = st.selectbox("Select your name", team_members)

        member_tasks = df[df["team_member"] == selected_member].reset_index(drop=True)
        total_tasks = len(member_tasks)
        completed = 0

        st.markdown(f"### Layouts Assigned to {selected_member}")

        for idx, row in member_tasks.iterrows():
            task_id = row["task_id"]
            adjusted_time = row["adjusted_time"]
            zone = row["zone"]
            doc_id = row["doc_id"]

            with st.expander(f"{idx+1}. {task_id} ({zone})"):
                st.write(f"Estimated Time: {adjusted_time} mins")

                if idx == 0 or all(member_tasks.loc[i, 'completed'] for i in range(idx)):
                    if not row["started"]:
                        if st.button(f"Start {task_id}", key=f"start_{task_id}"):
                            db.collection("allocations").document(doc_id).update({
                                "started": True,
                                "start_time": firestore.SERVER_TIMESTAMP
                            })
                            st.rerun()

                    elif not row["completed"]:
                        if st.button(f"Complete {task_id}", key=f"complete_{task_id}"):
                            db.collection("allocations").document(doc_id).update({
                                "completed": True,
                                "complete_time": firestore.SERVER_TIMESTAMP
                            })
                            st.rerun()

                        st.info("In Progress")

                    elif row["completed"]:
                        st.success("Completed")
                        completed += 1
                else:
                    st.warning("This layout is locked until the previous one is complete.")

        progress = int((completed / total_tasks) * 100)
        st.progress(progress / 100)
        st.markdown(f"**Progress: {completed} of {total_tasks} tasks complete ({progress}%)**")
