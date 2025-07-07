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
    
    logger.info(f"Checking {len(required_files)} input files for email campaign analysis:")
    
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
            logger.info(f"File: {fname}")
            logger.info(f"  Required columns: {columns}")
            logger.info(f"  Actual columns: {list(df.columns)}")
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

#Attempt fancy color match like Persona analysis for campaigns but don't confuse colors and make them gradients
def fancy_gradcolors(num_colors):
    from matplotlib.colors import LinearSegmentedColormap

    # Define your two contrasting colors that are not with Persona Colors
    color2 = 'orange'
    color1 = 'teal'

    # Create a custom colormap from these two colors
    custom_cmap = LinearSegmentedColormap.from_list("my_gradient", [color1, color2], N=256)

    # We'll pick evenly spaced points along the colormap
    gradient_colors = [custom_cmap(i / (num_colors - 1)) for i in range(num_colors)]

    return gradient_colors



class Campaign_Analysis:   
    def process_campaign(self, pdf, logger, output_dir, input_dir):
        logger.info("=== EMAIL CAMPAIGN ANALYSIS STARTED ===")
        try:
            df_campaign_monitor_extract = pd.read_csv(os.path.join(input_dir, 'campaign_monitor_extract.csv'))
            df_contact_extract = pd.read_csv(os.path.join(input_dir, 'contact_extract.csv'))
            df_email_tracking_extract = pd.read_csv(os.path.join(input_dir, 'email_tracking_extract.csv'))

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
                
            df.head()

            # 1. Find top 5 CAMPAIGN_ID by sum of TOTAL_GIFTS
            top_campaigns = (
                df.groupby(by=['CAMPAIGN_ID'])['TOTAL_GIFTS']
                .sum()
                .nlargest(5)
                .index.tolist()
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
            # COMMENTED OUT: Email Campaign Performance Analysis temporarily suppressed
            # g = sns.FacetGrid(agg_df, col='CAMPAIGN_ID', col_wrap=3, height=4, sharex=True, sharey=True)
            # g.map_dataframe(
            #     sns.barplot, 
            #     x='NUM_OPENS_BIN', 
            #     y='TOTAL_GIFTS',
            #     color='skyblue'
            # )
            # g.set_axis_labels("NUM_OPENS (binned)", "Sum of TOTAL_GIFTS")
            # for ax in g.axes.flatten():
            #     ax.set_xticklabels([str(label.get_text()) for label in ax.get_xticklabels()], rotation=45, ha='right')
            # plt.subplots_adjust(top=0.85)
            # g.fig.suptitle('Email Campaign Performance Analysis', fontsize=18, fontweight='bold', y=0.98)
            # pdf.savefig()
            # plt.close()

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
                .reset_index()
            )
            avg_total_gifts.columns = ['GENDER', 'avg_TOTAL_GIFTS']

            print(avg_total_gifts)

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
            # COMMENTED OUT: Email Engagement Analysis temporarily suppressed
            # fig, ax = plt.subplots(figsize=(8,6))
            # fig.suptitle('Email Engagement Analysis', fontsize=18, fontweight='bold', y=0.98)
            # ax.scatter(df_opened['opened_count_7d'], df_opened['TOTAL_GIFTS'], alpha=0.6)
            # ax.set_xlabel("Number of 'Opened' records in 7-day window")
            # ax.set_ylabel("TOTAL_GIFTS")
            # ax.set_title("Distribution of 'Opened' Activity Count (7d window) vs TOTAL_GIFTS", pad=20)
            # ax.grid(True)
            # plt.tight_layout()
            # pdf.savefig()
            # plt.close()

            from datetime import timedelta

            # Ensure LAST_GIFT_DATE is datetime
            df['LAST_GIFT_DATE'] = pd.to_datetime(df['LAST_GIFT_DATE'])

            # Filter for 'Opened' activity and count occurrences for each CAMPAIGN_ID
            opened_counts = df[df['ACTIVITY'] == 'Opened'].groupby(by=['CAMPAIGN_ID']).size()

            # Get top 10 CAMPAIGN_IDs by 'Opened' activity count
            top_campaigns = opened_counts.nlargest(10).index.tolist()
            df_top = df[df['CAMPAIGN_ID'].isin(top_campaigns)].copy()

            # Filter for 'Opened' activity and calculate average TOTAL_GIFTS within 7-day window
            def avg_gifts_in_window_1(row):
                window_start = row['LAST_GIFT_DATE'] - timedelta(days=7)
                mask = (
                    (df_top['ACTIVITY'] == 'Opened') &
                    (df_top['LAST_GIFT_DATE'] >= window_start) &
                    (df_top['LAST_GIFT_DATE'] <= row['LAST_GIFT_DATE']) &
                    (df_top['CAMPAIGN_ID'] == row['CAMPAIGN_ID'])
                )
                return df_top.loc[mask, 'TOTAL_GIFTS'].mean()

            df_top['avg_gifts_7d'] = df_top.apply(avg_gifts_in_window_1, axis=1)

            # Aggregate data for plotting
            plot_data = df_top.groupby('CAMPAIGN_ID')['avg_gifts_7d'].mean().reset_index()

            # Create new page 4 with 2 subfigures matching the size of first 3 pages
            fig, axes = plt.subplots(2, 2, figsize=(20, 18))
            fig.suptitle('Email Campaign Analysis', fontsize=18, fontweight='bold', y=0.98)

            #Finish the final table analysis here so that the colors can be used consistently in the bar charts
            # Aggregate campaign performance by NUM_OPENS and NUM_CLICKS
            campaign_performance = df.groupby('CAMPAIGN_ID').agg({
                'CAMPAIGN_NAME': 'first',
                'NUM_OPENS': 'sum',
                'NUM_CLICKS': 'sum',
                'NUM_RECIPIENTS': 'first'
            }).reset_index()

            # Get 5 highest and 5 lowest performing campaigns by NUM_OPENS (then NUM_CLICKS as tie-breaker)
            highest_performing = df_campaign_monitor_extract.nlargest(n=5,columns=['NUM_OPENS', 'NUM_CLICKS']).sort_values(by=['NUM_OPENS', 'NUM_CLICKS'], ascending=[False, False])
            lowest_performing = df_campaign_monitor_extract.nsmallest(n=5,columns=['NUM_OPENS', 'NUM_CLICKS']).sort_values(by=['NUM_OPENS', 'NUM_CLICKS'], ascending=[False, False])

            # Combine for the table
            summary_data = pd.concat([highest_performing, lowest_performing])
            
            # Business-friendly names for the table
            column_names = ['Campaign ID', 'Campaign Name', 'Opens', 'Clicks', '# of Recipients']
            summary_data = summary_data[['CAMPAIGN_ID', 'CAMPAIGN_NAME', 'NUM_OPENS', 'NUM_CLICKS', 'NUM_RECIPIENTS']]

            colorlist=fancy_gradcolors(len(summary_data))
            summary_data['colors']=colorlist
            campaign_color_map = summary_data.set_index('CAMPAIGN_ID')['colors'].to_dict()


            # First subfigure: Top 5 Email Campaigns by Opens
            #opened_counts_top5 = opened_counts.nlargest(5)

            #colors = opened_counts_top5.index.map(campaign_color_map).fillna('gray')
         
            colors=[campaign_color_map.get(campaign_id, 'gray') for campaign_id in highest_performing['CAMPAIGN_ID']]
            opened_counts_top5 = highest_performing['NUM_OPENS']
            #axes[0, 0].bar(opened_counts_top5.index, opened_counts_top5.values, color=colors, alpha=0.7)
            axes[0, 0].bar(highest_performing['CAMPAIGN_ID'], highest_performing['NUM_OPENS'], color=colors, alpha=0.7)
            axes[0, 0].set_title('Top 5 Email Campaigns by Opens', fontweight='bold', fontsize=14, pad=10)
            axes[0, 0].set_xlabel('Campaign ID')
            axes[0, 0].set_ylabel('Number of Opens')
            axes[0, 0].tick_params(axis='x', rotation=45)
            axes[0, 0].grid(True, alpha=0.3)
            
            # Add value labels on bars
            for i, v in enumerate(opened_counts_top5.values):
                axes[0, 0].text(i, v + max(opened_counts_top5.values) * 0.01, f'{v:,.0f}', 
                           ha='center', va='bottom', fontweight='bold')
            
            # Second subfigure: Top 5 Email Campaigns by Total Donations within 7 days
            # Calculate total donations within 7 days for each campaign
            def total_gifts_7d_window(campaign_id):
                campaign_data = df[df['CAMPAIGN_ID'] == campaign_id].copy()
                if len(campaign_data) == 0:
                    return 0
                
                # For each row, calculate gifts within 7 days
                total_gifts = 0
                for _, row in campaign_data.iterrows():
                    last_gift_date = row['LAST_GIFT_DATE']
                    if last_gift_date is not None and not pd.isna(last_gift_date):
                        window_start = last_gift_date - timedelta(days=7)
                        mask = (
                            (df['CAMPAIGN_ID'] == campaign_id) &
                            (df['LAST_GIFT_DATE'] >= window_start) &
                            (df['LAST_GIFT_DATE'] <= last_gift_date)
                        )
                        total_gifts += df.loc[mask, 'TOTAL_GIFTS'].sum()
                return total_gifts
            
            # Get top campaigns by opens and calculate their 7-day donation totals
            top_campaigns_7d = opened_counts_top5.index.tolist()
            donation_totals_7d = {}
            
            for campaign_id in top_campaigns_7d:
                donation_totals_7d[campaign_id] = total_gifts_7d_window(campaign_id)
            
            # Sort by donation totals
            sorted_campaigns = sorted(donation_totals_7d.items(), key=lambda x: x[1], reverse=True)
            campaign_ids_7d = [item[0] for item in sorted_campaigns]
            donation_values_7d = [item[1] for item in sorted_campaigns]

            colors=[campaign_color_map.get(campaign_id, 'gray') for campaign_id in campaign_ids_7d]
            
            axes[0, 1].bar(campaign_ids_7d, donation_values_7d, color=colors, alpha=0.7)
            axes[0, 1].set_title('Top 5 Email Campaigns by Total Donations within 7 days', fontweight='bold', fontsize=14, pad=10)
            axes[0, 1].set_xlabel('Campaign ID')
            axes[0, 1].set_ylabel('Total Donations ($)')
            axes[0, 1].tick_params(axis='x', rotation=45)
            axes[0, 1].grid(True, alpha=0.3)
            
            # Format y-axis to avoid scientific notation
            axes[0, 1].yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}' if x >= 1000 else f'${x:.0f}'))
            
            # Add value labels on bars
            for i, v in enumerate(donation_values_7d):
                axes[0, 1].text(i, v + max(donation_values_7d) * 0.01, f'${v:,.0f}', 
                           ha='center', va='bottom', fontweight='bold')

            # Subfigure 3: Campaigns with Lowest Opens and Highest Unsubscribes
            # Aggregate opens and unsubscribes by campaign
            campaign_engagement = df.groupby('CAMPAIGN_ID').agg({
                'NUM_OPENS': 'sum',
                'NUM_UNSUBSCRIBED': 'sum'
            }).reset_index()

            # Get top 5 campaigns with lowest opens

            colors=[campaign_color_map.get(campaign_id, 'gray') for campaign_id in lowest_performing['CAMPAIGN_ID']]

            # Get top 5 campaigns with highest unsubscribes
            highest_unsubscribes = campaign_engagement.nlargest(5, 'NUM_UNSUBSCRIBED')


            # Plotting lowest opens
            axes[1, 0].bar(lowest_performing['CAMPAIGN_ID'], lowest_performing['NUM_OPENS'], color=colors, alpha=0.7)
            axes[1, 0].set_title('Top 5 Campaigns with Lowest Opens', fontweight='bold', fontsize=14, pad=15)
            axes[1, 0].set_xlabel('Campaign ID')
            axes[1, 0].set_ylabel('Total Opens')
            axes[1, 0].tick_params(axis='x', rotation=45)
            axes[1, 0].grid(True, alpha=0.3)
            for i, v in enumerate(lowest_performing['NUM_OPENS']):
                axes[1, 0].text(i, v + max(lowest_performing['NUM_OPENS']) * 0.01, f'{v:,.0f}', ha='center', va='bottom', fontweight='bold')

            # Subfigure 4: Summary Table of Highest and Lowest Performing Campaigns
            

            axes[1, 1].axis('off') # Hide axes for the table

            axes[1, 1].set_title('Campaign Performance Summary (Top/Bottom 4 by Opens/Clicks)', fontweight='bold', fontsize=14, pad=15)

            # Format numerical columns as integers
            formatted_data = summary_data[['CAMPAIGN_ID', 'CAMPAIGN_NAME', 'NUM_OPENS', 'NUM_CLICKS', 'NUM_RECIPIENTS']].copy()

            for col in ['NUM_OPENS', 'NUM_CLICKS', 'NUM_RECIPIENTS']:
                formatted_data[col] = formatted_data[col].apply(lambda x: f'{int(x):,}')

            table = axes[1, 1].table(cellText=formatted_data.values,
                                      colLabels=column_names,
                                      cellLoc='center', loc='top', bbox=[0, 0, 1, 1]) # Adjust bbox to reduce space
            
            table.auto_set_font_size(False)
            table.set_fontsize(10)
            table.scale(1, 2) # Adjust scale to reduce padding

            # Color the header row
            for i in range(len(column_names)):
                table[(0, i)].set_facecolor('#E6E6E6')
                table[(0, i)].set_text_props(weight='bold')
                row=1
                for color in colorlist:
                    table[(row, i)].set_facecolor(color)
                    row+=1

            plt.tight_layout()
            pdf.savefig()
            plt.close()

            # Create figure showing number of opens by Personas
            logger.debug('   Creating opens by personas visualization')
            
            try:
                # Load persona data from the output directory
                persona_file = os.path.join(output_dir, 'd4g_value_output.csv')
                if os.path.exists(persona_file):
                    df_personas = pd.read_csv(persona_file)
                    
                    # Merge email campaign data with persona data
                    # We'll use CONTACT ID to match with AccountId from persona data
                    df_with_personas = df.merge(
                        df_personas[['AccountId', 'persona']], 
                        left_on='CONTACT', 
                        right_on='AccountId', 
                        how='left'
                    )
                    
                    # Filter for 'Opened' activity and group by persona
                    df_opens_by_persona = df_with_personas[df_with_personas['ACTIVITY'] == 'Opened'].copy()
                    
                    if len(df_opens_by_persona) > 0 and 'persona' in df_opens_by_persona.columns:
                        # Count opens by persona
                        opens_by_persona = df_opens_by_persona.groupby('persona').size()
                        opens_by_persona = opens_by_persona.sort_values(ascending=False)
                        
                        # Persona color mapping (matching persona analysis)
                        persona_colors = {
                            'Gary': 'gold',
                            'Ryan': 'green', 
                            'Yara': 'lightblue',
                            'Laura': 'purple',
                            'Peter': 'darkblue',
                            'Beth': 'red'
                        }
                        
                        # Create the visualization
                        fig, ax = plt.subplots(figsize=(20, 10))
                        fig.suptitle('Email Campaign Performance by Donor Personas', fontsize=18, fontweight='bold', y=0.98)
                        
                        # Use consistent colors from persona definitions
                        colors = [persona_colors.get(str(persona), 'gray') for persona in opens_by_persona.index]
                        
                        # Create the bar plot
                        ax.bar(opens_by_persona.index, opens_by_persona.values, color=colors, alpha=0.7)
                        ax.set_title('Number of Email Opens by Persona', fontweight='bold', fontsize=14, pad=20)
                        ax.set_xlabel('Persona')
                        ax.set_ylabel('Number of Opens')
                        ax.tick_params(axis='x', rotation=45)
                        ax.grid(True, alpha=0.3)
                        
                        # Format y-axis to avoid scientific notation
                        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:,.0f}' if x >= 1000 else f'{x:.0f}'))
                        
                        # Add value labels on bars
                        for i, v in enumerate(opens_by_persona.values):
                            ax.text(i, v + max(opens_by_persona.values) * 0.01, f'{v:,.0f}', 
                                   ha='center', va='bottom', fontweight='bold')
                        
                        # Add persona definitions as text box
                        persona_definitions = {
                            'Gary': 'Top 33% amount, low dormancy (high value, active donors)',
                            'Ryan': 'Middle 33% amount, low dormancy (medium value, active donors)',
                            'Yara': 'Lowest 33% amount, low dormancy (low value, active donors)',
                            'Laura': 'Top 33% amount, high dormancy (high value, dormant donors)',
                            'Peter': 'Middle 33% amount, high dormancy (medium value, dormant donors)',
                            'Beth': 'Lowest 33% amount, high dormancy (low value, dormant donors)'
                        }
                        
                        # Create text box with persona definitions
                        textstr = '\n'.join([f'{persona}: {desc}' for persona, desc in persona_definitions.items()])
                        props = dict(boxstyle='round', facecolor='wheat', alpha=0.8)
                        ax.text(0.02, 0.98, textstr, transform=ax.transAxes, fontsize=10,
                               verticalalignment='top', bbox=props)
                        
                        plt.tight_layout()
                        pdf.savefig()
                        plt.close()
                        
                        logger.debug(f'   Opens by persona visualization created successfully. Found {len(opens_by_persona)} personas with opens data.')
                    else:
                        logger.warning('   No persona data found in opens data or no opens activity found')
                        
                else:
                    logger.warning(f'   Persona file not found: {persona_file}')
                    
            except Exception as e:
                logger.warning(f'   Could not create opens by personas visualization: {str(e)}')

            logger.info("=== EMAIL CAMPAIGN ANALYSIS SUCCESSFULLY COMPLETED ===")
        except Exception as e:
            logger.error(f"=== EMAIL CAMPAIGN ANALYSIS FAILED ===")
            logger.error(f"Error during email campaign analysis: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise








