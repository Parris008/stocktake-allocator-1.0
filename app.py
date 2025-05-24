import streamlit as st
import pandas as pd
import time
import firebase_admin
from firebase_admin import credentials, firestore
from collections import Counter, defaultdict
import os
import json

if "firebase_app" not in st.session_state:
    firebase_cert = json.loads(os.environ["FIREBASE_CREDENTIALS"])
    cred = credentials.Certificate(firebase_cert)
    firebase_admin.initialize_app(cred)
    st.session_state.firebase_app = True

db = firestore.client()

st.set_page_config(page_title="Task Allocator + Tracker (Firebase)", layout="wide")
st.title("Task Allocator and Team Tracker (Firebase Edition)")

view_mode = st.radio("Select View", ["Lead View", "Team Member View"])

if "task_state" not in st.session_state:
    st.session_state.task_state = {}

if view_mode == "Lead View":
    st.header("Lead View: Allocate Tasks")
    uploaded_tasks = st.file_uploader("Upload Tasks CSV", type=["csv"])
    uploaded_team = st.file_uploader("Upload Team CSV", type=["csv"])

    if uploaded_tasks and uploaded_team:
        tasks_df = pd.read_csv(uploaded_tasks)
        team_df = pd.read_csv(uploaded_team)

        for i, row in team_df.iterrows():
            db.collection("team").document(str(row["name"])).set(row.to_dict())

        for i, row in tasks_df.iterrows():
            db.collection("tasks").document(str(i)).set(row.to_dict())

        st.success("Tasks and team uploaded successfully!")

elif view_mode == "Team Member View":
    st.header("Team Member View: My Tasks")
    team_member = st.selectbox("Select your name", [doc.id for doc in db.collection("team").stream()])

    tasks = db.collection("tasks").stream()
    assigned_tasks = [t.to_dict() for t in tasks if t.to_dict().get("assigned_to") == team_member]

    for task in assigned_tasks:
        with st.expander(task["id"]):
            st.write(f"Zone: {task['zone']}")
            st.write(f"Time: {task['time']}")
            st.write(f"Difficulty: {task['difficulty']}")
            if st.button(f"Mark {task['id']} as complete", key=task["id"]):
                db.collection("tasks").document(task["id"]).update({"status": "complete"})
                st.success(f"{task['id']} marked as complete!")


