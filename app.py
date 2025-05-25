import streamlit as st
import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore
import datetime
import os
import json

# Firebase initialization
if "firebase_app" not in st.session_state:
    if not firebase_admin._apps:
        cred = credentials.Certificate("firebase_key.json")
        firebase_admin.initialize_app(cred)
    st.session_state.firebase_app = True

db = firestore.client()

st.set_page_config(page_title="Task Allocator + Tracker", layout="wide")
st.title("Task Allocator and Team Tracker (DEBUG MODE)")

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
        st.write("Reading CSV files...")
        tasks = pd.read_csv(task_file)
        team = pd.read_csv(team_file)

        st.write(f"Loaded {len(tasks)} tasks and {len(team)} team members.")

        st.write("Clearing Firestore...")
        for t in db.collection("tasks").stream():
            db.collection("tasks").document(t.id).delete()
        for m in db.collection("team").stream():
            db.collection("team").document(m.id).delete()

        st.write("Uploading team data...")
        for _, row in team.iterrows():
            db.collection("team").document(row["name"]).set(row.to_dict())

        st.write("Sorting and allocating tasks...")
        tasks = tasks.sort_values(by="priority", ascending=False)

        task_list = []
        team_cycle = iter(team["name"].tolist())
        assigned_first = {}
        skipped = 0

        for _, task in tasks.iterrows():
            try:
                person = next(team_cycle)
            except StopIteration:
                team_cycle = iter(team["name"].tolist())
                person = next(team_cycle)

            speed = float(team[team["name"] == person]["speed"].values[0])
            if person not in assigned_first:
                if task["difficulty"] >= 4 and speed < 1:
                    st.write(f"Skipped task {task['id']} for {person} due to difficulty.")
                    skipped += 1
                    continue
                assigned_first[person] = True

            task_data = task.to_dict()
            task_data["assigned_to"] = person
            task_data["status"] = "pending"
            db.collection("tasks").document(task_data["id"]).set(task_data)
            st.write(f"Assigned task {task_data['id']} to {person}")

        st.success(f"Allocation complete. {len(task_list)} tasks assigned. {skipped} skipped.")

elif view_mode == "Team Member View":
    st.header("Team Member View")
    task_df, team_df = load_data()
    team_names = team_df["name"].tolist()
    selected_name = st.selectbox("Select your name", team_names)

    if selected_name:
        tasks = task_df[(task_df["assigned_to"] == selected_name) & (task_df["status"] != "complete")]
        tasks = tasks.sort_values(by="priority", ascending=False)

        if tasks.empty:
            st.success("All tasks completed!")
        else:
            current = tasks.iloc[0]
            st.subheader(f"Current Task: {current['id']}")
            st.write(f"Priority: {current['priority']}, Time: {current['time']} mins, Difficulty: {current['difficulty']}")

            if st.button("Mark as Complete"):
                db.collection("tasks").document(str(current["id"])).update({
                    "status": "complete",
                    "completed_at": datetime.datetime.now().isoformat()
                })
                st.success("Marked as complete.")
                st.rerun()

            total = len(task_df[task_df["assigned_to"] == selected_name])
            done = len(task_df[(task_df["assigned_to"] == selected_name) & (task_df["status"] == "complete")])
            progress = done / total if total > 0 else 0
            st.progress(progress)
