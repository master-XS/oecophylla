import pandas as pd
import biom
from biom.util import biom_open


def combine_profiles(profiles):
    """Combines profiles for several samples into one table.

    Parameters
    ----------
    profiles : iterable((str, str))
        An iterable of tuples, where the second component is the filepath
        pointing to a profile (format: feature<tab>count), while the first
        component defines a sample name for the profile.

    Returns
    -------
    Pandas.DataFrame with rows for features, columns for samples.
    """
    samples = [pd.read_table(file, index_col=0, names=[name], comment='#')
               for name, file in profiles]
    return pd.concat(samples, axis=1).fillna(0).astype(float)


def extract_level(table, code, delim=';', dic=None):
    """Extract features at certain level from a table.

    Parameters
    ----------
    table : Pandas.DataFrame
        with rows for features, columns for samples
        fearures are Greengenes-style lineage strings
    code : str
        single-letter abbreviation of level
    delim : str (optional)
        delimiter for levels in lineage string (default: ";")
    dic : dict (optional)
        translate rank names into TaxIDs using this dictionary

    Returns
    -------
    Pandas.DataFrame
        with features replaced by individual ranks

    Raises
    ------
    ValueError
        if there are duplicated rank names at current level

    Notes
    -----
    Rank names not found in the dictionary will be dropped.
    Duplicated TaxIDs are allowed. They will be merged and their cell values
    will be summed.
    """
    df = table.copy()

    # get last (right-most) rank of lineage get index of new column
    i = len(df.columns)
    df[i] = df.index.str.split(delim).str.get(-1)

    # only keep given level with explicit name
    df = df[(df[i].str.len() > 3)
            & df[i].str.startswith('%s__' % code)
            & ~df[i].str.endswith('_noname')]

    # check for duplicated rank names
    if df[i].duplicated().any():
        raise ValueError('Duplicated taxa detected')
    df.set_index(i, inplace=True)

    # translate rank names into TaxIDs
    if dic is not None:
        df[i] = df.index.to_series().map(dic)
        df = df.groupby(2).sum()
    df.index.name = None
    return df


def combine_kraken(kraken_reports):
    """Combines Kraken-style reports for several samples into one table.

    Parameters
    ----------
    kraken_reports : Iterable((str, str))
        An iterable of tuples, where the second component is the filepath
        pointing to a Kraken report file, the first component defines a
        sample name for the Kraken report.

    Returns
    -------
    tuple of (
        Pandas.DataFrame
            with rows for features, columns for samples
        dict of set of str
            level code : set of TaxIDs
    )

    Notes
    -----
    A "Kraken-style report" is generated by Kraken and Centrifuge, and
    potentially other programs.
    """
    # a Kraken report file is a table of six columns, the 2nd, 4th and 5th of
    # which are number of reads covered, level code, and TaxID
    samples = [pd.read_table(file, usecols=[1, 3, 4], names=[name, 'lv', None],
               index_col=2) for name, file in kraken_reports]

    # for extended compatibility, convert TaxIDs to strings
    for sample in samples:
        sample.index = sample.index.map(str)

    # combine number of reads covered by each TaxID across samples
    combined = pd.concat([x.iloc[:, 0] for x in samples],
                         axis=1).fillna(0).astype(float)

    # get TaxID to level code map
    tid2lv = pd.concat([x['lv'] for x in samples])

    # replace D(omain) with K(ingdom)
    tid2lv.replace('D', 'K', inplace=True)

    # summarize TaxIDs belonging to each level
    lv2tids = {}
    for tid, code in tid2lv.iteritems():
        if not code in lv2tids:
            lv2tids[code] = set()
        lv2tids[code].add(tid)

    # return the combined DataFrame and the level to TaxIDs map
    return (combined, lv2tids)


def combine_centrifuge(centrifuge_outputs):
    """Combines Centrifuge counts for several samples into one table.

    Parameters
    ----------
    centrifuge_outputs : Iterable((str, str))
        An iterable of tuples, where the second component is the filepath
        pointing to a Centrifuge output file, the first component defines a
        sample name for the Centrifuge output.

    Returns
    -------
    Pandas.DataFrame with rows for features, columns for samples.

    Notes
    -----
    A Centrifuge output file is a table of 7 columns, the 2nd and 5th of which
    are TaxID and number of reads assigned to it.
    """
    samples = [pd.read_table(file, index_col=0, header=0, usecols=[1, 4],
               names=[None, name]) for name, file in centrifuge_outputs]
    return pd.concat(samples, axis=1).fillna(0).astype(float)


def combine_bracken(bracken_outputs):
    """Combines bracken counts for several samples into one table.

    Parameters
    ----------
    bracken_outputs : Iterable((str, str))
        An iterable of tuples, where the second component is the filepath
        pointing to a Bracken output file, the first component defines a
        sample name for the Bracken output.

    Returns
    -------
    Pandas.DataFrame with rows for features, columns for samples.
    Feature labels are NCBI taxonomy IDs. Sample labels are obtained from first
    components of passed iterable.

    Notes
    -----
    More information about the bracken file format:
    https://ccb.jhu.edu/software/bracken/index.shtml?t=manual
    """
    samples = []
    # walking over the given directory.
    # We don't know which files are actual bracken abundance estimation files.
    for (samplename, _file) in bracken_outputs:
        sample_abund = pd.read_csv(_file, sep='\t', index_col=1)

        # we are collecting the bracken estimated kraken assigned read numbers
        sample_counts = sample_abund['new_est_reads']

        # infer sample name from filename and remove file extension if present
        sample_counts.name = samplename

        # add resulting pd.Series to our collection of samples
        samples.append(sample_counts)

    # return a merged pd.DataFrame of all absolute estimated assigned reads
    return pd.concat(samples, axis=1).fillna(0).astype(int)


def pandas2biom(file_biom, table):
    """ Writes a Pandas.DataFrame into a biom file.

    Parameters
    ----------
    file_biom: str
        The filename of the BIOM file to be created.
    table: a Pandas.DataFrame
        The table that should be written as BIOM.

    Returns
    -------
    Nothing
    """
    bt = biom.Table(table.values,
                    observation_ids=list(map(str, table.index)),
                    sample_ids=table.columns)

    with biom_open(file_biom, 'w') as f:
        bt.to_hdf5(f, "example")
