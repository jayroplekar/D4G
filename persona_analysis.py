import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
import string
import datetime
import warnings

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
    
    logger.info(f"Checking {len(required_files)} files for persona analysis:")
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
        logger.info("All persona analysis input files validated successfully.")
    return all_ok

class Persona_Analysis:
    def process_Personas(self, pdf, logger, output_dir, input_dir):
        # account
        acc_req_cols = ['npo02__LastCloseDate__c','Id']
        acc = pd.read_csv(f'{input_dir}/d4g_account.csv')
        acc_cols = acc.columns
        logger.info(f'DEBUG: Columns in d4g_account.csv: {list(acc_cols)}')
        try:
            logger.info('Reading account table')
            all(req in acc_cols for req in acc_req_cols)
        except:
            logger.info("Account table columns missing, Can't continue Analysis!!")
            raise SystemExit("Account table columns missing, Can't continue Analysis!!") 

        acc['npo02__LastCloseDate__c'] = acc['npo02__LastCloseDate__c'].astype('datetime64[ns]') 
        acc['Last_Close_Month'] = acc['npo02__LastCloseDate__c'].dt.month
        acc["Id"] = acc["Id"].astype(str, errors = 'ignore')

        #opportunity
        opp_req_cols = ['Amount','AccountId','CloseDate']     
        try:
            logger.info('Reading opportunity table')
            opp = pd.read_csv(f'{input_dir}/d4g_opportunity.csv',low_memory=False)
            opp_cols = opp.columns
            all(req in opp_cols for req in opp_req_cols)           
        except:
            logger.info("Oppotunity table columns missing")
            raise SystemExit("Oppotunity table columns missing, Can't continue Analysis!!") 
        opp['CloseDate'] = opp['CloseDate'].astype('datetime64[ns]') 
        opp['Close_Month'] = opp['CloseDate'].dt.month
        opp['Close_Year'] = opp['CloseDate'].dt.year

        #address
        addr_req_cols = ['npsp__Household_Account__c', 'npsp__MailingCity__c', 'npsp__MailingState__c']
        try:            
            logger.info('Reading address table')
            addr = pd.read_csv(f'{input_dir}/d4g_address.csv',low_memory=False)
            addr_cols=addr.columns
            all(req in addr_cols for req in addr_req_cols)
        except:
            logger.info("Address table columns missing")
            raise SystemExit("Address table columns missing, Can't continue Analysis!!") 


        ########################## data manipulation #############################
        logger.info('\nData progressing on opportunity table')
        Amount = 'Amount' # donation amount col
        opp_id = 'AccountId' # oppotunity id col
        # account_id = 'Name' # account id col
        plot_dict = {'amount_total':1000, 'non_zero_counts':1, 'dormancy_years':2} # config on classification

        # opportunity table stats
        # print("opportunity table: ", opp.shape)

        opp[opp_id] = opp[opp_id].astype(str, errors = 'ignore')

        # col for account & oppo table
        opp = opp.loc[:, [opp_id, Amount, 'Close_Month', 'Close_Year']]


        logger.info('Fetching key column & calculate statistics for.....')
        # Stats account-wise
        logger.info('   donation amount')
        a1 = opp.groupby(opp_id).agg({Amount:'min'}).reset_index().rename(columns = {Amount:'amount_min'})
        a2 = opp.groupby(opp_id).agg({Amount:'max'}).reset_index().rename(columns = {Amount:'amount_max'})
        a3 = opp.groupby(opp_id).agg({Amount:'mean'}).reset_index().rename(columns = {Amount:'amount_mean'})
        a9 = opp.groupby(opp_id).agg({Amount:'sum'}).reset_index().rename(columns = {Amount:'amount_total'})
        # print("a1: ", a1.shape)
        # print("a2: ", a2.shape)
        # print("a3: ", a3.shape)


        # year related columns
        logger.info('   donation years & seasons')
        a4 = opp.groupby(opp_id).agg({'Close_Year':'min'}).reset_index().rename(columns = {'Close_Year':'start_year'})
        a5 = opp.groupby(opp_id).agg({'Close_Year':'max'}).reset_index().rename(columns = {'Close_Year':'latest_year'})

        # month related columns,seasonality checks
        a6 = opp.groupby(opp_id).agg({'Close_Month':'min'}).reset_index().rename(columns = {'Close_Month':'first_month'})
        a7 = opp.groupby(opp_id).agg({'Close_Month':'mean'}).reset_index().rename(columns = {'Close_Month':'avg_month'})
        a8 = opp.groupby(opp_id).agg({'Close_Month':'max'}).reset_index().rename(columns = {'Close_Month':'latest_month'})

        # non zero counts for accounts
        logger.info('   non zero donation counts')
        a10 = opp[opp[Amount]>0].groupby(opp_id).agg({'Close_Month':'count'}).reset_index().rename(columns = {'Close_Month':'non_zero_counts'})

        # yearly aggregations
        logger.info('   time statistics')
        a11 = opp[opp['Close_Year']==2024].groupby(opp_id).agg({'Close_Month':'count'}).reset_index().rename(columns = {'Close_Month':'this_year_non_zero_counts'})
        a12 = opp[opp['Close_Year']==2024].groupby(opp_id).agg({Amount:'sum'}).reset_index().rename(columns = {Amount:'this_year_amount_total'})
        a13 = opp[opp['Close_Year']==2024].groupby(opp_id).agg({Amount:'mean'}).reset_index().rename(columns = {Amount:'this_year_amount_mean'})

        a14 = opp[opp['Close_Year']==2023].groupby(opp_id).agg({'Close_Month':'count'}).reset_index().rename(columns = {'Close_Month':'prev_year_non_zero_counts'})
        a15 = opp[opp['Close_Year']==2023].groupby(opp_id).agg({Amount:'sum'}).reset_index().rename(columns = {Amount:'prev_year_amount_total'})
        a16 = opp[opp['Close_Year']==2023].groupby(opp_id).agg({Amount:'mean'}).reset_index().rename(columns = {Amount:'prev_year_amount_mean'})


        # merging into 1 account table
        logger.info('Creating oppotunity summary table')

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
        # print("account: ", account.shape)

        y = pd.DataFrame()

        # TODO try catches for year availability - 2022? use min and max years
        for i in range(0,6):
            calc_year = datetime.datetime.now().year - i
            # print("calc_year: ", calc_year)
            y1 = opp[(opp['Close_Year']==calc_year) & (opp[Amount]>0)].groupby(opp_id).agg({'Close_Month':'count'}).reset_index().rename(columns = {'Close_Month':'times_donated_'+str(calc_year)})
            # print("y1: ", y1)
            y1.loc[y1['times_donated_'+str(calc_year)]>0, 'flag_donated_'+str(calc_year)] = 1
            y = y._append(y1, ignore_index=True)

        y = y.fillna(0)

        y['last_5_non0_years'] = 0
        for i in range(0,6):
            calc_year = datetime.datetime.now().year - i
            y['last_5_non0_years'] = y['last_5_non0_years'] + y['flag_donated_'+str(calc_year)]

        # print("y: ", y.shape)


        ## get state counts
        state_counts = pd.DataFrame(addr.groupby(['npsp__MailingState__c', 'npsp__MailingCity__c']).size())
        # print(type(state_counts))

        ################### New columns for classifications #####################
        logger.info('\nClassifying...')
        account['account_age'] = datetime.datetime.now().year - account['start_year']

        account['dormancy_years'] = datetime.datetime.now().year - account['latest_year']

        account['average_total_donation'] = account['amount_total'] / account['account_age']

        account['average_time_between_donation'] = account['non_zero_counts'] / account['account_age']

        # Danation account
        df_value = account[account['amount_total']>0]
        # Non-donation/volunteer account
        df_none = account[account['amount_total'] <= 0]

        # print("df_value: ", df_value.shape)
        # print("df_none: ", df_none.shape)
        ########################### Statistics #######################
        stats = (df_value[['amount_total','non_zero_counts', 'dormancy_years']]
           .quantile([0.01, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0])
        )
        for i in ['amount_total','non_zero_counts', 'dormancy_years']:
            df_value[i+'_percentiles'] = df_value[i].rank(pct=True)
        ########################## CLASSIFICATION #######################
        # Classification group in persona & color
        logger.info('Creating Persona group...')
        df_value['persona'] = np.nan
        #Gary(Gold): high value, regular donnor, active
        df_value.loc[(df_value['dormancy_years'] <=2) & (df_value['non_zero_counts'] > 1) & (df_value['amount_total'] >=1000), 'persona'] = 'Gary'
        #Yara(Yellow): low value, regular donnor, active 
        df_value.loc[(df_value['dormancy_years'] <=2) & (df_value['non_zero_counts'] > 1) & (df_value['amount_total'] <1000), 'persona'] = 'Yara'
        #Ryan(Red): high value, young account
        df_value.loc[(df_value['dormancy_years'] <=2) & (df_value['non_zero_counts'] == 1) & (df_value['amount_total'] >=1000), 'persona'] = 'Ryan'
        #Kaura(Light Green): low value, young accounts
        df_value.loc[(df_value['dormancy_years'] <=2) & (df_value['non_zero_counts'] == 1) & (df_value['amount_total'] < 1000), 'persona'] = 'Laura'
        #Peter(Purple): high value, regular donor, dormant
        df_value.loc[(df_value['dormancy_years'] > 2) & (df_value['non_zero_counts'] > 1) & (df_value['amount_total'] >=1000), 'persona'] = 'Peter'
        #Beth(Blue): high avlue, one-time, dormant
        df_value.loc[(df_value['dormancy_years'] > 2) & (df_value['non_zero_counts'] == 1) & (df_value['amount_total'] >=1000), 'persona'] = 'Beth'
        #Olivia: low value, dormant
        df_value.loc[(df_value['dormancy_years'] > 2) & (df_value['non_zero_counts'] > 1) & (df_value['amount_total'] < 1000), 'persona'] = 'Olivia'
        #Oliver: low value, dormant
        df_value.loc[(df_value['dormancy_years'] > 2) & (df_value['non_zero_counts'] == 1) & (df_value['amount_total'] < 1000), 'persona'] = 'Oliver'

        logger.info('Creating color group...')
        #Organge: low value, dormant
        df_value['group'] = 'Orange'
        #Gold: high value, regular donnor, active
        df_value.loc[(df_value['dormancy_years'] <=2) & (df_value['non_zero_counts'] > 1) & (df_value['amount_total'] >=1000), 'group'] = 'Gold'
        #Yellow: low value, regular donnor, active 
        df_value.loc[(df_value['dormancy_years'] <=2) & (df_value['non_zero_counts'] > 1) & (df_value['amount_total'] <1000), 'group'] = 'Yellow'
        #Red: high value, young account
        df_value.loc[(df_value['dormancy_years'] <=2) & (df_value['non_zero_counts'] == 1) & (df_value['amount_total'] >=1000), 'group'] = 'Red'
        #Green: low value, young accounts
        df_value.loc[(df_value['dormancy_years'] <=2) & (df_value['non_zero_counts'] == 1) & (df_value['amount_total'] < 1000), 'group'] = 'Light Green'
        #Purple: high value, regular donor, dormant
        df_value.loc[(df_value['dormancy_years'] > 2) & (df_value['non_zero_counts'] > 1) & (df_value['amount_total'] >=1000), 'group'] = 'Purple'
        #Blue: high avlue, one-time, dormant
        df_value.loc[(df_value['dormancy_years'] > 2) & (df_value['non_zero_counts'] == 1) & (df_value['amount_total'] >=1000), 'group'] = 'Blue'

        df_mrg = acc.merge(df_value, left_on = "Id", right_on = opp_id, how = 'left')
        ################################ OUTPUT ##################################
        # Output table
        logger.info('\nOutput progressing....')

        logger.info('   Compiling output files')
        stats.to_csv(os.path.join(output_dir, f'd4g_stat_summary.csv'))
        df_value.to_csv(os.path.join(output_dir, f'd4g_value_output.csv'))
        df_none.to_csv(os.path.join(output_dir, f'd4g_potential_output.csv'))
        df_mrg.to_csv(os.path.join(output_dir, f'd4g_merge_account_output.csv'))
        state_counts.to_csv(os.path.join(output_dir, f'd4g_address_state_distibution.csv'))

        # visualizations
        logger.info('   Compiling graph pdf')
        #pdf = PdfPages(path+f"/donor_histogram_{str_current_datetime}.pdf")
        for i in ['amount_total','non_zero_counts', 'dormancy_years']:
            df_value[i].hist()
            # fig1.get_figure() 
            plt.title(i)
            plt.grid()
            plt.xlabel('value')
            plt.ylabel('Count')
            pdf.savefig()
            # plt.show()
            plt.close()
        #pdf.close()

        # address visualization
        # initialize the map and store it in a m object
        # get us map
        # us_map = geopandas.read_file(geodatasets.get_path("geoda.chicago_commpop"))
        # us_map.plot()

        
