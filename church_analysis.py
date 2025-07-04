import re
import datetime
import os

import matplotlib
import matplotlib.figure
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import pandas as pd
import logging

# Place validate_inputs here, outside the class

def validate_inputs(logger, input_dir):
    """
    Validates required input files and columns for church analysis.
    Logs status and errors to the provided logger.
    """
    logger.info("=== CHURCH ANALYSIS INPUT VALIDATION ===")
    required_files = {
        'd4g_account.csv': ['Account Record Type', 'First_Gift_Year__c', 'Id'],
        'd4g_opportunity.csv': ['Amount', 'AccountId', 'CloseDate', 'Probability'],
    }
    
    logger.info(f"Checking {len(required_files)} files for church analysis:")
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
        logger.info("All church analysis input files validated successfully.")
    return all_ok

class Church_Analysis:
    """Library of tools for conducting Church Analysis."""

    _LOWERCASE_CHURCH_INDICATORS = ["church", "temple", "religious institution"]
    _TODAY = datetime.datetime.now()
    _CHURCH_COLOR = "red"

    def process_ChurchData(self, pdf, logger, output_dir, input_dir):
        try:
            logger.debug('Reading account and opportunity tables')
            account_table= pd.read_csv(f'{input_dir}/d4g_account.csv')
            opportunity_table=pd.read_csv(f'{input_dir}/d4g_opportunity.csv')
        except:
            logger.error("Account and opportunity tables or columns missing, Can't continue Analysis!!")
            raise SystemExit("Account and opportunity tables or columns missing, Can't continue Analysis!!")

        
        # Process data
        df_account = Church_Analysis.process_account_table(account_table)
        df_opportunity_account = Church_Analysis.join_account_and_opportunity(
            df_account, opportunity_table
        )

        # Aggregate for plots
        donors_gained_by_year = Church_Analysis.get_donors_gained_per_year(df_account)
        opportunity_by_year = Church_Analysis.get_closed_donation_opportunity_by_year(
            df_opportunity_account
        )
        opportunity_by_month = Church_Analysis.get_closed_donation_opportunity_by_month(
            df_opportunity_account
        )

        # Make plot
        church_analysis_fig, church_analysis_axes = Church_Analysis.plot_church_analysis(
            donors_gained_by_year, 
            opportunity_by_year, 
            opportunity_by_month
        )
        pdf.savefig(church_analysis_fig)
        

        
    def process_account_table(df_account: pd.DataFrame) -> pd.DataFrame:
        """Preprocesses the account table for Church Analysis.

        Args:
            df_account: The Account table.

        Returns:
            A pd.DataFrame representing a processed copy of the account table.
        """
        df_account["is_church"] = df_account["Account Record Type"].str.strip().str.lower().isin(
            Church_Analysis._LOWERCASE_CHURCH_INDICATORS
        )

        # Ensure First_Gift_Year__c is numeric
        df_account['First_Gift_Year__c'] = pd.to_numeric(df_account['First_Gift_Year__c'], errors='coerce')
        df_account = df_account.dropna(subset=['First_Gift_Year__c'])
        if df_account['First_Gift_Year__c'].empty:
            logger.error('ERROR: No valid First_Gift_Year__c values after conversion.')
        df_account['First_Gift_Year__c'] = df_account['First_Gift_Year__c'].astype(int)

        df_account = df_account[["Account Record Type", "is_church", "First_Gift_Year__c", "Id"]]
        return df_account

    def join_account_and_opportunity(
        df_account: pd.DataFrame, df_opportunity: pd.DataFrame
    ) -> pd.DataFrame:
        """Joins the account and opportunity table, and does some preprocessing.

        Args:
            df_opportunity: The Opportunity table.
            df_account: The Account table.

        Returns:
            A pd.DataFrame of a processed copy of the merged tables.
        """
        # we only want closed info
        df_opportunity = df_opportunity.loc[df_opportunity.Probability == "100%"]

        # Amount is normally Currency(11, 12) = $11.12. But we want it as float
        # Check if Amount is already numeric or needs conversion
        if df_opportunity["Amount"].dtype in ['int64', 'float64']:
            # Already numeric, no conversion needed
            df_opportunity["Amount"] = df_opportunity["Amount"].astype(float)
        else:
            # Convert from currency string format
            df_opportunity["Amount"] = df_opportunity.Amount.apply(
                lambda x: float(re.sub(r"[A-Za-z\(\)\s]", "", x).replace(",", "."))
            )

        df_opportunity_account = df_opportunity.merge(
            df_account, left_on="AccountId", right_on="Id"
        )[["Amount", "Id", "CloseDate", "is_church"]]
        if df_opportunity_account['CloseDate'].head(10).empty:
            logger.error('ERROR: No valid CloseDate values after merge.')
        df_opportunity_account["CloseDate"] = pd.to_datetime(df_opportunity_account.CloseDate)
        df_opportunity_account["year"] = df_opportunity_account.CloseDate.apply(lambda d: d.year)
        df_opportunity_account["month"] = df_opportunity_account.CloseDate.apply(lambda d: d.month)

        # Drop rows with NaT in year
        df_opportunity_account = df_opportunity_account.dropna(subset=['year'])
        if len(df_opportunity_account['year'].unique()) == 0:
            logger.error('ERROR: No valid years in opportunity data after processing.')
        min_year = int(df_opportunity_account.year.min())
        max_year = int(df_opportunity_account.year.max())

        return df_opportunity_account

    def get_donors_gained_per_year(df_account: pd.DataFrame) -> dict[str, pd.DataFrame]:
        """Processes the Account table for statistics on how many donors were gained each year.

        Args:
            df_account: A processed version of the Account table.

        Returns:
            A dict containing stats for all donors, just churches, and not churches.
        """
        donors_gained_over_time = df_account.First_Gift_Year__c.value_counts().reset_index()
        churches_gained_over_time = (
            df_account.loc[df_account.is_church, "First_Gift_Year__c"].value_counts().reset_index()
        )
        not_churches_gained_over_time = (
            df_account.loc[~df_account.is_church, "First_Gift_Year__c"].value_counts().reset_index()
        )

        # Fill in missing years

        min_year = int(df_account.First_Gift_Year__c.min())
        max_year = int(df_account.First_Gift_Year__c.max())
        base = pd.DataFrame(
            data={
                "First_Gift_Year__c": range(
                    min_year, max_year + 1, 1
                )
            }
        )
        donors_gained_over_time = (
            base.merge(donors_gained_over_time, on="First_Gift_Year__c", how="outer")
            .fillna(0)
            .set_index("First_Gift_Year__c")
        )
        churches_gained_over_time = (
            base.merge(churches_gained_over_time, on="First_Gift_Year__c", how="outer")
            .fillna(0)
            .set_index("First_Gift_Year__c")
        )
        not_churches_gained_over_time = (
            base.merge(not_churches_gained_over_time, on="First_Gift_Year__c", how="outer")
            .fillna(0)
            .set_index("First_Gift_Year__c")
        )

        return {
            "total": donors_gained_over_time,
            "church": churches_gained_over_time,
            "not_church": not_churches_gained_over_time,
        }

    def get_closed_donation_opportunity_by_year(
        df_opportunity_account: pd.DataFrame,
    ) -> dict[str, pd.DataFrame]:
        """Total closed donation opportunity dollar amount per year.

        Args:
            df_opportunity_account: A merged an processed combo of Account and Opportunity tables.

        Returns:
            A dict containing stats for all donors, just churches, and not churches.
        """
        total_opportunity = (
            df_opportunity_account[["year", "Amount"]].groupby("year", as_index=False).sum()
        )
        church_opportunity = (
            df_opportunity_account.loc[df_opportunity_account.is_church, ["year", "Amount"]]
            .groupby("year", as_index=False)
            .sum()
        )
        not_church_opportunity = (
            df_opportunity_account.loc[~df_opportunity_account.is_church, ["year", "Amount"]]
            .groupby("year", as_index=False)
            .sum()
        )

        # Drop rows with NaT in year
        df_opportunity_account = df_opportunity_account.dropna(subset=['year'])
        min_year = int(df_opportunity_account.year.min())
        max_year = int(df_opportunity_account.year.max())
        base = pd.DataFrame(
            data={
                "year": range(
                    min_year, max_year + 1, 1
                )
            }
        )
        total_opportunity = (
            base.merge(total_opportunity, on="year", how="outer").fillna(0).set_index("year")
        )
        church_opportunity = (
            base.merge(church_opportunity, on="year", how="outer").fillna(0).set_index("year")
        )
        not_church_opportunity = (
            base.merge(not_church_opportunity, on="year", how="outer").fillna(0).set_index("year")
        )

        return {
            "total": total_opportunity,
            "church": church_opportunity,
            "not_church": not_church_opportunity,
        }

    def get_closed_donation_opportunity_by_month(
        df_opportunity_account: pd.DataFrame,
    ) -> dict[str, pd.DataFrame]:
        """Total closed donation opportunity by month aggregated from past 2 years.

        Args:
            df_opportunity_account: A merged an processed combo of Account and Opportunity tables.

        Returns:
            A dict containing stats for all donors, just churches, and not churches.
        """
        total_opportunity = (
            df_opportunity_account.loc[
                df_opportunity_account.year >= Church_Analysis._TODAY.year - 2, ["Amount", "month"]
            ]
            .groupby("month", as_index=False)
            .sum()
        )
        church_opportunity = (
            df_opportunity_account.loc[
                (
                    (df_opportunity_account.is_church)
                    & (df_opportunity_account.year >= Church_Analysis._TODAY.year - 2)
                ),
                ["Amount", "month"],
            ]
            .groupby("month", as_index=False)
            .sum()
        )
        not_church_opportunity = (
            df_opportunity_account.loc[
                (
                    (~df_opportunity_account.is_church)
                    & (df_opportunity_account.year >= Church_Analysis._TODAY.year - 2)
                ),
                ["Amount", "month"],
            ]
            .groupby("month", as_index=False)
            .sum()
        )

        # Fill in missing months

        base = pd.DataFrame(
            data={
                "month": range(
                    df_opportunity_account.month.min(), df_opportunity_account.month.max() + 1, 1
                )
            }
        )
        total_opportunity = (
            base.merge(total_opportunity, on="month", how="outer").fillna(0).set_index("month")
        )
        church_opportunity = (
            base.merge(church_opportunity, on="month", how="outer").fillna(0).set_index("month")
        )
        not_church_opportunity = (
            base.merge(not_church_opportunity, on="month", how="outer").fillna(0).set_index("month")
        )

        return {
            "total": total_opportunity,
            "church": church_opportunity,
            "not_church": not_church_opportunity,
        }

    def ticker_currency_formatter(x: float, _) -> str:
        """Formats floating points to plot tick labels.

        Args:
            x: float representing some dollar amount.
            _: place holder for tick label functionality.

        Returns:
            A str of the formatted currency value.
        """
        if x >= 1e9:
            return f"${x/1e9:.1f}B"
        elif x >= 1e6:
            return f"${x/1e6:.1f}M"
        elif x >= 1e3:
            return f"${x/1e3:.1f}K"
        else:
            return f"${x:.0f}"

    def ticker_month_formatter(x: int, _) -> str:
        """Converts month as a number to month as a string.

        Args:
            x: An int representing a month.
            _: place holder for tick label functionality.

        Returns:
            A string of the formatted month.
        """
        months = [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ]
        num_to_month = {num: month for num, month in enumerate(months, start=1)}

        x = int(x)

        return num_to_month[x] if x in num_to_month else ""

    def plot_church_analysis(
        donors_gained_over_time: dict[str, pd.DataFrame],
        closed_opportunity_by_year: dict[str, pd.DataFrame],
        closed_opportunity_by_month: dict[str, pd.DataFrame],
        save: bool = False,
    ) -> tuple[matplotlib.figure.Figure, plt.Axes]:
        """Plots church analysis.

        Args:
            donors_gained_over_time: # of new donors over time for church, not church, and total.
            closed_opportunity_by_year: Total closed $'s by year for church, not church, and total.
            closed_opportunity_by_month: Closed $'s by year-month for past 2 years for all groups.
            save: Optional; If True, save plot image as a png.

        Returns:
            A figure and a set of subplots. A matplotlib plot.
        """
        fig, axes = plt.subplots(3, 2, figsize=(20, 10))

        # Number of donors gained over time

        axes[0, 0].plot(donors_gained_over_time["total"], label="All Donors")
        axes[0, 0].plot(donors_gained_over_time["not_church"], label="Not Churches")
        axes[0, 0].plot(
            donors_gained_over_time["church"], label="Churches", color=Church_Analysis._CHURCH_COLOR
        )
        axes[0, 0].set_title("Number of Donors Gained Each Year")

        axes[0, 1].plot(
            donors_gained_over_time["church"], label="Churches", color=Church_Analysis._CHURCH_COLOR
        )
        axes[0, 1].set_title("Number of Church Donors Gained Each Year")

        for i in (0, 1):
            axes[0, i].set_xlabel("Years")
            axes[0, i].set_ylabel("Number of Donors")
            axes[0, i].xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
            axes[0, i].ticklabel_format(style="plain")

        # Total Closed $ by year

        axes[1, 0].plot(closed_opportunity_by_year["total"], label="All Donors")
        axes[1, 0].plot(closed_opportunity_by_year["not_church"], label="Not Churches")
        axes[1, 0].plot(
            closed_opportunity_by_year["church"],
            label="churches",
            color=Church_Analysis._CHURCH_COLOR,
        )
        axes[1, 0].set_title("Total Donation Opportunity Each Year")

        axes[1, 1].plot(
            closed_opportunity_by_year["church"],
            label="Churches",
            color=Church_Analysis._CHURCH_COLOR,
        )
        axes[1, 1].set_title("Total Church Donation Opportunity Each Year")

        for i in (0, 1):
            axes[1, i].set_xlabel("Years")
            axes[1, i].set_ylabel("Total Opportunity")
            axes[1, i].yaxis.set_major_formatter(
                ticker.FuncFormatter(Church_Analysis.ticker_currency_formatter)
            )

        # Total Closed $ by month for past 2 years, seasonality

        axes[2, 0].plot(closed_opportunity_by_month["total"], label="All Donors")
        axes[2, 0].plot(closed_opportunity_by_month["not_church"], label="Not Churches")
        axes[2, 0].plot(
            closed_opportunity_by_month["church"],
            label="Churches",
            color=Church_Analysis._CHURCH_COLOR,
        )
        axes[2, 0].set_title("Total Opportunity By Month For the Past 2 Years")

        axes[2, 1].plot(closed_opportunity_by_month["church"], color=Church_Analysis._CHURCH_COLOR)
        axes[2, 1].set_title("Total Opportunity By Month For Churches For the Past 2 Years")

        for i in (0, 1):
            axes[2, i].set_xlabel("Months")
            axes[2, i].set_ylabel("Total Opportunity")
            axes[2, i].xaxis.set_major_formatter(
                ticker.FuncFormatter(Church_Analysis.ticker_month_formatter)
            )
            axes[2, i].yaxis.set_major_formatter(
                ticker.FuncFormatter(Church_Analysis.ticker_currency_formatter)
            )

        # Format plot

        for i in (0, 1, 2):
            for j in (0, 1):
                axes[i, j].grid(True)

                if j == 0:
                    axes[i, j].legend()

        fig.tight_layout()

        # outputs

        if save:
            plt.savefig("church_analysis.png")

        return fig, axes


if __name__ == "__main__":
    #account_table = THING THAT GETS THE ACCOUNT TABLE AS A PD.DATAFRAME
    #opportunity_table = THING THAT GETS THE OPPORTUNITY TABLE AS A PD.DATAFRAME

    # Process data
    df_account = Church_Analysis.process_account_table(account_table)
    df_opportunity_account = Church_Analysis.join_account_and_opportunity(
        df_account, opportunity_table
    )

    # Aggregate for plots
    donors_gained_by_year = Church_Analysis.get_donors_gained_per_year(df_account)
    opportunity_by_year = Church_Analysis.get_closed_donation_opportunity_by_year(
        df_opportunity_account
    )
    opportunity_by_month = Church_Analysis.get_closed_donation_opportunity_by_month(
        df_opportunity_account
    )

    # Make plot
    church_analysis_fig, church_analysis_axes = Church_Analysis.plot_church_analysis(
        donors_gained_by_year, 
        opportunity_by_year, 
        opportunity_by_month
    )

    # Add the plot to the pdf
