import pandas as pd
import numpy as np
import datetime as dt
from dash_table.Format import Format, Symbol, Scheme
from dash_table import FormatTemplate


def clean_transactions(transactions_df):
    """ Expects transaction.csv DataFrame and returns a cleaned dataframe """

    # Convert Dates to datetime
    transactions_df["Date"] = transactions_df["Date"].apply(lambda x: pd.to_datetime(x, dayfirst=True)).dt.date

    # Convert Cash Amounts to floats (from strings)
    transactions_df["PL Amount"] = transactions_df["PL Amount"].apply(lambda x: float(x.replace(",","")))

    # Only retain relevant columns
    drop_columns = ["Period", "ProfitAndLoss", "Transaction type", "Reference", "Open level", "Close level", "Size", "Currency", "Cash transaction", "DateUtc", "OpenDateUtc", "CurrencyIsoCode" ]
    transactions_df.drop(drop_columns, axis=1, inplace=True)

    # Split up mega confusing "MarketName" column
    transactions_df["Conversion Rate"] = transactions_df["MarketName"].str.extract(r"((?<=Converted at\s|converted at\s)[0-9.]*)") # find converted at

    # Separate Dividend Price from "MarketName"
    transactions_df["Dividend Quantity"] = transactions_df["MarketName"].str.extract(r"([0-9.]*?(?=@))") # Look ahead, find any 0-9 or . character before the @
    transactions_df["Dividend Price"] = transactions_df["MarketName"].str.extract(r"((?<=@)[0-9.]*)") # Same as above but with Look behind

    # Separate Share Name
    transactions_df["Share Name"] = transactions_df["MarketName"].str.extract(r"^(?:Correction\s*)?(\S.*?)\s*(?:\([^()]*\)|DIVIDEND|\(All|CONS|COMM|Section)") # Uses an optional clause and capture groups

    # Section 31 Fee
    transactions_df["Summary"] = np.where(transactions_df["MarketName"].str.contains("Section 31 Fee"),
                                            "Section 31 Fee",
                                            transactions_df["Summary"])
    # Custody Fee
    transactions_df["Summary"] = np.where(transactions_df["MarketName"].str.contains("Custody Fee"),
                                            transactions_df["MarketName"],
                                            transactions_df["Summary"])
    # Cheque/Bank Deposit
    transactions_df["Summary"] = np.where(transactions_df["MarketName"].str.contains("Cheque Received|Bank Deposit"), # ISA transactions don't list Bank deposits as cash in
                                            "Cash In",
                                            transactions_df["Summary"])
    # Bonus (I have no idea what the bonus is)
    transactions_df["Summary"] = np.where(transactions_df["MarketName"].str.contains("Bonus"), # ISA transactions don't list Bank deposits as cash in
                                            "Bonus",
                                            transactions_df["Summary"])
    return transactions_df

def clean_trades(trades_df):
    """ Expects trade_history.csv DataFrame and returns a cleaned dataframe """

    # Convert Dates to datetime
    trades_df["Date"] = trades_df["Date"].apply(lambda x: pd.to_datetime(x, dayfirst=True)).dt.date # dt.date converts to date only

    # Remove "(All Sesssions)" from stock names
    trades_df["Market"] = trades_df["Market"].str.replace(" \(All Sessions\)", "")

    # Reverse tables. Ascending dates
    trades_df = trades_df[::-1]

    # Commission fees were changed from $15 to £10. Convert to £ for consistency.
    trades_df["Commission (£)"] = np.where(trades_df["Date"] < pd.Timestamp(2020, 4, 5),
                                            trades_df["Commission"] * trades_df["Conversion rate"],
                                            trades_df["Commission"])

    # Add Consideration in GBP
    trades_df["Consideration (£)"] = trades_df["Consideration"] * trades_df["Conversion rate"]

    return trades_df

# Custom Format
gbp_format = Format(precision=2, scheme=Scheme.fixed).symbol(Symbol.yes).symbol_prefix('£ ').group(True) # FormatTemplate.money(2) does $

def format_trades_columns(trades_df):
    """ Expects a trade history df and uses this to provide a column layout for Dash """
    column_layout = [{"name": i, "id": i} for i in trades_df.columns]
    column_layout[0]["type"] = "datetime"

    # Share Price
    column_layout[6]["type"] = "numeric"
    column_layout[6]["format"] = Format(precision=2, scheme=Scheme.fixed) # 2 dp, no scientific notation

    # Currency Columns
    for i in range(7,12):
        column_layout[i]["type"] = "numeric"
        column_layout[i]["format"] = gbp_format

    # Percentage format
    column_layout[12]["type"] = "numeric"
    column_layout[12]["format"] = FormatTemplate.percentage(1)

    return column_layout

def calculate_trades_summary(trades_df):
    """ Takes in the sd and isa dataframes and returns totals.
    Required as Dash app will filter dates and need to recalculate these """
    filt1 = trades_df["Net Profit (£)"].notna()

    sold_pos = round(trades_df[filt1]["Final Consideration (£)"].sum(), 2)
    fees = round(abs(trades_df[filt1]["Fees (£)"].sum()), 2)
    net_profit = round(trades_df[filt1]["Net Profit (£)"].sum(), 2)

    # %AGE CALCs
    initial_cons = trades_df[filt1]["Initial Consideration (£)"].sum()
    final_cons = trades_df[filt1]["Final Consideration (£)"].sum()
    net_profit_per = (final_cons/initial_cons - 1)*100

    return {"sold_pos": sold_pos, "fees": fees, "net_profit": net_profit, "net_profit_per": net_profit_per, "ic":initial_cons, "fc": final_cons}

def format_dividends_datatable(transactions_sd, transactions_isa):
    """ Concatenates, sorts and cleans transaction history to display dividends """

    filt1 = transactions_sd["Summary"] == "Dividend"
    filt2 = transactions_isa["Summary"] == "Dividend"
    transactions_sd["Account"] = "Share Dealing"
    transactions_isa["Account"] = "ISA"

    dividends_df = pd.concat([transactions_sd[filt1], transactions_isa[filt2]])
    dividends_df.sort_values(by=['Date'], inplace=True, ascending=True)
    dividends_df = dividends_df[["Date", "Account", "Share Name", "Dividend Quantity", "Dividend Price", "Conversion Rate", "PL Amount"]]

    column_layout = [{"name": i, "id": i} for i in dividends_df.columns]
    column_layout[6]["type"] = "numeric"
    column_layout[6]["format"] = gbp_format

    return {"df": dividends_df, "column_layout": column_layout}

def calculate_dividends_summary(dividends_df):
    """ Takes in a dividends dataframe and returns totals.
    Required as Dash app will filter dates and need to recalculate these """

    filt3 = dividends_df["Account"] == "Share Dealing"
    filt4 = dividends_df["Account"] == "ISA"
    sd_total = round(dividends_df[filt3]["PL Amount"].sum(), 2)
    isa_total = round(dividends_df[filt4]["PL Amount"].sum(), 2)

    return {"sd_total": sd_total, "isa_total": isa_total}

def format_fees_datatable(transactions_sd, transactions_isa):
    """ Concatenates, sorts and cleans transaction history to display dividends """

    filt1 = transactions_sd["Summary"].str.contains("Share Dealing Commissions|Section 31 Fee|Custody Fee")
    filt2 = transactions_isa["Summary"].str.contains("Share Dealing Commissions|Section 31 Fee|Custody Fee")
    transactions_sd["Account"] = "Share Dealing"
    transactions_isa["Account"] = "ISA"

    fees_df = pd.concat([transactions_sd[filt1], transactions_isa[filt2]])
    fees_df.sort_values(by=['Date'], inplace=True, ascending=True)
    fees_df = fees_df[["Date", "Account", "Summary", "Share Name", "PL Amount"]]

    column_layout = [{"name": i, "id": i} for i in fees_df.columns]
    column_layout[4]["type"] = "numeric"
    column_layout[4]["format"] = gbp_format  

    return {"df": fees_df, "column_layout": column_layout}

def calculate_fees_summary(fees_df):
    """ Takes in a fees dataframe and returns totals.
    Required as Dash app will filter dates and need to recalculate these """
    filt3 = fees_df["Summary"].str.contains("Section 31 Fee")
    filt4 = fees_df["Summary"].str.contains("Custody Fee")
    filt5 = fees_df["Summary"].str.contains("Share Dealing Commissions")
    
    section_31 = round(abs(fees_df[filt3]["PL Amount"].sum()), 2)
    custody = round(abs(fees_df[filt4]["PL Amount"].sum()), 2)
    commission = round(abs(fees_df[filt5]["PL Amount"].sum()), 2)

    return {"section_31": section_31, "custody": custody, "commission": commission}

def trade_history_report(trade_history):
    """ Takes in a trade history.csv DataFrame and adds details such as profit on closed positions 
    Returns only relevant columns in a new dataframe """
    
    share_names = trade_history["Market"].unique()
    
    for share_name in share_names: # loop through all the different shares
        filt = trade_history["Market"] == share_name
        positions = []
        
        for idx, row in trade_history[filt].iterrows():
            
            # Handle Share Splits
            if row["Activity"] == "CORPORATE ACTION": # Share split
                if row["Direction"] == "SELL":
                    share_split = abs(row["Quantity"])
                else:
                    share_split = abs(row["Quantity"]) / share_split
                    # Multiply all existing position share quantities by the split
                    for position in positions:
                        if position["qty"] != 0: # Don't adjust previously closed positions
                            position["qty"] *= share_split
                            position["price"] /= share_split
                continue

            # Add each Buy (new position) to a dictionary
            if row["Direction"] == "BUY":
                positions.append({"qty": row["Quantity"], "price": row["Price"], "fees": abs(row["Commission (£)"] + row["Charges"])})
            
            # When shares are sold, calculate profit using Positions list
            # This takes into account uneven buy/sell quantities using a FIFO model
            else: # Direction == SELL
                # Track these
                initial_consideration = 0 # running total
                fees = abs(row["Commission (£)"] + row["Charges"]) # we will add any fees of fully closed positions
                sell_qty = abs(row["Quantity"]) # Shares to sell. Will be adjusted as we sell off positions
                final_consideration = sell_qty * row["Price"]

                # We iterate through previous buy positions, selling those off first
                for position in positions:
                    if position["qty"] == 0: # we've already sold this position
                        continue
                        
                    elif sell_qty >= position["qty"]: # we can sell this position, and may need to continue on afterwards
                        initial_consideration += position["qty"] * position["price"]
                        fees += position["fees"] # associate the commission fees from Buy trade with this sell when calculating profit

                        # Adjust no. of shares
                        sell_qty -= position["qty"]
                        position["qty"] = 0
                        
                    else: # we are not selling enough shares to close this position.
                        initial_consideration += sell_qty * position["price"]
                        
                        # Adjust no. of shares
                        position["qty"] -= sell_qty # subtract shares from position
                        sell_qty = 0 

                    if sell_qty == 0:
                        trade_history.loc[idx, "Initial Consideration (£)"] = round(initial_consideration, 2)
                        trade_history.loc[idx, "Final Consideration (£)"] = round(final_consideration, 2)
                        trade_history.loc[idx, "Gross Profit (£)"] = round(final_consideration - initial_consideration, 2)
                        trade_history.loc[idx, "Fees (£)"] = round(fees, 2)
                        trade_history.loc[idx, "Net Profit (£)"] = round(final_consideration - initial_consideration - fees, 2)
                        trade_history.loc[idx, "Net Profit (%)"] = round(((final_consideration-fees)/initial_consideration)-1, 2)
                        #print(f"Initial Consideration: £{initial_investment:.2f}\nFinal Consideration: £{initial_investment+profit:.2f}\nGross Profit: £{profit:.2f}\nFees: £{fees:.2f}\nNet Profit: £{profit-fees:.2f}\nNet Profit(%): {100*((initial_investment+profit)/initial_investment) - 100:.2f}\n")
                        break
                        
    # Return only columns we want to see
    return trade_history[["Date", "Time",
                            "Market", "Activity", "Direction",
                            "Quantity", "Price",
                            "Consideration (£)",
                            "Initial Consideration (£)", "Final Consideration (£)",
                            #"Gross Profit (£)",
                            "Fees (£)", "Net Profit (£)", "Net Profit (%)"]]

def date_filter(start_date, end_date, table):
    # Convert str dates to datetime
    date1 = dt.datetime.strptime(start_date, "%Y-%m-%d").date()
    date2 = dt.datetime.strptime(end_date, "%Y-%m-%d").date()

    filt1 = table["Date"] > date1
    filt2 = table["Date"] < date2
    return table[filt1 & filt2]

if __name__ == "__main__":
    pass