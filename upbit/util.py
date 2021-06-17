def sai_to_upbit_symbol_converter(pair):
    return pair.replace('_', '-')


def upbit_to_sai_symbol_converter(pair):
    return pair.replace('-', '_')
