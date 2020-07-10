import os
#import pandas as pd

from os.path import join

from config import *


def write_all_classes_to_text_file(op_dir='./data'):

    op_fn = join(op_dir, 'disease_names.txt')

    labels = set()
    xls = pd.ExcelFile(TRANSLATION_CSV_FN)
    sheet_names = ['danderm', 'derm-atlas', 'derm101', 'dermSI', 'dermnet', 'derm-zh']

    # grab all English labels
    for sheet in sheet_names:
        df = pd.read_excel(xls, sheet)
        eng_lbls = df['英文'].tolist()
        print('for sheet={}, before: ', len(labels))
        labels = labels.union(set(eng_lbls))
        print('after: ', len(labels))

    # write to a text file
    with open(op_fn, 'w') as fwrite:
        for item in labels:
            fwrite.write(str(item)+'\n')
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

    file_opener = open(fn,'r')
    res = file_opener.readlines()
    # strip the very last newline character
    res = [x[:-1] for x in res]
    # remove 'nan'
    return list(filter(lambda x: x != 'nan', res))

if __name__ == '__main__':

    pass