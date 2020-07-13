import os
import pandas as pd
import random

from os.path import join

from config import *

# NOTE: deprecated
def write_all_classes_to_text_file_from_translation_excel_file(op_dir='./data'):

    op_fn = join(op_dir, 'disease_names.txt')

    labels = set()
    xls = pd.ExcelFile(TRANSLATION_EXCEL_FN)
    sheet_names = ['danderm', 'derm-atlas', 'derm101', 'dermSI', 'dermnet', 'derm-zh']

    # grab all English labels
    for sheet in sheet_names:
        df = pd.read_excel(xls, sheet)
        eng_lbls = df['英文'].tolist()
        print('for sheet={}, before: ', len(labels))
        labels = labels.union(set(eng_lbls))
        print('after: ', len(labels))

    # write to a text file
    with open(op_fn, 'w', encoding='utf-8') as fwrite:
        for item in labels:
            fwrite.write(str(item) + '\n')
    fwrite.close()
    print('Finish writing!')

def write_all_classes_to_text_file_from_new_excel_file(op_dir='./data'):

    op_fn = join(op_dir, 'disease_names.txt')

    df = pd.read_excel(DIAGNOSIS_NAMES_EXCEL_FN)
    labels = set(df['英文'].tolist())

    print('total number of labels: {}'.format(len(labels)))

    with open(op_fn, 'w', encoding='utf-8') as fwrite:
        for item in labels:
            fwrite.write(str(item) + '\n')
    fwrite.close()
    print('Finish writing!')

def load_all_classes_names(fn='./data/disease_names.txt'):
    '''
        Args:

        Returns:
            res (list[str])
    '''
    if not os.path.exists(fn):
        raise FileNotFoundError(f'Missing file={fn}!')

    file_opener = open(fn,'r', encoding='utf-8')
    res = file_opener.readlines()
    # strip the very last newline character
    res = [x[:-1] for x in res]
    # remove 'nan'
    return list(filter(lambda x: x != 'nan', res))

def get_login_credential():

    index = random.randint(0, len(CREDENTIALS)-1)

    return CREDENTIALS[index]

def fix_str_for_directory(your_str):
    '''Strips away invalid characters that are not allowed in directory naming conventions.

    Args:
        your_str (str):
    '''
    res = your_str
    chars2strip = [':', '/']

    for char in chars2strip:
        res = res.replace(char, '')

    return res


if __name__ == '__main__':

    pass

    write_all_classes_to_text_file_from_new_excel_file()