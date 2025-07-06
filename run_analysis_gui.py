import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess
import os
import sys

HELP_TEXT = """
Required Input Files and Columns:

1. d4g_account.csv
   - Columns: npo02__LastCloseDate__c, Id
   - Additional columns used: Account Record Type, First_Gift_Year__c

2. d4g_opportunity.csv
   - Columns: Amount, AccountId, CloseDate
   - Additional columns used: Probability

3. d4g_address.csv
   - Columns: npsp__Household_Account__c, npsp__MailingCity__c, npsp__MailingState__c

4. campaign_monitor_extract.csv
   - Columns: Name, wbsendit__Campaign_ID__c, wbsendit__Num_Opens__c, wbsendit__Num_Clicks__c

5. contact_extract.csv
   - Columns: ID, goldenapp__Gender__c, npo02__LastCloseDate__c, npo02__TotalOppAmount__c

6. email_tracking_extract.csv
   - Columns: Name, wbsendit__Campaign_ID__c, wbsendit__Contact__c, wbsendit__Activity__c

All files should be placed in the selected input folder.
"""

def select_input_folder(input_var):
    folder = filedialog.askdirectory(title="Select Input Folder")
    if folder:
        if not os.path.exists(folder):
            if messagebox.askyesno("Create Folder?", f"Input folder does not exist. Create it?\n{folder}"):
                try:
                    os.makedirs(folder)
                except Exception as e:
                    messagebox.showerror("Error", f"Could not create input folder: {e}")
                    return
            else:
                return
        input_var.set(folder)

def select_output_folder(output_var):
    folder = filedialog.askdirectory(title="Select Output Folder")
    if folder:
        if not os.path.exists(folder):
            if messagebox.askyesno("Create Folder?", f"Output folder does not exist. Create it?\n{folder}"):
                try:
                    os.makedirs(folder)
                except Exception as e:
                    messagebox.showerror("Error", f"Could not create output folder: {e}")
                    return
            else:
                return
        output_var.set(folder)

def run_combined(input_var,output_var):
    input_dir = input_var.get()
    output_dir = output_var.get()
    if not input_dir or not output_dir:
        messagebox.showerror("Error", "Please select both input and output folders.")
        return

    env = os.environ.copy()
    env["INPUT_DIR"] = input_dir
    env["OUTPUT_DIR"] = output_dir

    try:
        # Pass output_dir and input_dir as command-line arguments
        result = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(__file__), "combined.py"), output_dir, input_dir],
            cwd=os.getcwd(),
            env=env,
            capture_output=True,
            text=True
        )
        error_file = os.path.join(output_dir, "error_summary.txt")
        if os.path.exists(error_file):
            with open(error_file, "r") as f:
                error_msg = f.read()
            messagebox.showerror("Error", f"Analysis completed with errors:\n{error_msg}")
        elif result.returncode == 0:
            messagebox.showinfo("Success", "Analysis completed successfully!\nCheck the output folder for results.")
        else:
            messagebox.showerror("Error", f"Error running script:\n{result.stderr}")
    except Exception as e:
        messagebox.showerror("Error", str(e))

def show_help():
    messagebox.showinfo("Help: Required Files & Columns", HELP_TEXT)


def main():
    root = tk.Tk()
    root.title("MFB Data Analysis Runner")

    input_var = tk.StringVar()
    output_var = tk.StringVar()

    # Instructions label
    instructions = ("Step 1: Select the folder containing your input files.\n"
                    "Step 2: Select the folder where you want the results.\n"
                    "Step 3: Click 'Run Analysis'.\n"
                    "If you need help, click the 'Help' button.")
    tk.Label(root, text=instructions, justify="left", fg="blue").grid(row=0, column=0, columnspan=3, pady=(10, 10))

    tk.Label(root, text="Input Folder:").grid(row=1, column=0, sticky="e")
    tk.Entry(root, textvariable=input_var, width=40).grid(row=1, column=1)
    tk.Button(root, text="Browse...", command=lambda: select_input_folder(input_var)).grid(row=1, column=2)

    tk.Label(root, text="Output Folder:").grid(row=2, column=0, sticky="e")
    tk.Entry(root, textvariable=output_var, width=40).grid(row=2, column=1)
    tk.Button(root, text="Browse...", command=lambda:select_output_folder(output_var)).grid(row=2, column=2)

    tk.Button(root, text="Run Analysis", command=lambda:run_combined(input_var,output_var), bg="green", fg="white").grid(row=3, column=1, pady=10)
    tk.Button(root, text="Help", command=show_help).grid(row=3, column=2, pady=10)
    tk.Button(root, text="Quit", command=root.quit, bg="red", fg="white").grid(row=4, column=1, pady=10)

    root.mainloop() 


if __name__ == "__main__":
    main()
