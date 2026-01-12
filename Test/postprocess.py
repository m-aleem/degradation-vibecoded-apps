################################################################################
# Python script to plot JMeter test an Python monitoring script results
################################################################################

import pandas as pd
import matplotlib.pyplot as plt

# Define the list of apps to plot
apps = [
    'gemini-2.5-flash-445',
    'gpt-oss-120b-446',
    'deepseek-chat-v3.1-241',
    # Uncomment for Part 2:
    # "gemini-2.5-flash-418",
    # "gpt-oss-120b-115",
    # "deepseek-chat-v3.1-366"
]

data = {}
for app in apps:
    JMETER_RESULTS = f"./{app}/Output/jmeter_results.jtl"
    MEM_RESULTS = f"./{app}/Output/monitor_results.csv"

    try:
        # Load JMeter CSV
        df_jmeter = pd.read_csv(JMETER_RESULTS)
        df_jmeter["time"] = (df_jmeter["timeStamp"] - df_jmeter["timeStamp"].min()) / (1000 * 3600)
        df_jmeter["elapsed"] = df_jmeter["elapsed"].astype(float)

        # Load Python monitoring CSV
        df_mem = pd.read_csv(MEM_RESULTS)
        df_mem_project = df_mem[df_mem["scope"] == "project"].copy()
        df_mem_project["memory_mib"] = df_mem_project["memory_mib"].astype(float)
        df_mem_project["time"] = (df_mem_project["timestamp"] - df_jmeter["timeStamp"].min()) / (1000 * 3600)

        data[app] = {
            'jmeter': df_jmeter,
            'memory': df_mem_project
        }

    except FileNotFoundError as e:
        print(f"Error loading data for {app}: {e}")
    except Exception as e:
        print(f"Error processing {app}: {e}")

if data:
    fig1, axes1 = plt.subplots(1, len(apps), figsize=(18, 4), sharey=True)
    if len(apps) == 1:
        axes1 = [axes1]

    for idx, app in enumerate(apps):
        if app in data:
            axes1[idx].plot(data[app]['memory']["time"], data[app]['memory']["memory_mib"], color="blue")
            axes1[idx].set_xlabel("Time (hours)")
            axes1[idx].set_title(app)
            axes1[idx].grid(True)
            axes1[idx].set_xlim(left=0)

    axes1[0].set_ylabel("Memory Usage (MiB)")
    # fig1.suptitle("Memory Usage Comparison", fontsize=14)
    plt.tight_layout()
    plt.show()

    # Create response time subplot (3 columns, 1 row)
    fig2, axes2 = plt.subplots(1, len(apps), figsize=(18, 4), sharey=True)
    if len(apps) == 1:
        axes2 = [axes2]

    for idx, app in enumerate(apps):
        if app in data:
            axes2[idx].plot(data[app]['jmeter']["time"], data[app]['jmeter']["elapsed"], color="blue")
            axes2[idx].set_xlabel("Time (hours)")
            axes2[idx].set_title(app)
            axes2[idx].grid(True)
            axes2[idx].set_xlim(left=0)
            axes2[idx].set_ylim(bottom=0)

    axes2[0].set_ylabel("Response Time (ms)")
    # fig2.suptitle("Response Time Comparison", fontsize=14)
    plt.tight_layout()
    plt.show()