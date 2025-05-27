import streamlit as st
import pandas as pd
import time
import datetime

st.set_page_config(page_title="Offline Task Allocator", layout="wide")
st.title("Offline Task Allocator & Tracker")

view_mode = st.radio("Select View", ["Lead View", "Team Member View"])

if view_mode == "Lead View":
    st.header("Lead View - Allocate Tasks")
    tasks_file = st.file_uploader("Upload Task File (CSV)", type="csv")
    team_file = st.file_uploader("Upload Team File (CSV)", type="csv")

    if st.button("Allocate Tasks") and tasks_file and team_file:
        tasks_df = pd.read_csv(tasks_file)
        team_df = pd.read_csv(team_file)

        tasks_df = tasks_df.sort_values(by=["priority", "difficulty"], ascending=[False, False])
        team_df["capacity"] = team_df["speed"] * 300  # 5 hours in minutes
        assignments = {name: [] for name in team_df["name"]}
        capacities = dict(zip(team_df["name"], team_df["capacity"]))

        output_rows = []

        for _, task in tasks_df.iterrows():
            for name in capacities:
                if capacities[name] >= task["time"]:
                    task_info = task.to_dict()
                    task_info["assigned_to"] = name
                    assignments[name].append(task_info)
                    capacities[name] -= task["time"]
                    output_rows.append(task_info)
                    break

        st.session_state.assignments = assignments
        output_df = pd.DataFrame(output_rows)
        st.success("Tasks allocated.")

        st.download_button("Download Allocated Tasks CSV", output_df.to_csv(index=False), "allocated_tasks.csv", "text/csv")

        for name, tasks in assignments.items():
            st.subheader(f"Tasks for {name}")
            st.write(pd.DataFrame(tasks))

elif view_mode == "Team Member View":
    st.header("Team Member View")
    if "assignments" not in st.session_state:
        st.warning("No tasks have been allocated yet.")
    else:
        all_names = list(st.session_state.assignments.keys())
        selected_name = st.selectbox("Select Your Name", all_names)

        if selected_name:
            st.markdown("<h2 style='color:red;'>Let's get ready to count!</h2>", unsafe_allow_html=True)

            tasks = st.session_state.assignments[selected_name]
            if "task_state" not in st.session_state:
                st.session_state.task_state = {}

            member_state = st.session_state.task_state.setdefault(selected_name, {
                "current_task": None,
                "start_time": None,
                "completed": []
            })

            # Show full list of tasks
            st.subheader("All Tasks Assigned to You (in order):")
            st.write(pd.DataFrame(tasks)[["id", "zone", "time", "priority", "difficulty"]])

            if member_state["current_task"] is None and len(member_state["completed"]) < len(tasks):
                next_task = tasks[len(member_state["completed"])]
                if st.button("Start Next Task"):
                    member_state["current_task"] = next_task
                    member_state["start_time"] = time.time()

            if member_state["current_task"]:
                task = member_state["current_task"]
                st.subheader(f"Current Task: {task['id']}")
                st.write(f"Zone: {task['zone']}")
                st.write(f"Time Allocated: {task['time']} minutes")
                st.write(f"Difficulty: {task['difficulty']}")

                elapsed = (time.time() - member_state["start_time"]) / 60
                st.write(f"Time Spent: {elapsed:.1f} minutes")

                if st.button("Complete Task"):
                    member_state["completed"].append({
                        "task": task,
                        "started": datetime.datetime.fromtimestamp(member_state["start_time"]),
                        "finished": datetime.datetime.now(),
                        "elapsed": elapsed
                    })
                    member_state["current_task"] = None
                    member_state["start_time"] = None

            # Show progress
            st.write(f"Progress: {len(member_state['completed'])} of {len(tasks)} tasks completed")
            st.progress(len(member_state["completed"]) / len(tasks))
