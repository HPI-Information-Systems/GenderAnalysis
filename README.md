# GenderAnalysis
An analysis of gender distribution in scientific publications. Genders are determined with the commercial tool 
[Gender-API](https://gender-api.com/) on the basis of first names. Results are `female`, `male`, `neutral` or `unknown`.  
With the ratio between unique woman and man among the authors in mind, we assign authors with unknown or neutral gender 
one of the binary genders. As this is a random process, it will produce different outcomes with each execution resulting
in slightly different plots.

While we realize that gender is not a binary concept distinguishing women and men, we do not have the means 
to identify any more fine-grained designations based on the given data (first names), which matches that which reviewers
and readers usually have at their disposition. 

## Setup

Clone the repository and install all dependencies. We use Pipenv to manage dependencies, so this must be installed 
first. To install other dependencies, run `pipenv install`.
For getting the publication data, we use [dblp-retriever](https://github.com/nenock/dblp-retriever) which is soon going
to be installed as a submodule here.

## Usage

### Get help and documentation
Run `pipenv run python3 analyse_dblp_data.py --help` to get a list of possible subcommands `analyse_dblp_data` provides.
Run get information about the subcommand, just run `pipenv run python3 analyse_dblp_data.py <subcommand> --help`. 

### Extract unique first names for initial gender-annotation
We use the Gender-API to determine the gender of author's first names (sometimes middle names are used).
As this is a commercial tool, we do not provide the gender-annotated list of first names but the raw list of first_names.
Run the following if you want to generate the raw list of first names based on different venue data.
All csv files under `input` are used to generate that list. The list is saved under `helpers/first_names.csv` or any 
destination, you choose as the last option of the command:

```pipenv run python3 analyse_dblp_data.py prepare-names-for-gapi helpers/first_names.csv```

### Get gender-annotations for first names from [Gender-API](https://gender-api.com/)
Upload the list of first_names (`helpers/first_names.csv`) to the Gender-API and save the result under 
`helpers/GenderAPI`. 

### Run the gender analysis
After having one or more lists of gender-annotated first names under `helpers/GenderAPI`, run the following
command with the path to a specific file or to a directory to use all files in there to do the gender analysis.

```pipenv run python3 analyse_dblp_data.py analyse-data helpers/GenderAPI/``` OR

```pipenv run python3 analyse_dblp_data.py analyse-data helpers/GenderAPI/first_names_gapi_processed.csv```

It saves the gender-annotated list of authorships under `output/with_genders` and produces `.pgf` plots saved to 
`/output`. Statistics (first and last publication year, overall number of papers and overall number of unique authors)
of the venues are saved to `output/statistics.txt`.

If you add later on new submission data with potential unseen first names, just run the analysis, pass 
`helpers/unprocessed_first_names.csv` to the Gender-API and add the result to `helpers/GenderAPI`.

### Get names of unknown or neutral gender for manual annotations
If you want to manually annotate the gender of known persons that were given a neutral or unknown gender by the 
Gender-API, run the following command to get a list of these persons. For a dblp's author id, it adds all in the 
submission data used names of that person as well as links to the papers to give you a starting point. Inspect `--help`
for default source and destination paths or specify them.

```pipenv run python3 analyse_dblp_data.py extract-unknown-neutrals```

OR with specified source and destination files:

```pipenv run python3 analyse_dblp_data.py extract-unknown-neutrals --source output/with_genders/authorships_db_field_gender_assumed_without_PODS.csv --destination input/known_identities/unknown_neutral_db_authors.csv```

Just add a `1` in the applicable gender column for persons who and whose gender you can identify with certainty. 
You can find an annotated sample output file under `input/known_identities/sample_file.csv`. 
