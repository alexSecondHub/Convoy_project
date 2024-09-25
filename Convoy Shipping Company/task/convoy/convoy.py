import pandas as pd
import sqlite3
import json
import re
import os


# Functions
def get_file_name_from_user():
    while True:
        file_name = input('Input file name\n')
        if re.search(r'\.xlsx$', file_name):
            return re.sub(r'\.xlsx$', '', file_name), '.xlsx'
        elif re.search(r'\.csv$', file_name):
            return re.sub(r'\.csv$', '', file_name), '.csv'
        elif re.search(r'\.s3db$', file_name):
            return re.sub(r'\.s3db$', '', file_name), '.s3db'
        else:
            print('Wrong file name!')


def prepare_csv_from_xlsx(convoy_df, file_name):
    convoy_df.to_csv(path_or_buf=file_name + '.csv', index=False)
    rows, columns = convoy_df.shape
    if rows == 1:
        print('{} line was imported to {}'.format(rows, file_name + '.csv'))
    else:
        print('{} lines were imported to {}'.format(rows, file_name + '.csv'))


def prepare_checked_csv(convoy_df, file_name):
    corrected_cells = 0
    for column in convoy_df:
        for row_index in range(convoy_df[column].size):
            if re.search(r'[^0-9]+', convoy_df[column][row_index]):
                convoy_df.loc[row_index, column] = ''.join(re.findall(r'\d+', convoy_df[column][row_index]))
                corrected_cells += 1

    file_name_output_corrected = file_name + '[CHECKED]' + '.csv'
    convoy_df.to_csv(path_or_buf=file_name_output_corrected, index=False)

    if corrected_cells == 1:
        print('{} cell was corrected in {}'.format(corrected_cells, file_name_output_corrected))
    else:
        print('{} cells were corrected in {}'.format(corrected_cells, file_name_output_corrected))

    return convoy_df


def prepare_create_table_sql(convoy_df):
    sql_query_create_table = 'CREATE TABLE convoy ('
    for column in convoy_df:
        if column == 'vehicle_id':
            sql_query_create_table += column + ' INTEGER PRIMARY KEY'
        else:
            sql_query_create_table += column + ' INTEGER NOT NULL'

        if column == convoy_df.columns[-1]:
            sql_query_create_table += ');'
        else:
            sql_query_create_table += ', '

    return sql_query_create_table


def prepare_start_insert_sql(convoy_df):
    sql_query_start_add_row = 'INSERT INTO convoy('
    for column in convoy_df:
        sql_query_start_add_row += column

        if column == convoy_df.columns[-1]:
            sql_query_start_add_row += ') VALUES('
        else:
            sql_query_start_add_row += ', '

    return sql_query_start_add_row


def prepare_full_insert_table_sql(convoy_df, row_index):
    sql_query_add_row = prepare_start_insert_sql(convoy_df)
    for column in convoy_df:
        sql_query_add_row += str(convoy_df[column][row_index])
        if column == convoy_df.columns[-1]:
            sql_query_add_row += ');'
        else:
            sql_query_add_row += ', '

    return sql_query_add_row


def delete_db_file(file_name):
    if os.path.exists(file_name):
        os.remove(file_name)


def create_db_content(convoy_df, db_conn, file_name):
    try:
        db_cursor_name = db_conn.cursor()
        db_cursor_name.execute(prepare_create_table_sql(convoy_df))

        rows, columns = convoy_df.shape
        for row_index in range(rows):
            db_cursor_name.execute(prepare_full_insert_table_sql(convoy_df, row_index))

        if rows == 1:
            print('{} record was inserted in {}'.format(rows, file_name + '.s3db'))
        else:
            print('{} records were inserted in {}'.format(rows, file_name + '.s3db'))

        db_conn.commit()
    except Exception as db_exception:
        print('Something went wrong: ', db_exception)


def create_json(convoy_df, file_name):
    rows, columns = convoy_df.shape
    rows_as_dicts = convoy_df.to_dict(orient='records')
    json_dict = {'convoy': rows_as_dicts}

    with open(file_name + '.json', 'w') as json_file:
        json.dump(json_dict, json_file, indent=4)

    print_action_vehicles_save(file_name + '.json', rows)


def create_xml(convoy_df, file_name):
    rows, columns = convoy_df.shape
    if rows > 0:
        convoy_df.to_xml(path_or_buffer=file_name + '.xml',
                         root_name='convoy', row_name='vehicle',
                         index=False, xml_declaration=False)
    else:
        with open(file_name + '.xml', 'w') as xml_file:
            xml_file.write('<convoy></convoy>')
    print_action_vehicles_save(file_name + '.xml', rows)


def print_action_vehicles_save(file_name_full, number_of_rows):
    if number_of_rows == 1:
        print('{} vehicle was saved into {}'.format(number_of_rows, file_name_full))
    else:
        print('{} vehicles were saved into {}'.format(number_of_rows, file_name_full))


def add_score(convoy_df):
    rows, columns = convoy_df.shape
    scores = list()
    for row_index in range(rows):
        score_temp = 0
        if int(convoy_df['maximum_load'][row_index]) >= 20:
            score_temp += 2

        litres_per_trip = 4.5 * int(convoy_df['fuel_consumption'][row_index])
        if litres_per_trip <= 230:
            score_temp += 2
        else:
            score_temp += 1

        if litres_per_trip / int(convoy_df['engine_capacity'][row_index]) < 1:
            score_temp += 2
        elif litres_per_trip / int(convoy_df['engine_capacity'][row_index]) < 2:
            score_temp += 1

        scores.append(score_temp)

    convoy_df.insert(columns, 'score', scores)
    return convoy_df


def sort_data_up(convoy_df):
    rows, columns = convoy_df.shape
    for row_index in range(rows):
        if int(convoy_df['score'][row_index]) <= 3:
            convoy_df = convoy_df.drop(row_index)
    convoy_df = convoy_df.drop('score', axis=1)
    return convoy_df


def sort_data_down(convoy_df):
    rows, columns = convoy_df.shape
    for row_index in range(rows):
        if int(convoy_df['score'][row_index]) > 3:
            convoy_df = convoy_df.drop(row_index)
    convoy_df = convoy_df.drop('score', axis=1)
    #print(convoy_df)
    return convoy_df

# Main
def main():
    file_name, file_format = get_file_name_from_user()
    convoy_df = pd.DataFrame()

    if file_format == '.xlsx':
        convoy_df = pd.read_excel(io=file_name + file_format, sheet_name='Vehicles', dtype=str)
    elif file_format == '.csv':
        convoy_df = pd.read_csv(filepath_or_buffer=file_name + file_format, dtype=str)

    # Convert excel

    if file_format == '.xlsx':
        prepare_csv_from_xlsx(convoy_df, file_name)

    # Clean up cells

    if not re.search(r'\[CHECKED]', file_name) and file_format != '.s3db':
        convoy_df = prepare_checked_csv(convoy_df, file_name)
    else:
        file_name = re.sub(r'\[CHECKED]', '', file_name)

    # Create SQL database

    if file_format != '.s3db':
        delete_db_file(file_name + '.s3db')

    db_conn = sqlite3.connect(file_name + '.s3db')

    if file_format == '.s3db':
        convoy_df = pd.read_sql_query('SELECT * FROM convoy', db_conn)
    else:
        convoy_df = add_score(convoy_df)
        create_db_content(convoy_df, db_conn, file_name)

    db_conn.close()

    # Filter
    convoy_df_json = sort_data_up(convoy_df)
    convoy_df_xml = sort_data_down(convoy_df)

    # Create JSON

    create_json(convoy_df_json, file_name)

    # Create XML

    create_xml(convoy_df_xml, file_name)


# Body
main()
