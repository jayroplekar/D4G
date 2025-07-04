import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
import string
import datetime
import warnings
warnings.filterwarnings('ignore') # Ignore all warnings
import seaborn as sns
import logging as log
import logging.handlers as hdl
import os

# Place validate_inputs here, outside the class
def validate_inputs(logger, input_dir):
    """
    Validates required input files and columns for campaign analysis.
    Logs status and errors to the provided logger.
    """
    logger.info("=== EMAIL CAMPAIGN ANALYSIS INPUT VALIDATION ===")
    required_files = {
        'campaign_monitor_extract.csv': ['Name', 'wbsendit__Campaign_ID__c', 'wbsendit__Num_Opens__c', 'wbsendit__Num_Clicks__c'],
        'contact_extract.csv': ['ID', 'goldenapp__Gender__c', 'npo02__LastCloseDate__c', 'npo02__TotalOppAmount__c'],
        'email_tracking_extract.csv': ['Name', 'wbsendit__Campaign_ID__c', 'wbsendit__Contact__c', 'wbsendit__Activity__c'],
    }
    
    logger.info(f"Checking {len(required_files)} files for email campaign analysis:")
    for fname, columns in required_files.items():
        logger.info(f"  - {fname}: {', '.join(columns)}")
    
    all_ok = True
    missing_columns = []
    
    for fname, columns in required_files.items():
        fpath = os.path.join(input_dir, fname)
        if not os.path.exists(fpath):
            logger.error(f"Missing required file: {fname}")
            all_ok = False
            continue
        try:
            df = pd.read_csv(fpath, nrows=1)
        except Exception as e:
            logger.error(f"Error reading {fname}: {e}")
            all_ok = False
            continue
        missing_cols = [col for col in columns if col not in df.columns]
        if missing_cols:
            logger.error(f"File {fname} is missing columns: {missing_cols}")
            missing_columns.extend([f"{fname}:{col}" for col in missing_cols])
            all_ok = False
        else:
            logger.info(f"File {fname} loaded successfully with all required columns.")
    
    if missing_columns:
        # Group missing columns by file
        file_errors = {}
        for error in missing_columns:
            file_name, column = error.split(':', 1)
            if file_name not in file_errors:
                file_errors[file_name] = []
            file_errors[file_name].append(column)
        
        logger.error("Missing columns by file:")
        for file_name, columns in file_errors.items():
            logger.error(f"  {file_name}: {', '.join(columns)}")
    
    if all_ok:
        logger.info("All campaign analysis input files validated successfully.")
    return all_ok

class Campaign_Analysis:   
    def process_campaign(self, pdf, logger, output_dir, input_dir):
        
        df_campaign_monitor_extract = pd.read_csv(f'{input_dir}/campaign_monitor_extract.csv') 
        df_contact_extract = pd.read_csv(f'{input_dir}/contact_extract.csv') 
        df_email_tracking_extract = pd.read_csv(f'{input_dir}/email_tracking_extract.csv')

        #Following to convert the actual column names at MFB into what the team used without refactoring code below and variable names are smaller too
        df_campaign_monitor_extract.rename(columns={'Name': 'CAMPAIGN_NAME','wbsendit__Campaign_ID__c':'CAMPAIGN_ID',\
                                                    'wbsendit__Num_Opens__c':'NUM_OPENS',\
                                                    'wbsendit__Num_Clicks__c':'NUM_CLICKS'}, inplace=True)

        df_contact_extract.rename(columns={'goldenapp__Gender__c': 'GENDER','npo02__LastCloseDate__c':'LAST_GIFT_DATE',\
                                                    'npo02__TotalOppAmount__c':'TOTAL_GIFTS'}, inplace=True)

        df_email_tracking_extract.rename(columns={'Name': 'CAMPAIGN','wbsendit__Campaign_ID__c':'CAMPAIGN_ID',\
                                                    'wbsendit__Contact__c':'CONTACT',\
                                                    'wbsendit__Activity__c':'ACTIVITY'}, inplace=True)

        df = df_email_tracking_extract.merge(df_campaign_monitor_extract, left_on=['CAMPAIGN', 'CAMPAIGN_ID'], 
                                             right_on=['CAMPAIGN_NAME','CAMPAIGN_ID'], how='left').merge(
                                            df_contact_extract, left_on=['CONTACT'], right_on=['ID'], how='left'
                                            )
                


        # %%
        df.head()

        # %%
        # 1. Find top 5 CAMPAIGN_ID by sum of TOTAL_GIFTS
        top_campaigns = (
            df.groupby('CAMPAIGN_ID')['TOTAL_GIFTS']
            .sum()
            .nlargest(5)
            .index
        )

        # 2. Filter dataframe for top campaigns
        df_top = df[df['CAMPAIGN_ID'].isin(top_campaigns)].copy()

        # 3. Bin NUM_OPENS
        df_top['NUM_OPENS_BIN'] = pd.cut(df_top['NUM_OPENS'], bins=10)

        # 4. Aggregate TOTAL_GIFTS by NUM_OPENS_BIN and CAMPAIGN_ID
        agg_df = (
            df_top.groupby(['CAMPAIGN_ID', 'NUM_OPENS_BIN'])['TOTAL_GIFTS']
            .sum()
            .reset_index()
        )

        # 5. Plot
        g = sns.FacetGrid(agg_df, col='CAMPAIGN_ID', col_wrap=3, height=4, sharex=True, sharey=True)
        g.map_dataframe(
            sns.barplot, 
            x='NUM_OPENS_BIN', 
            y='TOTAL_GIFTS',
            color='skyblue'
        )
        g.set_axis_labels("NUM_OPENS (binned)", "Sum of TOTAL_GIFTS")
        for ax in g.axes.flatten():
            ax.set_xticklabels([str(label.get_text()) for label in ax.get_xticklabels()], rotation=45, ha='right')
        plt.subplots_adjust(top=0.85)
        g.fig.suptitle('Sum of TOTAL_GIFTS by NUM_OPENS bins for Top 5 CAMPAIGN_IDs')
        pdf.savefig()
        plt.close()

        # %%
        grouped = (
            df.groupby(['ACTIVITY', 'CAMPAIGN_ID'], dropna=False)['TOTAL_GIFTS']
            .sum()
            .reset_index()
        )

        # For each ACTIVITY, get top 5 CAMPAIGN_IDs by TOTAL_GIFTS sum
        top5_by_activity = (
            grouped.sort_values(['ACTIVITY', 'TOTAL_GIFTS'], ascending=[True, False])
            .groupby('ACTIVITY')
            .head(5)
        )

        print(top5_by_activity)

        # %%
        # Categorize ACTIVITY as 'Unsubscribed' and 'Others'
        df['ACTIVITY_CAT'] = df['ACTIVITY'].apply(lambda x: 'Unsubscribed' if x == 'Unsubscribed' else 'Others')

        # Group by new category and CAMPAIGN_ID, sum TOTAL_GIFTS
        grouped = (
            df.groupby(['ACTIVITY_CAT', 'CAMPAIGN_ID'], dropna=False)['TOTAL_GIFTS']
            .sum()
            .reset_index()
        )

        # For each ACTIVITY_CAT, get top 5 CAMPAIGN_IDs by TOTAL_GIFTS sum
        top5_by_activity_cat = (
            grouped.sort_values(['ACTIVITY_CAT', 'TOTAL_GIFTS'], ascending=[True, False])
            .groupby('ACTIVITY_CAT')
            .head(5)
        )

        print(top5_by_activity_cat)

        # %%
        # Filter to only Male and Female
        df_gender = df[df['GENDER'].isin(['Male', 'Female'])].copy()

        # Group by GENDER and calculate count and mean for each column, round and convert to int
        result = (
            df_gender.groupby('GENDER')[['NUM_OPENS', 'TOTAL_GIFTS', 'NUM_CLICKS']]
            .agg(['count', 'mean'])
            .round(0)
            .astype(int)  # Convert to integer to remove decimal point
            .reset_index()
        )

        print(result)

        # Get just the average TOTAL_GIFTS for each gender, rounded and as integer
        avg_total_gifts = (
            df_gender.groupby('GENDER')['TOTAL_GIFTS']
            .mean()
            .round(0)
            .astype(int)
            .reset_index(name='avg_TOTAL_GIFTS')
        )

        print(avg_total_gifts)

        # %%
        # Categorize ACTIVITY as 'Unsubscribed' and 'Others'
        df['ACTIVITY_CAT'] = df['ACTIVITY'].apply(lambda x: 'Unsubscribed' if x == 'Unsubscribed' else 'Others')

        # Top 5 CAMPAIGN_IDs by sum of TOTAL_GIFTS for each ACTIVITY
        grouped = (
            df.groupby(['ACTIVITY', 'CAMPAIGN_ID'], dropna=False)['TOTAL_GIFTS']
            .sum()
            .reset_index()
        )
        top5_by_activity = (
            grouped.sort_values(['ACTIVITY', 'TOTAL_GIFTS'], ascending=[True, False])
            .groupby('ACTIVITY')
            .head(5)
        )
        print("Top 5 CAMPAIGN_IDs by TOTAL_GIFTS sum for each ACTIVITY:")
        print(top5_by_activity)

        # Top campaign ids by value counts grouped by ACTIVITY_CAT (Unsubscribed and Others)
        def top_campaigns_by_count_cat(df, n=5):
            result = []
            for cat, group in df.groupby('ACTIVITY_CAT', dropna=False):
                top_campaigns = group['CAMPAIGN_ID'].value_counts().head(n)
                for campaign_id, count in top_campaigns.items():
                    result.append({'ACTIVITY_CAT': cat, 'CAMPAIGN_ID': campaign_id, 'COUNT': count})
            return pd.DataFrame(result)

        top_campaigns_count_cat = top_campaigns_by_count_cat(df)
        print("\nTop campaign ids by value counts grouped by ACTIVITY_CAT:")
        print(top_campaigns_count_cat)

        # %%
        # import pandas as pd
        # import matplotlib.pyplot as plt

        # Ensure LAST_GIFT_DATE is datetime
        df['LAST_GIFT_DATE'] = pd.to_datetime(df['LAST_GIFT_DATE'])

        # Filter for 'Opened' activity
        df_opened = df[df['ACTIVITY'] == 'Opened'].copy()

        # For each row, filter for records within 7 days before LAST_GIFT_DATE (inclusive)
        def count_opened_in_window(row):
            window_start = row['LAST_GIFT_DATE'] - pd.Timedelta(days=7)
            mask = (
                (df['ACTIVITY'] == 'Opened') &
                (df['LAST_GIFT_DATE'] >= window_start) &
                (df['LAST_GIFT_DATE'] <= row['LAST_GIFT_DATE'])
            )
            return df.loc[mask].shape[0]

        df_opened['opened_count_7d'] = df_opened.apply(count_opened_in_window, axis=1)

        # Plot distribution: number of 'Opened' records in 7-day window vs TOTAL_GIFTS
        plt.figure(figsize=(8,6))
        plt.scatter(df_opened['opened_count_7d'], df_opened['TOTAL_GIFTS'], alpha=0.6)
        plt.xlabel("Number of 'Opened' records in 7-day window")
        plt.ylabel("TOTAL_GIFTS")
        plt.title("Distribution of 'Opened' Activity Count (7d window) vs TOTAL_GIFTS")
        plt.grid(True)
        plt.tight_layout()
        pdf.savefig()
        plt.close()

        # %%
        # df.to_csv(os.path.join(os.getcwd(), 'df_merged.csv'), index=False)

        # %%
        # import matplotlib.pyplot as plt
        # import pandas as pd
        from datetime import timedelta

        # Ensure LAST_GIFT_DATE is datetime
        df['LAST_GIFT_DATE'] = pd.to_datetime(df['LAST_GIFT_DATE'])

        # Filter for 'Opened' activity and count occurrences for each CAMPAIGN_ID
        opened_counts = df[df['ACTIVITY'] == 'Opened'].groupby('CAMPAIGN_ID').size()

        # Get top 10 CAMPAIGN_IDs by 'Opened' activity count
        top_campaigns = opened_counts.nlargest(10).index
        df_top = df[df['CAMPAIGN_ID'].isin(top_campaigns)].copy()

        # Filter for 'Opened' activity and calculate average TOTAL_GIFTS within 7-day window
        def avg_gifts_in_window(row):
            window_start = row['LAST_GIFT_DATE'] - timedelta(days=7)
            mask = (
                (df_top['ACTIVITY'] == 'Opened') &
                (df_top['LAST_GIFT_DATE'] >= window_start) &
                (df_top['LAST_GIFT_DATE'] <= row['LAST_GIFT_DATE']) &
                (df_top['CAMPAIGN_ID'] == row['CAMPAIGN_ID'])
            )
            return df_top.loc[mask, 'TOTAL_GIFTS'].mean()

        df_top['avg_gifts_7d'] = df_top.apply(avg_gifts_in_window, axis=1)

        # Aggregate data for plotting
        plot_data = df_top.groupby('CAMPAIGN_ID')['avg_gifts_7d'].mean().reset_index()

        # Create a single plot with 10 subplots in a 2x5 grid
        fig, axes = plt.subplots(2, 5, figsize=(20, 10), sharey=True)
        axes = axes.flatten()

        for i, campaign_id in enumerate(top_campaigns):
            campaign_data = plot_data[plot_data['CAMPAIGN_ID'] == campaign_id]
            axes[i].bar(
                [campaign_id],
                campaign_data['avg_gifts_7d'],
                color='skyblue',
                alpha=0.7
            )
            axes[i].set_title(f"Campaign ID: {campaign_id}")
            axes[i].set_xlabel("Campaign ID")
            axes[i].grid(True)

        # Remove the last empty subplot if there are fewer than 10 plots
        for j in range(len(top_campaigns), len(axes)):
            fig.delaxes(axes[j])

        axes[0].set_ylabel("Average TOTAL_GIFTS")
        fig.suptitle("Top 10 Campaigns: Average TOTAL_GIFTS (7-day window)", fontsize=16)
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        pdf.savefig()
        plt.close()

        # %%
        # import matplotlib.pyplot as plt
        # import pandas as pd
        # from datetime import timedelta

        # Ensure LAST_GIFT_DATE is datetime
        df['LAST_GIFT_DATE'] = pd.to_datetime(df['LAST_GIFT_DATE'])

        # Filter for 'Opened' activity and count occurrences for each CAMPAIGN_ID
        opened_counts = df[df['ACTIVITY'] == 'Opened'].groupby('CAMPAIGN_ID').size()

        # Get top 10 CAMPAIGN_IDs by 'Opened' activity count
        top_campaigns = opened_counts.nlargest(10).index
        df_top = df[df['CAMPAIGN_ID'].isin(top_campaigns)].copy()

        # Filter for 'Opened' activity and calculate average TOTAL_GIFTS within 7-day window
        def avg_gifts_in_window(row):
            window_start = row['LAST_GIFT_DATE'] - timedelta(days=7)
            mask = (
                (df_top['ACTIVITY'] == 'Opened') &
                (df_top['LAST_GIFT_DATE'] >= window_start) &
                (df_top['LAST_GIFT_DATE'] <= row['LAST_GIFT_DATE']) &
                (df_top['CAMPAIGN_ID'] == row['CAMPAIGN_ID'])
            )
            return df_top.loc[mask, 'TOTAL_GIFTS'].mean()

        df_top['avg_gifts_7d'] = df_top.apply(avg_gifts_in_window, axis=1)

        # Aggregate data for plotting
        plot_data = (
            df_top.groupby('CAMPAIGN_ID')
            .agg(avg_gifts_7d=('avg_gifts_7d', 'mean'), opened_count=('ACTIVITY', 'size'))
            .reset_index()
        )

        # Determine global y-axis limits for synchronization
        max_avg_gifts = plot_data['avg_gifts_7d'].max()
        max_opened_count = plot_data['opened_count'].max()

        # Create a single plot with 10 subplots in a 2x5 grid
        fig, axes = plt.subplots(2, 5, figsize=(20, 10), sharey=False)
        axes = axes.flatten()

        for i, campaign_id in enumerate(top_campaigns):
            campaign_data = plot_data[plot_data['CAMPAIGN_ID'] == campaign_id]
            
            ax1 = axes[i]
            ax2 = ax1.twinx()  # Create a twin y-axis
            
            # Bar for average TOTAL_GIFTS
            ax1.bar(
                [0],  # Single bar at position 0
                campaign_data['avg_gifts_7d'],
                color='skyblue',
                alpha=0.7,
                width=0.4,
                label='Avg TOTAL_GIFTS'
            )
            ax1.set_ylabel("Avg TOTAL_GIFTS", color='skyblue')
            ax1.tick_params(axis='y', labelcolor='skyblue')
            ax1.set_ylim(0, max_avg_gifts * 1.1)  # Synchronize y-axis for avg TOTAL_GIFTS
            
            # Bar for 'Opened' count
            ax2.bar(
                [0.5],  # Single bar at position 0.5
                campaign_data['opened_count'],
                color='orange',
                alpha=0.7,
                width=0.4,
                label='Opened Count'
            )
            ax2.set_ylabel("Opened Count", color='orange')
            ax2.tick_params(axis='y', labelcolor='orange')
            ax2.set_ylim(0, max_opened_count * 1.1)  # Synchronize y-axis for Opened Count
            
            ax1.set_title(f"Campaign ID: {campaign_id}")
            ax1.set_xticks([0, 0.5])
            ax1.set_xticklabels(['Avg Gifts', 'Opened Count'])
            ax1.grid(False)
            ax2.grid(False)

        # Remove the last empty subplot if there are fewer than 10 plots
        for j in range(len(top_campaigns), len(axes)):
            fig.delaxes(axes[j])

        fig.suptitle("Top 10 Campaigns: Avg TOTAL_GIFTS and Opened Count (7-day window)", fontsize=16)
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        pdf.savefig()
        plt.close()

        # %%


        # %% [markdown]
        # ## Dual Axis Bar Plots for Top 10 Campaigns
        # This section shows, for the top 10 campaigns by 'Opened' activity count, the average of total gifts (7-day window) and the number of times each campaign was opened. All axes are synchronized for comparison. A summary table is also provided.

        # %%
        # import matplotlib.pyplot as plt
        # import pandas as pd
        # from datetime import timedelta

        # Ensure LAST_GIFT_DATE is datetime
        if not pd.api.types.is_datetime64_any_dtype(df['LAST_GIFT_DATE']):
            df['LAST_GIFT_DATE'] = pd.to_datetime(df['LAST_GIFT_DATE'])

        # Filter for 'Opened' activity and count occurrences for each CAMPAIGN_ID
        opened_counts = df[df['ACTIVITY'] == 'Opened'].groupby('CAMPAIGN_ID').size()

        # Get top 10 CAMPAIGN_IDs by 'Opened' activity count
        top_campaigns = opened_counts.nlargest(10).index

        df_top = df[df['CAMPAIGN_ID'].isin(top_campaigns)].copy()

        # For each row, calculate average TOTAL_GIFTS in 7-day window for its campaign

        def avg_gifts_in_window(row):
            window_start = row['LAST_GIFT_DATE'] - timedelta(days=7)
            mask = (
                (df_top['ACTIVITY'] == 'Opened') &
                (df_top['LAST_GIFT_DATE'] >= window_start) &
                (df_top['LAST_GIFT_DATE'] <= row['LAST_GIFT_DATE']) &
                (df_top['CAMPAIGN_ID'] == row['CAMPAIGN_ID'])
            )
            return df_top.loc[mask, 'TOTAL_GIFTS'].mean()

        # Only apply to rows with 'Opened' activity for efficiency
        opened_rows = df_top[df_top['ACTIVITY'] == 'Opened'].copy()
        opened_rows['avg_gifts_7d'] = opened_rows.apply(avg_gifts_in_window, axis=1)

        # Aggregate for plotting
        plot_data = (
            opened_rows.groupby('CAMPAIGN_ID')
            .agg(avg_gifts_7d=('avg_gifts_7d', 'mean'), opened_count=('ACTIVITY', 'size'))
            .reset_index()
        )

        # Determine global y-axis limits for synchronization
        max_avg_gifts = plot_data['avg_gifts_7d'].max()
        max_opened_count = plot_data['opened_count'].max()

        # Create a single plot with 10 subplots in a 2x5 grid
        fig, axes = plt.subplots(2, 5, figsize=(20, 10), sharey=False)
        axes = axes.flatten()

        for i, campaign_id in enumerate(top_campaigns):
            campaign_data = plot_data[plot_data['CAMPAIGN_ID'] == campaign_id]
            ax1 = axes[i]
            ax2 = ax1.twinx()
            # Bar for average TOTAL_GIFTS
            ax1.bar([0], campaign_data['avg_gifts_7d'], color='skyblue', alpha=0.7, width=0.4, label='Avg TOTAL_GIFTS')
            ax1.set_ylabel("Avg TOTAL_GIFTS", color='skyblue')
            ax1.tick_params(axis='y', labelcolor='skyblue')
            ax1.set_ylim(0, max_avg_gifts * 1.1)
            # Bar for 'Opened' count
            ax2.bar([0.5], campaign_data['opened_count'], color='orange', alpha=0.7, width=0.4, label='Opened Count')
            ax2.set_ylabel("Opened Count", color='orange')
            ax2.tick_params(axis='y', labelcolor='orange')
            ax2.set_ylim(0, max_opened_count * 1.1)
            ax1.set_title(f"Campaign ID: {campaign_id}")
            ax1.set_xticks([0, 0.5])
            ax1.set_xticklabels(['Avg Gifts', 'Opened Count'])
            ax1.grid(False)
            ax2.grid(False)

        # Remove the last empty subplot if there are fewer than 10 plots
        for j in range(len(top_campaigns), len(axes)):
            fig.delaxes(axes[j])

        fig.suptitle("Top 10 Campaigns: Avg TOTAL_GIFTS and Opened Count (7-day window)", fontsize=16)
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        pdf.savefig()
        plt.close()

        # Show table of how many times each of these top 10 campaign ids have been opened
        print("Table: Number of times each top 10 campaign was 'Opened':")
        print(plot_data[['CAMPAIGN_ID', 'opened_count']].rename(columns={'opened_count': "Opened Count"}))
        
        #display(plot_data[['CAMPAIGN_ID', 'opened_count']].rename(columns={'opened_count': "Opened Count"}))


        # %%








