import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
import string
import datetime
import warnings
import seaborn as sns

# from pandas.core.common import SettingWithCopyWarning
# warnings.simplefilter(action="ignore", category=SettingWithCopyWarning)


import os

# Place validate_inputs here, outside the class
def validate_inputs(logger, input_dir):
    """
    Validates required input files and columns for persona analysis.
    Logs status and errors to the provided logger.
    """
    logger.info("=== PERSONA ANALYSIS INPUT VALIDATION ===")
    required_files = {
        'd4g_account.csv': ['npo02__LastCloseDate__c', 'Id'],
        'd4g_opportunity.csv': ['Amount', 'AccountId', 'CloseDate'],
        'd4g_address.csv': ['npsp__Household_Account__c', 'npsp__MailingCity__c', 'npsp__MailingState__c'],
    }
    
    logger.info(f"Checking {len(required_files)} input files for persona analysis:")
    
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
        logger.info("All persona analysis input files validated successfully.")
    return all_ok

class Persona_Analysis:
    def process_Personas(self, pdf, logger, output_dir, input_dir):
        logger.info("=== PERSONA ANALYSIS STARTED ===")
        try:
            # account
            acc_req_cols = ['npo02__LastCloseDate__c','Id']
            acc = pd.read_csv(os.path.join(input_dir, 'd4g_account.csv'))
            acc_cols = acc.columns.tolist()
            logger.debug(f'Columns in d4g_account.csv: {acc_cols}')
            try:
                logger.debug('Reading account table')
                all(req in acc_cols for req in acc_req_cols)
            except:
                logger.error("Account table columns missing, Can't continue Analysis!!")
                raise SystemExit("Account table columns missing, Can't continue Analysis!!") 

            acc['npo02__LastCloseDate__c'] = acc['npo02__LastCloseDate__c'].astype('datetime64[ns]') 
            acc['Last_Close_Month'] = acc['npo02__LastCloseDate__c'].dt.month
            acc["Id"] = acc["Id"].astype(str, errors = 'ignore')

            #opportunity
            opp_req_cols = ['Amount','AccountId','CloseDate']     
            try:
                logger.debug('Reading opportunity table')
                opp = pd.read_csv(os.path.join(input_dir, 'd4g_opportunity.csv'), low_memory=False)
                opp_cols = opp.columns.tolist()
                logger.debug(f'Columns in d4g_opportunity.csv: {opp_cols}')
                all(req in opp_cols for req in opp_req_cols)           
            except:
                logger.error("Oppotunity table columns missing")
                raise SystemExit("Oppotunity table columns missing, Can't continue Analysis!!") 
            opp['CloseDate'] = opp['CloseDate'].astype('datetime64[ns]') 
            opp['Close_Month'] = opp['CloseDate'].dt.month
            opp['Close_Year'] = opp['CloseDate'].dt.year

            #address
            addr_req_cols = ['npsp__Household_Account__c', 'npsp__MailingCity__c', 'npsp__MailingState__c']
            try:            
                logger.debug('Reading address table')
                addr = pd.read_csv(os.path.join(input_dir, 'd4g_address.csv'), low_memory=False)
                addr_cols=addr.columns.tolist()
                logger.debug(f'Columns in d4g_address.csv: {addr_cols}')
                all(req in addr_cols for req in addr_req_cols)
            except:
                logger.error("Address table columns missing")
                raise SystemExit("Address table columns missing, Can't continue Analysis!!") 


            ########################## data manipulation #############################
            logger.debug('\nData progressing on opportunity table')
            Amount = 'Amount' # donation amount col
            opp_id = 'AccountId' # oppotunity id col
            # account_id = 'Name' # account id col
            plot_dict = {'amount_total':1000, 'non_zero_counts':1, 'dormancy_years':2} # config on classification

            # opportunity table stats
            opp[opp_id] = opp[opp_id].astype(str, errors = 'ignore')

            # col for account & oppo table
            opp = opp.loc[:, [opp_id, Amount, 'Close_Month', 'Close_Year']]


            logger.debug('Fetching key column & calculate statistics for.....')
            logger.debug('   donation amount')
            a1 = opp.groupby(opp_id).agg({Amount:'min'}).reset_index().rename(columns = {Amount:'amount_min'})
            a2 = opp.groupby(opp_id).agg({Amount:'max'}).reset_index().rename(columns = {Amount:'amount_max'})
            a3 = opp.groupby(opp_id).agg({Amount:'mean'}).reset_index().rename(columns = {Amount:'amount_mean'})
            a9 = opp.groupby(opp_id).agg({Amount:'sum'}).reset_index().rename(columns = {Amount:'amount_total'})


            # year related columns
            logger.debug('   donation years & seasons')
            a4 = opp.groupby(opp_id).agg({'Close_Year':'min'}).reset_index().rename(columns = {'Close_Year':'start_year'})
            a5 = opp.groupby(opp_id).agg({'Close_Year':'max'}).reset_index().rename(columns = {'Close_Year':'latest_year'})

            # month related columns,seasonality checks
            a6 = opp.groupby(opp_id).agg({'Close_Month':'min'}).reset_index().rename(columns = {'Close_Month':'first_month'})
            a7 = opp.groupby(opp_id).agg({'Close_Month':'mean'}).reset_index().rename(columns = {'Close_Month':'avg_month'})
            a8 = opp.groupby(opp_id).agg({'Close_Month':'max'}).reset_index().rename(columns = {'Close_Month':'latest_month'})

            # non zero counts for accounts
            logger.debug('   non zero donation counts')
            a10 = opp[opp[Amount]>0].groupby(opp_id).agg({'Close_Month':'count'}).reset_index().rename(columns = {'Close_Month':'non_zero_counts'})

            # yearly aggregations
            logger.debug('   time statistics')
            a11 = opp[opp['Close_Year']==2024].groupby(opp_id).agg({'Close_Month':'count'}).reset_index().rename(columns = {'Close_Month':'this_year_non_zero_counts'})
            a12 = opp[opp['Close_Year']==2024].groupby(opp_id).agg({Amount:'sum'}).reset_index().rename(columns = {Amount:'this_year_amount_total'})
            a13 = opp[opp['Close_Year']==2024].groupby(opp_id).agg({Amount:'mean'}).reset_index().rename(columns = {Amount:'this_year_amount_mean'})

            a14 = opp[opp['Close_Year']==2023].groupby(opp_id).agg({'Close_Month':'count'}).reset_index().rename(columns = {'Close_Month':'prev_year_non_zero_counts'})
            a15 = opp[opp['Close_Year']==2023].groupby(opp_id).agg({Amount:'sum'}).reset_index().rename(columns = {Amount:'prev_year_amount_total'})
            a16 = opp[opp['Close_Year']==2023].groupby(opp_id).agg({Amount:'mean'}).reset_index().rename(columns = {Amount:'prev_year_amount_mean'})


            # merging into 1 account table
            logger.debug('Creating oppotunity summary table')

            account = a1.merge(a2,how='left',on=opp_id)
            account = account.merge(a3,how='left',on=opp_id)
            account = account.merge(a4,how='left',on=opp_id)
            account = account.merge(a5,how='left',on=opp_id)
            account = account.merge(a6,how='left',on=opp_id)
            account = account.merge(a7,how='left',on=opp_id)
            account = account.merge(a8,how='left',on=opp_id)
            account = account.merge(a9,how='left',on=opp_id)
            account = account.merge(a10,how='left',on=opp_id)
            account = account.merge(a11,how='left',on=opp_id)
            account = account.merge(a12,how='left',on=opp_id)
            account = account.merge(a13,how='left',on=opp_id)
            account = account.merge(a14,how='left',on=opp_id)
            account = account.merge(a15,how='left',on=opp_id)
            account = account.merge(a16,how='left',on=opp_id)

            y = pd.DataFrame()

            # TODO try catches for year availability - 2022? use min and max years
            for i in range(0,6):
                calc_year = datetime.datetime.now().year - i
                y1 = opp[(opp['Close_Year']==calc_year) & (opp[Amount]>0)].groupby(opp_id).agg({'Close_Month':'count'}).reset_index().rename(columns = {'Close_Month':'times_donated_'+str(calc_year)})
                y1.loc[y1['times_donated_'+str(calc_year)]>0, 'flag_donated_'+str(calc_year)] = 1
                y = y._append(y1, ignore_index=True)

            y = y.fillna(0)

            y['last_5_non0_years'] = 0
            for i in range(0,6):
                calc_year = datetime.datetime.now().year - i
                y['last_5_non0_years'] = y['last_5_non0_years'] + y['flag_donated_'+str(calc_year)]


            ## get state counts
            state_counts = pd.DataFrame(addr.groupby(['npsp__MailingState__c', 'npsp__MailingCity__c']).size())

            ################### New columns for classifications #####################
            logger.debug('\nClassifying...')
            account['account_age'] = datetime.datetime.now().year - account['start_year']

            account['dormancy_years'] = datetime.datetime.now().year - account['latest_year']

            account['average_total_donation'] = account['amount_total'] / account['account_age']

            account['average_time_between_donation'] = account['non_zero_counts'] / account['account_age']

            # Danation account
            df_value = account[account['amount_total']>0]
            # Non-donation/volunteer account
            df_none = account[account['amount_total'] <= 0]
            ########################### Statistics #######################
            stats = (df_value[['amount_total','non_zero_counts', 'dormancy_years']]
               .quantile([0.01, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0])
            )
            # Assign percentiles to new columns, do NOT overwrite persona
            for i in ['amount_total','non_zero_counts', 'dormancy_years']:
                df_value[i+'_percentiles'] = df_value[i].rank(pct=True)
            # (Do NOT assign percentiles to the 'persona' column)

            ########################## CLASSIFICATION #######################
            # Classification group in persona & color
            logger.debug('Creating Persona group...')
            df_value['persona'] = np.nan
            
            # Calculate quantiles for amount_total and median for dormancy_years
            amount_q33 = df_value['amount_total'].quantile(0.33)
            amount_q67 = df_value['amount_total'].quantile(0.67)
            dormancy_median = df_value['dormancy_years'].median()
            
            logger.debug(f'Amount quantiles: 33% = {amount_q33:.2f}, 67% = {amount_q67:.2f}')
            logger.debug(f'Dormancy median: {dormancy_median:.2f}')
            
            # Gary: top 33% amount_total and less than median dormancy_years
            df_value.loc[(df_value['amount_total'] >= amount_q67) & (df_value['dormancy_years'] < dormancy_median), 'persona'] = 'Gary'
            
            # Yara: lowest third quantile of amount_total and less than median dormancy_years
            df_value.loc[(df_value['amount_total'] <= amount_q33) & (df_value['dormancy_years'] < dormancy_median), 'persona'] = 'Yara'
            
            # Ryan: middle third amount_total and less than median dormancy_years
            df_value.loc[(df_value['amount_total'] > amount_q33) & (df_value['amount_total'] < amount_q67) & (df_value['dormancy_years'] < dormancy_median), 'persona'] = 'Ryan'
            
            # Laura: top 33% amount_total and greater than or equal to median dormancy_years
            df_value.loc[(df_value['amount_total'] >= amount_q67) & (df_value['dormancy_years'] >= dormancy_median), 'persona'] = 'Laura'
            
            # Peter: middle third amount_total and greater than or equal to median dormancy_years
            df_value.loc[(df_value['amount_total'] > amount_q33) & (df_value['amount_total'] < amount_q67) & (df_value['dormancy_years'] >= dormancy_median), 'persona'] = 'Peter'
            
            # Beth: lowest third quantile of amount_total and greater than or equal to median dormancy_years
            df_value.loc[(df_value['amount_total'] <= amount_q33) & (df_value['dormancy_years'] >= dormancy_median), 'persona'] = 'Beth'

            # --- Ensure persona column is string and not overwritten ---
            df_value['persona'] = df_value['persona'].astype(str)
            # Remove rows where persona is nan or 'nan'
            df_value = df_value[df_value['persona'].notna() & (df_value['persona'] != 'nan')]

            logger.debug('Creating color group...')
            # Assign colors based on new quantile-based personas
            # Gary: top 33% amount, low dormancy - Gold
            df_value.loc[df_value['persona'] == 'Gary', 'group'] = 'Gold'
            
            # Yara: lowest 33% amount, low dormancy - Light Blue
            df_value.loc[df_value['persona'] == 'Yara', 'group'] = 'Light Blue'
            
            # Ryan: middle 33% amount, low dormancy - Green
            df_value.loc[df_value['persona'] == 'Ryan', 'group'] = 'Green'
            
            # Laura: top 33% amount, high dormancy - Purple
            df_value.loc[df_value['persona'] == 'Laura', 'group'] = 'Purple'
            
            # Peter: middle 33% amount, high dormancy - Dark Blue
            df_value.loc[df_value['persona'] == 'Peter', 'group'] = 'Dark Blue'
            
            # Beth: lowest 33% amount, high dormancy - Red
            df_value.loc[df_value['persona'] == 'Beth', 'group'] = 'Red'

            df_mrg = acc.merge(df_value, left_on = "Id", right_on = opp_id, how = 'left')
            ################################ OUTPUT ##################################
            # Output table
            logger.debug('\nOutput progressing....')

            logger.debug('   Compiling output files')
            stats.to_csv(os.path.join(output_dir, f'd4g_stat_summary.csv'))
            df_value.to_csv(os.path.join(output_dir, f'd4g_value_output.csv'))
            df_none.to_csv(os.path.join(output_dir, f'd4g_potential_output.csv'))
            df_mrg.to_csv(os.path.join(output_dir, f'd4g_merge_account_output.csv'))
            state_counts.to_csv(os.path.join(output_dir, f'd4g_address_state_distibution.csv'))

            # visualizations
            logger.debug('   Compiling graph pdf')
            
            # Create first page: Overall Donor Statistics (3 subplots)
            fig1, axes1 = plt.subplots(1, 3, figsize=(18, 6))
            fig1.suptitle('Overall Donor Statistics', fontsize=16, fontweight='bold', y=0.95)
            
            for i, col in enumerate(['amount_total','non_zero_counts', 'dormancy_years']):
                df_value[col].hist(ax=axes1[i])
                axes1[i].set_title(col)
                axes1[i].grid()
                axes1[i].set_xlabel('value')
                axes1[i].set_ylabel('Count')
                # Format axes to avoid scientific notation
                if col == 'amount_total':
                    axes1[i].xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}' if x >= 1000 else f'${x:.0f}'))
                    axes1[i].yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:,.0f}' if x >= 1000 else f'{x:.0f}'))
                else:
                    axes1[i].xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:,.0f}' if x >= 1000 else f'{x:.0f}'))
                    axes1[i].yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:,.0f}' if x >= 1000 else f'{x:.0f}'))
            
            plt.tight_layout()
            pdf.savefig()
            plt.close()

            # Create persona donation behavior visualizations
            logger.debug('   Creating persona donation behavior visualizations')
            
            # Persona definitions with colors for reference (quantile-based)
            persona_definitions = {
                'Gary': {'description': 'Top 33% amount, low dormancy (high value, active donors)', 'color': 'gold'},
                'Yara': {'description': 'Lowest 33% amount, low dormancy (low value, active donors)', 'color': 'lightblue'},
                'Ryan': {'description': 'Middle 33% amount, low dormancy (medium value, active donors)', 'color': 'green'},
                'Laura': {'description': 'Top 33% amount, high dormancy (high value, dormant donors)', 'color': 'purple'},
                'Peter': {'description': 'Middle 33% amount, high dormancy (medium value, dormant donors)', 'color': 'darkblue'},
                'Beth': {'description': 'Lowest 33% amount, high dormancy (low value, dormant donors)', 'color': 'red'}
            }
            
            # Filter out personas that don't exist in the data
            existing_personas = df_value['persona'].dropna().unique()
            logger.debug(f'   Found personas in data: {existing_personas}')
            
            if len(existing_personas) > 0:
                # Create comprehensive persona analysis visualizations
                fig, axes = plt.subplots(2, 2, figsize=(18, 12))
                
                # 1. Total Amount Donated by Persona (Bar Chart)
                persona_amounts = df_value.groupby('persona')['amount_total'].sum().sort_values(ascending=False)
                # Use consistent colors from persona definitions
                colors = [persona_definitions[persona]['color'] for persona in persona_amounts.index]
                axes[0, 0].bar(persona_amounts.index, persona_amounts.values, color=colors, alpha=0.7)
                axes[0, 0].set_title('Total Amount Donated by Persona', fontweight='bold')
                axes[0, 0].set_xlabel('Persona')
                axes[0, 0].set_ylabel('Total Amount ($)')
                axes[0, 0].tick_params(axis='x', rotation=45)
                axes[0, 0].grid(True, alpha=0.3)
                # Format y-axis to avoid scientific notation
                axes[0, 0].yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}' if x >= 1000 else f'${x:.0f}'))
                
                # Add value labels on bars
                for i, v in enumerate(persona_amounts.values):
                    axes[0, 0].text(i, v + max(persona_amounts.values) * 0.01, f'${v:,.0f}', 
                                   ha='center', va='bottom', fontweight='bold')
                
                # 2. Number of Non-Zero Donations by Persona (Bar Chart)
                persona_counts = df_value.groupby('persona')['non_zero_counts'].sum().sort_values(ascending=False)
                # Use consistent colors from persona definitions
                colors = [persona_definitions[persona]['color'] for persona in persona_counts.index]
                axes[0, 1].bar(persona_counts.index, persona_counts.values, color=colors, alpha=0.7)
                axes[0, 1].set_title('Number of Non-Zero Donations by Persona', fontweight='bold')
                axes[0, 1].set_xlabel('Persona')
                axes[0, 1].set_ylabel('Number of Donations')
                axes[0, 1].tick_params(axis='x', rotation=45)
                axes[0, 1].grid(True, alpha=0.3)
                # Format y-axis to avoid scientific notation
                axes[0, 1].yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:,.0f}' if x >= 1000 else f'{x:.0f}'))
                
                # Add value labels on bars
                for i, v in enumerate(persona_counts.values):
                    axes[0, 1].text(i, v + max(persona_counts.values) * 0.01, f'{v:,.0f}', 
                                   ha='center', va='bottom', fontweight='bold')
                
                # 3. Average Amount per Donation by Persona (Bar Chart)
                persona_avg = df_value.groupby('persona')['amount_total'].mean().sort_values(ascending=False)
                # Use consistent colors from persona definitions
                colors = [persona_definitions[persona]['color'] for persona in persona_avg.index]
                axes[1, 0].bar(persona_avg.index, persona_avg.values, color=colors, alpha=0.7)
                axes[1, 0].set_title('Average Amount per Donation by Persona', fontweight='bold')
                axes[1, 0].set_xlabel('Persona')
                axes[1, 0].set_ylabel('Average Amount ($)')
                axes[1, 0].tick_params(axis='x', rotation=45)
                axes[1, 0].grid(True, alpha=0.3)
                # Format y-axis to avoid scientific notation
                axes[1, 0].yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}' if x >= 1000 else f'${x:.0f}'))
                
                # Add value labels on bars
                for i, v in enumerate(persona_avg.values):
                    axes[1, 0].text(i, v + max(persona_avg.values) * 0.01, f'${v:,.0f}', 
                                   ha='center', va='bottom', fontweight='bold')
                
                # 4. Persona Definitions Table
                axes[1, 1].set_title('Persona Definitions', fontweight='bold', fontsize=14)
                axes[1, 1].axis('off')  # Hide axes for table
                
                # Create table data
                table_data = []
                headers = ['Persona', 'Color', 'Description']
                
                for persona, info in persona_definitions.items():
                    table_data.append([persona, info['color'], info['description']])
                
                # Create the table
                table = axes[1, 1].table(cellText=table_data, colLabels=headers, 
                                        cellLoc='left', loc='center',
                                        colWidths=[0.15, 0.15, 0.7])
                
                # Style the table
                table.auto_set_font_size(False)
                table.set_fontsize(10)
                table.scale(1, 2)  # Adjust row height
                
                # Color the header row
                for i in range(len(headers)):
                    table[(0, i)].set_facecolor('#E6E6E6')
                    table[(0, i)].set_text_props(weight='bold')
                
                # Color the persona cells with their respective colors
                for i, (persona, info) in enumerate(persona_definitions.items(), 1):
                    # Color the persona name cell
                    table[(i, 0)].set_facecolor(info['color'])
                    table[(i, 0)].set_text_props(weight='bold', color='white')
                    
                    # Color the color name cell with the actual color
                    table[(i, 1)].set_facecolor(info['color'])
                    table[(i, 1)].set_text_props(weight='bold', color='white')
                    
                    # Style the description cell
                    table[(i, 2)].set_facecolor('#F8F8F8')
                
                plt.tight_layout()
                pdf.savefig()
                plt.close()
                
                # Create summary statistics table
                persona_stats = df_value.groupby('persona').agg({
                    'amount_total': ['sum', 'mean', 'count'],
                    'non_zero_counts': ['sum', 'mean'],
                    'dormancy_years': 'mean'
                }).round(2)
                
                # Flatten column names
                persona_stats.columns = ['Total_Amount', 'Avg_Amount', 'Account_Count', 'Total_Donations', 'Avg_Donations', 'Avg_Dormancy']
                
                logger.debug('   Persona donation behavior visualizations created successfully')
                logger.debug(f'   Persona statistics summary:\n{persona_stats}')
                
            else:
                logger.warning('   No personas found in the data for visualization')

            # address visualization
            # initialize the map and store it in a m object
            # get us map
            # us_map = geopandas.read_file(geodatasets.get_path("geoda.chicago_commpop"))
            # us_map.plot()

            logger.info("=== PERSONA ANALYSIS SUCCESSFULLY COMPLETED ===")
        except Exception as e:
            logger.error(f"=== PERSONA ANALYSIS FAILED ===")
            logger.error(f"Error during persona analysis: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
        
