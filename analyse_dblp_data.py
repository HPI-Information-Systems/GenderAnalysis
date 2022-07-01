import glob
import os
import pandas as pd
import collections
import random
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import itertools
import re


def prepare_names_for_gapi(destination, with_middle_names=True, df=None):
    """
    Prepare the first names for the GenderAPI with splitting full names up into first, (middle) and last names.
    Csv files under '/input' are used if no source is given in df.
    Results are saved to param destination.

    :param destination:         string, relative path to output file
    :param with_middle_names:   bool, default:True, whether to add middle names to output or not
    :param df:                  pd.DataFrame, containing e.g. only unknown names
    """
    if df is None:
        df = authorships(with_genders=False)

    # Extract first, middle and last names from full names
    # Exclude full names that only consist of one name (cannot determine if it's the first or last name)
    full_names = [author_name.split(" ") for author_name in df['author_name']]
    first_names = [full_name[0] for full_name in full_names if len(full_name) > 1]
    middle_names = [full_name[1:-1] for full_name in full_names if len(full_name) > 1]
    last_names = [full_name[-1] for full_name in full_names if len(full_name) > 1]

    # Clean last names
    for i, last_name in enumerate(last_names):
        if last_name == 'Jr.' or last_name == 'Sr.':
            # Add the last middle name to the last name
            last_names[i] = f"{middle_names[i][-1]} {last_names[i]}"
            middle_names[i] = middle_names[i][:-1]

    # Prepare checkable first and middle names
    # Discard abbreviations and 'nobiliary' particles
    cleaned_first_names = [name for name in first_names if not re.match(r'\w+[.]', name)]
    if with_middle_names:
        no_middle_name = ['van', 'Van', 'von', 'Von', 'zur', 'Zur', 'den', 'Den', 'der', 'Der', 'del', 'Del', 'de',
                          'De', 'la', 'La', 'los', 'Los', 'ul', 'Ul', 'al', 'Al', 'da', 'Da', 'el', 'El', 'vom', 'Vom',
                          'auf', 'Auf', 'des', 'Des', 'di', 'Di', 'dos', 'Dos', 'du', 'Du', 'ten', 'Ten', 'ter', 'Ter',
                          "van't", "Van't", ]
        cleaned_first_names.extend([name for name_list in middle_names for name in name_list
                                    if not re.match(r'\w+[.]', name) and name not in no_middle_name])
    # Discard quotes and brackets
    cleaned_first_names = [name.strip("()'\"") for name in cleaned_first_names]

    df = pd.DataFrame(cleaned_first_names, columns=['first_name'])
    df.drop_duplicates(inplace=True)
    df.sort_values(['first_name'], inplace=True)
    df.to_csv(destination, index=False, header=['first_name'])


def analyse_data(gapi_path):
    """
    Read the csv files given in '/input' (with commas as separators), extract authorships from it and enrich them with
    gender based on the file(s) given under param gapi_path (with semicolons as separators as the csv files returned by
    the Gender-API uses semicolons as separators). It produces plots saved to '/output' and also saves still unknown
    names under '/helper_files/unprocessed_first_names.csv' for future processing by the Gender-API.

    :param gapi_path: path, both a file or a directory is accepted
    """
    identities = _load_identity_list()
    df = authorships(with_accuracy=True, identity_list=identities, gapi_path=gapi_path)
    df.to_csv('output/with_genders/authorships_all_fields.csv', index=False)
    df_with_assumed = _assume_gender_weighted(df)
    df_with_assumed.to_csv('output/with_genders/authorships_all_fields_gender_assumed.csv', index=False)

    # Get all venues from all fields and assume the gender for unknown and neutral names
    df_with_assumed = pd.read_csv('output/with_genders/authorships_all_fields_gender_assumed.csv')

    # Get all venues from DB field except PODS
    df_db_without_pods = _exclude_venue(_get_field(df_with_assumed, ['DB']), ['PODS'])
    df_db_without_pods.to_csv('output/with_genders/authorships_db_field_gender_assumed_without_PODS.csv')
    aggregates_db_without_pods = aggregate_authorship(df_db_without_pods)

    # Get all fields without conferences not in CS Rankings
    df_whole_cs_ranked = _exclude_venue(df_with_assumed, ['CIDR', 'DASFAA', 'DKE', 'EDBT'])
    df_whole_cs_ranked.to_csv('output/with_genders/'
                              'authorships_all_fields_gender_assumed_without_CIDR_DASFAA_DKE_EDBT.csv')
    aggregates_whole_cs_ranked = aggregate_authorship(df_whole_cs_ranked, group_attrs=['field', 'year'],
                                                      funcs={'first': _first_woman_author})

    # Show plots of rolling means of authorships by woman
    plot_moving_averages_of_authorships(aggregates_db_without_pods['all'], 'all positions', save=False)
    plot_moving_averages_of_authorships(aggregates_db_without_pods['any'], 'any position', save=False)
    plot_moving_averages_of_authorships(aggregates_db_without_pods['first'], 'first author', save=False)
    plot_moving_averages_of_authorships(aggregates_db_without_pods['last'], 'last author', save=False)
    plot_moving_averages_of_authorships(aggregates_whole_cs_ranked['first'], 'first author', save=False)

    # Save plots of rolling means of authorships by woman
    plot_moving_averages_of_authorships(aggregates_db_without_pods['all'], 'all positions', save=True, header=False)
    plot_moving_averages_of_authorships(aggregates_db_without_pods['any'], 'any position', save=True, header=False)
    plot_moving_averages_of_authorships(aggregates_db_without_pods['first'], 'first author', save=True,
                                        header=False)
    plot_moving_averages_of_authorships(aggregates_db_without_pods['last'], 'last author', save=True, header=False)
    plot_moving_averages_of_authorships(aggregates_whole_cs_ranked['first'], 'first author', save='fields',
                                        header=False)

    # Extract and save unknown names
    unknown = df[df.unknown == 1]
    prepare_names_for_gapi('helper_files/unprocessed_first_names.csv', df=unknown)

    # Save and print used publication range per venue as well as total number of papers and authors
    statistics = df.groupby(['venue']).agg({'year': ['min', 'max'], 'paper_id': pd.Series.nunique,
                                            'author_id': pd.Series.nunique}).to_string()
    f = open("output/statistics.txt", "w")
    f.write(statistics)
    f.close()
    click.echo(statistics)


def authorships(field=None, with_accuracy=False, identity_list=None, with_genders=True, gapi_path=None):
    """
    Constructs a dataframe containing an entry for each authorship found in the submission data of the given field.
    The added columns 'man', 'woman', 'neutral', unknown' contain 1 if the author contains to the category, else 0.
    More added columns are 'field', 'year', 'venue', 'paper_id', 'title', 'author_position', 'author_position_last' and
    'accuracy' if with_accuracy is True. The accuracy is used to build 'f' and 'm' being the probability that the author
    has a female / male name. You can provide an identity_list that contains author with dblp id, name(s), paper(s) and
    the manually identified gender ('man' and 'woman'). This list has priority over the results of the Gender-API.

    :param field:           string or None, if field is specified, the csv file with that name in the output directory
                            is loaded. If no field is given, all under csv files in output directory are loaded with
                            given file name as the field's name.
    :param with_accuracy:   bool, whether to return the accuracy for the gender
    :param identity_list:   dataframe
    :param with_genders:    bool, whether to add gender to authorships or not
    :param gapi_path:       string, path to file of first names enriched with gender by Gender-API

    :return: dataframe
    """

    # If no field is specified, use them all
    glob_path = os.path.join('input', '*.csv') if field is None else os.path.join('input', field + '.csv')
    df = []
    field_was_specified = True if field else False

    for csv_file in glob.glob(glob_path):
        data = pd.read_csv(csv_file, usecols=['venue', 'year', 'paper_id', 'title', 'authors'])
        field = field if field_was_specified else csv_file.replace('input/', '').replace('.csv', '')
        click.echo(f"Successfully loaded authors from {csv_file} of field {field}")
        for _, paper in data.iterrows():

            # Skip papers without authors
            if pd.isna(paper.authors):
                continue

            venue = paper.venue
            authors = paper.authors.split('; ')
            for (index, author_info) in enumerate(authors):
                # Start author indexes at 1
                index += 1

                # Initialize a new data point
                datum = collections.OrderedDict(
                    field=field,
                    venue=venue,
                    year=int(paper.year),
                    paper_id=paper.paper_id,
                    title=paper.title,
                    author_position=None,
                    author_name=None,
                    author_id=None,
                    man=0,
                    woman=0,
                    neutral=0,
                    unknown=0,
                    accuracy=None
                )
                datum['author_position'] = index

                # Extract the author name and ID
                author_info = author_info.split(': ')
                author_id = author_info[0]
                author_name = author_info[1]

                # Remove numerical suffixes
                author_name = author_name.rstrip(' 0123456789')
                # Parse XHTML's apostrophe and quotes
                author_name = author_name.replace('&apos;', "'")
                author_name = author_name.replace('&quot;', '')

                datum['author_name'] = author_name
                datum['author_id'] = author_id
                gender = None

                if with_genders:
                    # Check if we know the gender of the person if desired
                    if identity_list is not None and not identity_list.empty:
                        known_identity = identity_list.loc[identity_list['author_id'] == datum['author_id']]
                        if len(known_identity) > 1:
                            click.echo(f"WARNING: More than one identity found for {datum['author_id']} in ")
                        if len(known_identity) == 1:
                            if known_identity.iloc[0]['woman'] == 1:
                                gender = 'woman'
                                f = 1.0
                                m = 0.0
                            elif known_identity.iloc[0]['man'] == 1:
                                gender = 'man'
                                f = 0.0
                                m = 1.0

                    if gender is None:
                        # Attempt to predict gender with GenderAPI's results
                        f = m = 0.0
                        if with_accuracy:
                            gender, accuracy = gapi_gender(author_name, gapi_path, with_accuracy=with_accuracy)
                        else:
                            gender = gapi_gender(author_name, gapi_path, with_accuracy=with_accuracy)
                        if gender == 'woman':
                            f = accuracy / 100
                            m = (100 - accuracy) / 100
                        if gender == 'man':
                            m = accuracy / 100
                            f = (100 - accuracy) / 100
                        if gender == 'neutral':
                            f = m = 0.5
                        datum['f'] = f
                        datum['m'] = m
                        if gender is None:
                            gender = 'unknown'

                    datum[gender] += 1
                    datum['accuracy'] = accuracy if accuracy else ''

                else:
                    datum['unknown'] = 1

                df.append(datum)

    df = pd.DataFrame(df)
    # Find index of the last author of each paper and add it as column
    last_author_index = df.groupby(['paper_id'], sort=False)['author_position'].max().to_frame()
    df = df.join(last_author_index, on='paper_id', rsuffix='_last')

    if with_genders:
        click.echo('Successfully infered the genders!')
    return df


def gapi_gender(author_name, gapi_path, with_accuracy=False):
    """
    Checks the gender of the author's first name (and middle names if necessary) against the list of first names with
    genders from Gender-API. It skips abbreviations as well as one-word names as it's unknown if the first name or the
    last name is given. Please provide the first name first in the author_name param.

    :param author_name:     string, full name divided with a space, first name comes first
    :param gapi_path:       string, path to csv file that contains the list of first names with genders from Gender-API
    :param with_accuracy:   bool, whether to return the accuracy for the gender

    :return: string or tuple of string and float, the gender is either 'woman', 'man', 'neutral' or None
    """

    # Load the list of first names with Gender-API once
    if not hasattr(gapi_gender, 'genders_by_gapi'):
        gapi_gender.genders_by_gapi = _load_gapi_list(gapi_path)
        print("Load the gender-enriched name list")

    # Can't determine if this is just the first or just the last name
    if len(author_name.split(" ")) == 1:
        return None, None if with_accuracy else None

    first_name = author_name.split(" ")[0].strip("()'\"")
    entry = gapi_gender.genders_by_gapi.query('first_name == @first_name')
    if entry.empty or pd.isnull(entry['ga_gender'].values[0]):
        # Check for middle names
        result = gapi_gender(" ".join(author_name.split(" ")[1:]), gapi_path, with_accuracy=with_accuracy)
        return result

    else:
        gender = entry['ga_gender'].values[0]
        accuracy = entry['ga_accuracy'].values[0]

        if accuracy == 50 or gapi_gender == 'unknown':
            # GenderAPI's 'unknown' names always have an accuracy of 50
            return ('neutral', accuracy) if with_accuracy else 'neutral'
        elif gender == 'male':
            return ('man', accuracy) if with_accuracy else 'man'
        elif gender == 'female':
            return ('woman', accuracy) if with_accuracy else 'woman'
        else:
            return (None, None) if with_accuracy else None


def aggregate_authorship(df, group_attrs=None, funcs=None):
    """
    Compute the average per year of the percentage of woman being at a certain position of the authors list. Positions
    can be: first, last, any and all (specified in param funcs).

    :param df:          pd.DataFrame, containing authorships. See method 'authorships' for more details.
    :param group_attrs: list of str, columns to use for grouping, default: ['venue', 'year']. Also: ['field', 'year'].
    :param funcs:       dict of functions with names to be accessed by later, possible options: _first_woman_author,
                        _last_woman_author, _any_woman_author, _all_woman_author
    :return:            dict of aggregates per functions specified in param func
    """
    if group_attrs is None:
        group_attrs = ['venue', 'year']
    aggregates = {}
    if funcs is None:
        funcs = {
            'first': _first_woman_author,
            'last': _last_woman_author,
            'any': _any_woman_author,
            'all': _all_woman_author
        }
    for (name, fn) in funcs.items():
        # First group by paper ID to calculate values per paper

        df_agg = df.groupby(['paper_id'] + group_attrs).apply(fn).to_frame('woman')

        # Then group by conference and year and calculate the percentage
        aggregates[name] = df_agg.groupby(group_attrs).mean().multiply(100)

    return aggregates


def plot_moving_averages_of_authorships(df, plot_label, save=None, header=True):
    """
    Plots or saves 3-year moving averages of the percentage of woman being at a certain position of the authors list.

    :param df:          pd.DataFrame of aggregates, See 'aggregate_authorship' for more details.
    :param plot_label:  string, to be added to the plot's title or file's name if param save == None.
                        Referring to the position of a female author.
    :param save:        None or str, whether to save the plot as pgf under given name or to show it.
    :param header:      bool, whether to add a title to the to be displayed plot.
    """
    # Calculate the rolling mean across three years
    rolling_mean = df.unstack(level=0).sort_values(['year']).ffill() \
                     .rolling(window=3).mean()

    # Generate a simple line plot
    if header:
        plot_title = 'Authors who are women by year (%s)' % plot_label
    else:
        plot_title = None
    fig = rolling_mean.plot(figsize=(15, 8), title=plot_title)

    # Set the markers
    markers = itertools.cycle((',', '+', '.', 'o', '*', 'x', '^', 'P'))
    for line in fig.get_lines():
        line.set_marker(next(markers))

    # Add x-axis labels every other year
    fig.xaxis.set_major_locator(ticker.MultipleLocator(5))

    # y-axis is always a percentage of all papers
    fig.set_ylabel('% of papers')

    # Strip the extra group part from legends
    fig.legend([c.split(', ')[1].rstrip(')')
                for c in fig.get_legend_handles_labels()[1]])

    # Optionally save to file
    if save:
        # Set matplotlib parameters
        matplotlib.use('pgf')
        matplotlib.rcParams.update({
            'pgf.texsystem': 'pdflatex',
            'font.family': 'serif',
            'text.usetex': True,
            'pgf.rcfonts': False,
            'font.size': 20,
        })

        # Calculate the filename
        if isinstance(save, str):
            filename = save
        else:
            filename = plot_label.replace(' ', '_')
        filename += '.pgf'

        fig.figure.set_tight_layout(True)
        fig.figure.savefig(os.path.join('output', filename))
    else:
        matplotlib.use('TkAgg')
        plt.show()


def extract_unknown_neutrals(source, destination):
    """
    Read the source csv file, extract names with unknown or neutral names, merge all unique names and paper_ids with
    the same author_id into columns 'author_names' and 'papers' and write pd.DataFrame to destination.
    Result can be used to manually annotate the gender from known persons.
    :param source:      path of a csv file
    :param destination: path of a csv file
    """
    df = pd.read_csv(source, usecols=['paper_id', 'author_id', 'author_name', 'man', 'woman', 'neutral', 'unknown'])
    df = df[(df['neutral'] == 1) | (df['unknown'] == 1)].reset_index(drop=True)
    grouped = df.groupby('author_id')
    names = grouped['author_name'].apply(set).apply(', '.join).\
        reset_index().rename(columns={'author_name': 'author_names'})
    papers = grouped['paper_id'].apply(', '.join).reset_index().rename(columns={'paper_id': 'papers'})['papers']
    man = pd.DataFrame([0] * grouped.ngroups, columns=['man'])
    woman = pd.DataFrame([0] * grouped.ngroups, columns=['woman'])
    neutral = grouped['neutral'].apply(lambda x: ', '.join(set(map(str, x)))).reset_index()['neutral']
    unknown = grouped['unknown'].apply(lambda x: ', '.join(set(map(str, x)))).reset_index()['unknown']
    df_new = pd.concat([names, man, woman, neutral, unknown, papers], axis=1)
    df_new.sort_values(['unknown', 'author_names'], inplace=True)
    df_new.to_csv(destination, index=False)


def _load_identity_list():
    glob_path = os.path.join('input/known_identities', '*.csv')
    identities = []
    for csv_file in glob.glob(glob_path):
        if 'sample_file.csv' not in csv_file:
            identities.append(pd.read_csv(csv_file))
    if identities:
        identities = pd.concat(identities)

        # Remove still unidentified names and duplicates
        identities = identities[(identities['man'] == 1) | (identities['woman'] == 1)]
        identities.drop_duplicates(inplace=True)
    return identities


def _load_gapi_list(gapi_path):
    if '.csv' in gapi_path:
        gender_enriched_names = pd.read_csv(gapi_path, sep=';')
    else:
        glob_path = os.path.join(gapi_path, '*.csv')
        gender_enriched_names = []
        for csv_file in glob.glob(glob_path):
            if 'sample_file.csv' not in csv_file:
                gender_enriched_names.append(pd.read_csv(csv_file, sep=';'))
        if gender_enriched_names:
            gender_enriched_names = pd.concat(gender_enriched_names)

    # Remove duplicates
    gender_enriched_names.drop_duplicates(inplace=True)
    return gender_enriched_names


def _assume_gender_weighted(df):
    """
    Assume the gender of unknown/neutral names to be proportional
    to the ratio of known man/woman names in the remainder
    """

    # Convert gender columns to booleans
    df['man'] = df['man'] == 1
    df['woman'] = df['woman'] == 1
    df['neutral'] = df['neutral'] == 1
    df['unknown'] = df['unknown'] == 1

    # Calculate gender ratio
    known = df[~df['neutral'] & ~df['unknown']]
    woman_authors = known[known['woman']]['author_id'].nunique()
    man_authors = known[known['man']]['author_id'].nunique()
    woman_ratio = woman_authors / (woman_authors + man_authors)

    # Assume a gender for each author with unknown
    # gender based on the observed distribution
    author_genders = {}
    for author in df[df['unknown'] | df['neutral']]['author_id'].unique():
        if random.random() <= woman_ratio:
            author_genders[author] = 'woman'
        else:
            author_genders[author] = 'man'

    # Set the assumed gender on the original dataframe
    for index in df.index:
        if df.loc[index, 'unknown'] or df.loc[index, 'neutral']:
            gender = author_genders[df.loc[index, 'author_id']]
            df.loc[index, gender] = True

    # Convert boolean gender columns to 0/1's
    df['man'] = df['man'].astype(int)
    df['woman'] = df['woman'].astype(int, copy=False)
    df['neutral'] = df['neutral'].astype(int, copy=False)
    df['unknown'] = df['unknown'].astype(int, copy=False)
    return df


def _first_woman_author(group):
    # Check for the first author of a paper being a woman
    return group['woman'].iloc[0]


def _last_woman_author(group):
    # Check for the last author of a paper being a woman
    return group['woman'].iloc[group['author_position_last'].iloc[0] - 1]


def _any_woman_author(group):
    # Check for any author of a paper being a woman
    return group['woman'].any()


def _all_woman_author(group):
    # Check for all authors of a paper being a woman
    return group['woman'].all()


def _exclude_venue(df, venue):
    return df[~df['venue'].isin(venue)]


def _get_field(df, field):
    return df[df['field'].isin(field)]


if __name__ == '__main__':
    import click


    @click.group()
    def cli():
        pass


    @cli.command(name='prepare-names-for-gapi')
    @click.argument('destination', type=click.File('w'))
    def click_prepare_names_for_gapi(destination):
        """
        Prepare the first names for the GenderAPI with splitting full names up into first, middle and last names.
        Csv files under '/input' are used. Results are saved to param destination.

        :param destination: string, relative path to output file
        """
        prepare_names_for_gapi(destination)


    @cli.command(name='analyse-data')
    @click.argument('gapi_path', type=click.Path(file_okay=True, dir_okay=True))
    def click_analyse_data(gapi_path):
        """
        Read the csv files given in '/input' (with commas as separators), extract authorships from it and enrich them
        with gender based on the file(s) given under param gapi_path (with semicolons as separators as the csv files
        returned by the Gender-API uses semicolons as separators). It produces plots saved to '/output' and also saves
        still unknown names under '/helper_files/unprocessed_first_names.csv' for future processing by the Gender-API.

        :param gapi_path: path, both a file or a directory is accepted
        """
        analyse_data(gapi_path)


    @cli.command(name='extract-unknown-neutrals')
    @click.option('--source', type=click.Path(), default='output/with_genders/authorships_all_fields.csv',
                  help='Path to csv file')
    @click.option('--destination', type=click.Path(), default='input/known_identities/authors_neutral_unknown.csv',
                  help='Path to csv file')
    def click_extract_unknown_neutrals(source, destination):
        """
        Read the source csv file, extract names with unknown or neutral names, merge all unique names and paper_ids with
        the same author_id into columns 'author_names' and 'papers' and write pd.DataFrame to destination.
        Result can be used to manually annotate the gender from known persons.
        :param source:      path to csv file
        :param destination: path to csv file
        """
        click.echo(f"Read file from {source}")
        extract_unknown_neutrals(source, destination)
        click.echo(f"Write file to {destination}")


    cli()
