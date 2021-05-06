import dash
import dash_core_components as dcc
import dash_html_components as html
from dash_table import DataTable

import pandas as pd
from datetime import date, timedelta
import json

import process_data

# Files
trades_sd_raw = pd.read_csv("./TradeHistory (Share Dealing).csv")
trades_isa_raw = pd.read_csv("./TradeHistory (ISA).csv")
transactions_sd_raw = pd.read_csv("./TransactionHistory (Share Dealing).csv")
transactions_isa_raw = pd.read_csv("./TransactionHistory (ISA).csv")

# Tidy up raw data
trades_sd = process_data.clean_trades(trades_sd_raw)
trades_isa = process_data.clean_trades(trades_isa_raw)
transactions_sd = process_data.clean_transactions(transactions_sd_raw)
transactions_isa = process_data.clean_transactions(transactions_isa_raw)

# Process trades and generate profit per position etc.
trades_sd = process_data.trade_history_report(trades_sd)
trades_isa = process_data.trade_history_report(trades_isa)

# Process relevant Tables
trades_column_layout = process_data.format_trades_columns(trades_sd) # we can pass either sd or isa here, same layout.
dividends = process_data.format_dividends_datatable(transactions_sd, transactions_isa)
fees = process_data.format_fees_datatable(transactions_sd, transactions_isa)

# Get current tax year
this_year = date.today().year
if date.today() >= date(this_year, 4, 6):
    previous_tax_year = [date(this_year-1, 4, 6), date(this_year, 4, 5)]
else:
    previous_tax_year = [date(this_year-2, 4, 6), date(this_year-1, 4, 5)]

# Filter all dataframes by the Date.
date_filters = [
    trades_sd["Date"] >= previous_tax_year[0],
    trades_sd["Date"] < previous_tax_year[1] + timedelta(days=1), # we want our date selector to include final day
    trades_isa["Date"] >= previous_tax_year[0],
    trades_isa["Date"] < previous_tax_year[1] + timedelta(days=1),
    dividends["df"]["Date"] >= previous_tax_year[0],
    dividends["df"]["Date"] < previous_tax_year[1] + timedelta(days=1),
    fees["df"]["Date"] >= previous_tax_year[0],
    fees["df"]["Date"] < previous_tax_year[1] + timedelta(days=1),
]

# Calculate totals - will need to be recalculated when using date range picker
sd_trades_summary = process_data.calculate_trades_summary(trades_sd[date_filters[0] & date_filters[1]])
isa_trades_summary = process_data.calculate_trades_summary(trades_isa[date_filters[2] & date_filters[3]])
dividends_summary = process_data.calculate_dividends_summary(dividends["df"][date_filters[4] & date_filters[5]])
fees_summary = process_data.calculate_fees_summary(fees["df"][date_filters[6] & date_filters[7]])

# Calculate %age profit
initial_cons = sd_trades_summary["ic"] + isa_trades_summary["ic"]
final_cons = sd_trades_summary["fc"] + isa_trades_summary["fc"]
net_profit_per = (final_cons/initial_cons - 1)*100

app = dash.Dash(__name__)

app.layout = html.Div([
                html.Div([
                    html.H1("Date Range"),
                    dcc.DatePickerRange(
                        id='date-picker-range',
                        min_date_allowed=date(2018, 1, 1),
                        max_date_allowed=date.today() + timedelta(days=1), # we want til the end of today
                        initial_visible_month=date.today(),
                        start_date=previous_tax_year[0],
                        end_date=previous_tax_year[1],
                        display_format='DD/MM/YYYY',
                    ),
                ], className="partition"),
                html.Div([
                    html.H1("Positions"),
                    html.H2("Share Dealing"),
                    DataTable(
                        id='sd-positions-table',
                        columns=trades_column_layout,
                        data=trades_sd[date_filters[0] & date_filters[1]].to_dict('records'), # "records" specifies a structure of [{column1: row1 value, column2, row2 value} {column1, row2 value...}]
                        filter_action="native", # add filters
                        sort_action="native", # column header sort buttons
                        style_cell={
                            "whiteSpace":"normal",
                            "height":"auto" # word wrap
                            },
                    ),
                    html.H2("Stocks & Shares ISA"),
                    DataTable(
                        id='isa-positions-table',
                        columns=trades_column_layout,
                        data=trades_isa[date_filters[2] & date_filters[3]].to_dict('records'), # "records" specifies a structure of [{column1: row1 value, column2, row2 value} {column1, row2 value...}]
                        filter_action="native", # add filters
                        sort_action="native", # column header sort buttons
                        style_cell={
                            "whiteSpace":"normal",
                            "height":"auto"
                            },
                    ),
                    html.H3("Summary of Closed Positions"),
                        html.Table([
                            html.Tr([
                                html.Th(),
                                html.Th("Share Dealing"),
                                html.Th("ISA"),
                                html.Th("Total"),
                            ]),
                            html.Tr([
                                html.Td("Initially Invested"),
                                html.Td(f'£ {sd_trades_summary["ic"]:,.2f}', id="sd-positions-invested"),
                                html.Td(f'£ {isa_trades_summary["ic"]:,.2f}', id="isa-positions-invested"),
                                html.Td(f'£ {(sd_trades_summary["ic"]+isa_trades_summary["ic"]):,.2f}', id="trades-total-invested"),
                            ]),
                            html.Tr([
                                html.Td("Total Sold"),
                                html.Td(f'£ {sd_trades_summary["sold_pos"]:,.2f}', id="sd-positions-sold"),
                                html.Td(f'£ {isa_trades_summary["sold_pos"]:,.2f}', id="isa-positions-sold"),
                                html.Td(f'£ {(sd_trades_summary["sold_pos"]+isa_trades_summary["sold_pos"]):,.2f}', id="trades-total-sold"),
                            ]),
                            html.Tr([
                                html.Td("Fees Associated"),
                                html.Td(f'£ {sd_trades_summary["fees"]:,.2f}', id="sd-fees"),
                                html.Td(f'£ {isa_trades_summary["fees"]:,.2f}', id="isa-fees"),
                                html.Td(f'£ {(sd_trades_summary["fees"]+isa_trades_summary["sold_pos"]):,.2f}', id="trades-total-fees"),
                            ]),
                            html.Tr([
                                html.Td("Net Profit"),
                                html.Td(f'£ {sd_trades_summary["net_profit"]:,.2f}', id="sd-net-profit"),
                                html.Td(f'£ {isa_trades_summary["net_profit"]:,.2f}', id="isa-net-profit"),
                                html.Td(f'£ {(sd_trades_summary["net_profit"]+isa_trades_summary["net_profit"]):,.2f}', id="trades-net-profit"),
                            ]),
                            html.Tr([
                                html.Td("Net Profit (%)"),
                                html.Td(f'{sd_trades_summary["net_profit_per"]:,.2f}%', id="sd-net-per"),
                                html.Td(f'{isa_trades_summary["net_profit_per"]:,.2f}%', id="isa-net-per"),
                                html.Td(f'{net_profit_per:,.2f}%', id="trades-net-per"),
                            ]),
                    ], className="table"),
                
                ], className="partition"),
                html.Div([
                    html.H1("Dividends"),
                    DataTable(
                        id="dividends-table",
                        columns=dividends["column_layout"],
                        data=dividends["df"][date_filters[4] & date_filters[5]].to_dict("records"),
                        filter_action="native", # add filters
                        sort_action="native", # column header sort buttons
                        style_cell={
                            "whiteSpace":"normal",
                            "height":"auto"
                            },
                    ),
                    html.H3("Dividends Summary"),
                    html.Table([
                        #html.Th(["", "Total"]),
                        html.Tr([
                            html.Td("Share Dealing"),
                            html.Td(f'£ {dividends_summary["sd_total"]:,.2f}', id="dividends-sd-total"),
                        ]),
                        html.Tr([
                            html.Td("ISA"),
                            html.Td(f'£ {dividends_summary["isa_total"]:,.2f}', id="dividends-isa-total"),
                        ]),
                        html.Tr([
                            html.Td("Total"),
                            html.Td(f'£ {(dividends_summary["sd_total"] + dividends_summary["isa_total"]):,.2f}', id="dividends-total"),
                        ]),
                    ], className="table"),
                ], className="partition"),
                html.Div([
                    html.H1("Fees"),
                    DataTable(
                        id="fees-table",
                        columns=fees["column_layout"],
                        data=fees["df"][date_filters[6] & date_filters[7]].to_dict("records"),
                        filter_action="native", # add filters
                        sort_action="native", # column header sort buttons
                        style_cell={
                            "whiteSpace":"normal",
                            "height":"auto"
                            },
                    ),
                    html.H3("Fees Summary"),
                    html.Table([
                        html.Tr([
                            html.Td("Commission Fees"),
                            html.Td(f'£ {fees_summary["commission"]:,.2f}', id="commission-fees"),
                        ]),
                        html.Tr([
                            html.Td("Section 31 Fees"),
                            html.Td(f'£ {fees_summary["section_31"]:,.2f}', id="section31-fees"),
                        ]),
                        html.Tr([
                            html.Td("Custody Fees"),
                            html.Td(f'£ {fees_summary["custody"]:,.2f}', id="custody-fees"),
                        ]),
                        html.Tr([
                            html.Td("Total"),
                            html.Td(f'£ {(fees_summary["commission"]+fees_summary["section_31"]+fees_summary["custody"]):,.2f}', id="total-fees"),
                        ]),
                    ], className="table"),
                ], className="partition"),
                dcc.Store(id='trades-summary-data'), # we use this to store values for summary tables
                dcc.Store(id='summary-data'),

], style={"margin":"auto", "width":"100%", "max-width":"1200px", "min-width":"900px"})


# Share Dealing Table
@app.callback(
    dash.dependencies.Output('sd-positions-table', 'data'),
    [dash.dependencies.Input('date-picker-range', 'start_date'),
     dash.dependencies.Input('date-picker-range', 'end_date')])
def update_sd_table(start_date, end_date):
    new_df = process_data.date_filter(start_date, end_date, trades_sd)
    return new_df.to_dict('records')

# ISA Table
@app.callback(
    dash.dependencies.Output('isa-positions-table', 'data'),
    [dash.dependencies.Input('date-picker-range', 'start_date'),
     dash.dependencies.Input('date-picker-range', 'end_date')])
def update_isa_table(start_date, end_date):
    new_df = process_data.date_filter(start_date, end_date, trades_isa)
    return new_df.to_dict('records')

# Dividends Table
@app.callback(
    dash.dependencies.Output('dividends-table', 'data'),
    [dash.dependencies.Input('date-picker-range', 'start_date'),
     dash.dependencies.Input('date-picker-range', 'end_date')])
def update_dividends_table(start_date, end_date):
    new_df = process_data.date_filter(start_date, end_date, dividends["df"])
    return new_df.to_dict('records')

# Fees Table
@app.callback(
    dash.dependencies.Output('fees-table', 'data'),
    [dash.dependencies.Input('date-picker-range', 'start_date'),
     dash.dependencies.Input('date-picker-range', 'end_date')])
def update_fees_table(start_date, end_date):
    new_df = process_data.date_filter(start_date, end_date, fees["df"])
    return new_df.to_dict('records')

# Update Summary HTML tables
# This is achieved by first updating the Dataframes, getting the relevant data and storing it as JSON in a Dash data object

# Trades HTML tables
@app.callback(
    dash.dependencies.Output('trades-summary-data', 'data'), # we first update a hidden data cell
    [dash.dependencies.Input('date-picker-range', 'start_date'),
     dash.dependencies.Input('date-picker-range', 'end_date')])
def update_trades_summary(start_date, end_date):
    sd_df = process_data.date_filter(start_date, end_date, trades_sd)
    isa_df = process_data.date_filter(start_date, end_date, trades_isa)
    sd_summary = process_data.calculate_trades_summary(sd_df)
    isa_summary = process_data.calculate_trades_summary(isa_df)

    data = {"sd": sd_summary, "isa": isa_summary}
    return json.dumps(data)

@app.callback(
    dash.dependencies.Output('sd-positions-invested', 'children'),
    [dash.dependencies.Input('trades-summary-data', 'data')])
def update_trades_1(data):
    summary_data = json.loads(data)
    return f'£ {summary_data["sd"]["ic"]:,.2f}'

@app.callback(
    dash.dependencies.Output('isa-positions-invested', 'children'),
    [dash.dependencies.Input('trades-summary-data', 'data')])
def update_trades_2(data):
    summary_data = json.loads(data)
    return f'£ {summary_data["isa"]["ic"]:,.2f}'

@app.callback(
    dash.dependencies.Output('trades-total-invested', 'children'),
    [dash.dependencies.Input('trades-summary-data', 'data')])
def update_trades_3(data):
    summary_data = json.loads(data)
    return f'£ {(summary_data["sd"]["ic"] + summary_data["isa"]["ic"]):,.2f}'

@app.callback(
    dash.dependencies.Output('sd-positions-sold', 'children'),
    [dash.dependencies.Input('trades-summary-data', 'data')])
def update_trades_1(data):
    summary_data = json.loads(data)
    return f'£ {summary_data["sd"]["sold_pos"]:,.2f}'

@app.callback(
    dash.dependencies.Output('isa-positions-sold', 'children'),
    [dash.dependencies.Input('trades-summary-data', 'data')])
def update_trades_2(data):
    summary_data = json.loads(data)
    return f'£ {summary_data["isa"]["sold_pos"]:,.2f}'

@app.callback(
    dash.dependencies.Output('trades-total-sold', 'children'),
    [dash.dependencies.Input('trades-summary-data', 'data')])
def update_trades_3(data):
    summary_data = json.loads(data)
    return f'£ {(summary_data["sd"]["sold_pos"] + summary_data["isa"]["sold_pos"]):,.2f}'

@app.callback(
    dash.dependencies.Output('sd-fees', 'children'),
    [dash.dependencies.Input('trades-summary-data', 'data')])
def update_trades_4(data):
    summary_data = json.loads(data)
    return f'£ {summary_data["sd"]["fees"]:,.2f}'

@app.callback(
    dash.dependencies.Output('isa-fees', 'children'),
    [dash.dependencies.Input('trades-summary-data', 'data')])
def update_trades_5(data):
    summary_data = json.loads(data)
    return f'£ {summary_data["isa"]["fees"]:,.2f}'

@app.callback(
    dash.dependencies.Output('trades-total-fees', 'children'),
    [dash.dependencies.Input('trades-summary-data', 'data')])
def update_trades_6(data):
    summary_data = json.loads(data)
    return f'£ {(summary_data["sd"]["fees"] + summary_data["isa"]["fees"]):,.2f}'

@app.callback(
    dash.dependencies.Output('sd-net-profit', 'children'),
    [dash.dependencies.Input('trades-summary-data', 'data')])
def update_trades_7(data):
    summary_data = json.loads(data)
    return f'£ {summary_data["sd"]["net_profit"]:,.2f}'

@app.callback(
    dash.dependencies.Output('isa-net-profit', 'children'),
    [dash.dependencies.Input('trades-summary-data', 'data')])
def update_trades_8(data):
    summary_data = json.loads(data)
    return f'£ {summary_data["isa"]["net_profit"]:,.2f}'

@app.callback(
    dash.dependencies.Output('trades-net-profit', 'children'),
    [dash.dependencies.Input('trades-summary-data', 'data')])
def update_trades_9(data):
    summary_data = json.loads(data)
    return f'£ {(summary_data["sd"]["net_profit"] + summary_data["isa"]["net_profit"]):,.2f}'

@app.callback(
    dash.dependencies.Output('sd-net-per', 'children'),
    [dash.dependencies.Input('trades-summary-data', 'data')])
def update_trades_10(data):
    summary_data = json.loads(data)
    return f'{summary_data["sd"]["net_profit_per"]:,.2f} %'

@app.callback(
    dash.dependencies.Output('isa-net-per', 'children'),
    [dash.dependencies.Input('trades-summary-data', 'data')])
def update_trades_11(data):
    summary_data = json.loads(data)
    return f'{summary_data["isa"]["net_profit_per"]:,.2f} %'

@app.callback(
    dash.dependencies.Output('trades-net-per', 'children'),
    [dash.dependencies.Input('trades-summary-data', 'data')])
def update_trades_12(data):
    summary_data = json.loads(data)

    initial_cons = summary_data["sd"]["ic"] + summary_data["isa"]["ic"]
    final_cons = summary_data["sd"]["fc"] + summary_data["isa"]["fc"]
    try:
        net_profit_per = (final_cons/initial_cons - 1)*100
        return f'{net_profit_per:,.2f} %'
    except ZeroDivisionError:
        return 'N/A'


# Fees and Dividends HTML tables
@app.callback(
    dash.dependencies.Output('summary-data', 'data'), # we first update a hidden data cell
    [dash.dependencies.Input('date-picker-range', 'start_date'),
     dash.dependencies.Input('date-picker-range', 'end_date')])
def update_summary(start_date, end_date):
    new_df1 = process_data.date_filter(start_date, end_date, dividends["df"])
    new_df2 = process_data.date_filter(start_date, end_date, fees["df"])
    dividends_summary = process_data.calculate_dividends_summary(new_df1)
    fees_summary = process_data.calculate_fees_summary(new_df2)

    data = {"sd_total": dividends_summary["sd_total"], "isa_total": dividends_summary["isa_total"],
    "section_31": fees_summary["section_31"], "custody": fees_summary["custody"], "commission": fees_summary["commission"]}

    return json.dumps(data)

@app.callback(
    dash.dependencies.Output('dividends-sd-total', 'children'),
    [dash.dependencies.Input('summary-data', 'data')])
def update_dividends1(data):
    summary_data = json.loads(data)
    return f'£ {summary_data["sd_total"]:,.2f}'

@app.callback(
    dash.dependencies.Output('dividends-isa-total', 'children'),
    [dash.dependencies.Input('summary-data', 'data')])
def update_dividends2(data):
    summary_data = json.loads(data)
    return f'£ {summary_data["isa_total"]:,.2f}'

@app.callback(
    dash.dependencies.Output('dividends-total', 'children'),
    [dash.dependencies.Input('summary-data', 'data')])
def update_dividends3(data):
    summary_data = json.loads(data)
    return f'£ {(summary_data["sd_total"] + summary_data["isa_total"]):,.2f}'

@app.callback(
    dash.dependencies.Output('commission-fees', 'children'),
    [dash.dependencies.Input('summary-data', 'data')])
def update_fees1(data):
    summary_data = json.loads(data)
    return f'£ {summary_data["commission"]:,.2f}'

@app.callback(
    dash.dependencies.Output('section31-fees', 'children'),
    [dash.dependencies.Input('summary-data', 'data')])
def update_fees2(data):
    summary_data = json.loads(data)
    return f'£ {summary_data["section_31"]:,.2f}'

@app.callback(
    dash.dependencies.Output('custody-fees', 'children'),
    [dash.dependencies.Input('summary-data', 'data')])
def update_fees3(data):
    summary_data = json.loads(data)
    return f'£ {summary_data["custody"]:,.2f}'

@app.callback(
    dash.dependencies.Output('total-fees', 'children'),
    [dash.dependencies.Input('summary-data', 'data')])
def update_fees4(data):
    summary_data = json.loads(data)
    return f'£ {(summary_data["custody"] + summary_data["section_31"] + summary_data["commission"]):,.2f}'


if __name__ == "__main__":
    app.run_server()



