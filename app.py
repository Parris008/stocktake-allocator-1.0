import streamlit as st
import pandas as pd
import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
import datetime

if "firebase_app" not in st.session_state:
    firebase_cert = json.loads(os.environ["FIREBASE_CREDENTIALS"])
    cred = credentials.Certificate(firebase_key)
    firebase_admin.initialize_app(cred, name="stocktake_allocator")
    st.session_state.firebase_app = True
    
db = firestore.client()

st.set_page_config(page_title="Task Allocator & Team Tracker", layout="wide")
st.title("Task Allocator & Team Tracker")

view_mode = st.radio("Select View", ["Lead View", "Team Member View"])

def load_data():
    tasks = [doc.to_dict() | {"id": doc.id} for doc in db.collection("tasks").stream()]
    team = [doc.to_dict() | {"name": doc.id} for doc in db.collection("team").stream()]
    return pd.DataFrame(tasks), pd.DataFrame(team)

if view_mode == "Lead View":
    st.header("Lead View")
    task_file = st.file_uploader("Upload Task File (CSV)", type="csv", key="tasks")
    team_file = st.file_uploader("Upload Team File (CSV)", type="csv", key="team")

    if st.button("Allocate Tasks") and task_file and team_file:
        tasks = pd.read_csv(task_file)
        team = pd.read_csv(team_file)

        # Clear existing Firestore data
        for t in db.collection("tasks").stream():
            db.collection("tasks").document(t.id).delete()
        for m in db.collection("team").stream():
            db.collection("team").document(m.id).delete()

        # Upload team
        for _, row in team.iterrows():
            db.collection("team").document(row["name"]).set(row.to_dict())

        # Sort tasks by custom logic
        freezer = tasks[tasks["priority"] == "fz"]
        dairy = tasks[tasks["priority"] == "dy"]
        other = tasks[~tasks["priority"].isin(["fz", "dy"])]
        task_list = pd.concat([freezer, dairy, other])

        # Assign team round-robin
        team_cycle = iter(team["name"].tolist())
        assignments = []
        for _, task in task_list.iterrows():
            try:
                person = next(team_cycle)
            except StopIteration:
                team_cycle = iter(team["name"].tolist())
                person = next(team_cycle)
            task_data = task.to_dict()
            task_data["assigned_to"] = person
            task_data["status"] = "pending"
            assignments.append(task_data)

        # Upload tasks
        for i, task in enumerate(assignments):
            db.collection("tasks").document(str(i)).set(task)

        st.success("Tasks allocated and uploaded to Firebase.")

    elif st.button("View Unassigned Layouts"):
        task_df, _ = load_data()
        unassigned = task_df[task_df["assigned_to"].isna()]
        st.dataframe(unassigned if not unassigned.empty else "All layouts assigned.")

elif view_mode == "Team Member View":
    st.header("Team Member View")
    _, team_df = load_data()
    team_names = team_df["name"].tolist()
    selected_name = st.selectbox("Select your name", team_names)

    if selected_name:
        task_df, _ = load_data()
        tasks = task_df[(task_df["assigned_to"] == selected_name) & (task_df["status"] != "complete")]
        tasks = tasks.sort_values(by=["priority", "zone"])

        if tasks.empty:
            st.success("All tasks completed!")
        else:
            current = tasks.iloc[0]
            st.subheader(f"Current Task: {current['layout']}")
            st.write(f"Zone: {current['zone']}, Time: {current['time']}, Difficulty: {current['difficulty']}")

            if st.button("Mark as Complete"):
                db.collection("tasks").document(str(current["id"])).update({
                    "status": "complete",
                    "completed_at": datetime.datetime.now().isoformat()
                })
                st.success("Task marked as complete.")
                st.rerun()

            st.progress((1 - len(tasks) / len(task_df[task_df["assigned_to"] == selected_name])) * 100)

