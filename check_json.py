import json
import os
import warnings
from difflib import SequenceMatcher
from enum import Enum
from typing import Optional, Dict, Set, Tuple

import boto3
import pandas as pd
from botocore.exceptions import ClientError

from config_campaignreporting.json_generator.prompts import rules, first_example, expected_response_1, second_example, \
    expected_response_2, third_example, expected_response_3, new_request

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

class GptRoles(str, Enum):
    """
    Enum class for GPT roles.
    """

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

# Get the project directory (assuming the script is in the project directory or a subdirectory)
project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
print(project_dir)

# Construct the paths relative to the project directory
jsons_path = os.path.join(project_dir, "reports/jsons")
briefings_path = os.path.join(project_dir, "reports/briefing")
print(briefings_path)
shots_path = os.path.join(project_dir, "reports/Shots")

s3_session = boto3.Session(profile_name="ESP-DEV")
s3_client = s3_session.client("bedrock-runtime", region_name="us-east-1")
model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"

example_json_content = None

def load_example_json() -> None:
    """
    Load the example JSON content from the file.
    ----------
    Returns
        None
    """
    global example_json_content
    if example_json_content is None:
        example_json_path = os.path.join(shots_path, "example_json_1.json")
        with open(example_json_path, "r") as file:
            example_json_content = json.load(file)

def process_excel_content(excel_content: Optional[str] = None) -> str:
    """
    Process the given Excel content and create a JSON file with the results.
    Parameters
    ----------
    excel_content: str
        The Excel content to process.

    Returns
    -------
    clean_briefing
        The clean Excel file as a json string.
    """
    load_example_json()

    user_message = f"""Process the following Excel content:\n\n{excel_content}, and create a JSON file with the results.
                       The main body of the JSON should be 'briefing accion comercial'.
                       Then, 'informacion general' should be a block containing 'Nombre de la acción Comercial', 'Producto', 'Abierto/Segmentada', 'Metadata Adobe Campaign', and so on.
                       Do not translate the dictionary keys, keep the original names like 'Nombre de la acción Comercial' or 'Producto'.
                       Clean the strings of the desired format such as '•' or '\\n'.
                       When there are colons, such as in 'descripcion campaña', they should also be part of the JSON as key-value pairs.
                       The 'n.a.' values should be null.
                       Ensure that the dates are formatted as 'yyyy-mm-dd'.
                       The structure should be similar to the following example, with different success and metric criteria based off the typology of the campaign:
                       {json.dumps(example_json_content, indent=2)}
                       The most important part is the "MEDICIONES" section in the Briefing, where the adobe input is shown, with the different success criteria if any and campaign typology.
                       The descripcion campaña part is also important, where the promotional code is shown, as well as specific conditions such as amount of bills to be domiciled.
                       """
    conversation = [
        {
            "role": GptRoles.USER,
            "content": [{"text": user_message}],
        }
    ]

    try:
        response = s3_client.converse(
            modelId=model_id,
            messages=conversation,
            inferenceConfig={"maxTokens": 4096, "temperature": 0.01},
            additionalModelRequestFields={"top_k": 250},
        )

        clean_briefing = response["output"]["message"]["content"][0]["text"].rstrip()

    except (ClientError, Exception) as e:
        print(f"ERROR: Can't invoke '{model_id}'. Reason: {e}")
        exit(1)

    return clean_briefing


def list_excel_files_path(directory: str) -> list:
    """
    Return a list of all Excel files in the given directory.

    Parameters
    ----------
    directory : str
        The directory path to search for Excel files.

    Returns
    -------
    list
        A list of paths to the Excel files found in the directory.
    """
    excel_files_path = [
        os.path.join(directory, f)
        for f in os.listdir(directory)
        if f.endswith(".xlsx") or f.endswith(".xls")
    ]
    return excel_files_path

all_briefings = list_excel_files_path(briefings_path)

excels_descriptions = {}

for excel_file in all_briefings:
    excel_df = pd.read_excel(excel_file)
    action_name = str(excel_df["Unnamed: 7"].iloc[5])
    if isinstance(action_name, str):
        start = action_name.find(') ') + 1
        excels_descriptions[excel_file] = action_name[start:].strip().replace("/", "").replace("  ", " ")
    else:
        excels_descriptions[excel_file] = "Invalid description"

print(len(excels_descriptions),"briefing files gathered")

def list_json_file_paths(directory: str) -> list:
    """
    Return a list of all JSON files in the given directory.

    Parameters
    ----------
    directory : str
        The directory path to search for JSON files.

    Returns
    -------
    list
        A list of paths to the JSON files found in the directory.
    """
    json_paths = [
        os.path.join(directory, f) for f in os.listdir(directory) if f.endswith(".json")
    ]
    return json_paths

all_json_paths = list_json_file_paths(jsons_path)

json_descriptions = {}
for json_file in all_json_paths:
    with open(json_file, "r") as file:
        json_string = file.read()
    start = json_string.find(') ') + 2
    end = json_string.find('",', start) - 5
    description = json_string[start:end].strip().strip('"')
    json_descriptions[json_file] = description

print(len(json_descriptions),"json files gathered")

def match_descriptions(
    json_dict: Dict[str, str], excel_dict: Dict[str, str], threshold: float = 0.93
) -> Set[Tuple[str, str, str]]:
    """
    Match descriptions between JSON and Excel dictionaries based on a similarity threshold.

    Parameters
    ----------
    json_dict : Dict[str, str]
        Dictionary containing JSON file paths and their descriptions.
    excel_dict : Dict[str, str]
        Dictionary containing Excel file paths and their descriptions.
    threshold : float, optional
        Similarity threshold for matching descriptions (default is 0.9).

    Returns
    -------
    Set[Tuple[str, str, str]]
        A set of tuples containing matched JSON file path, Excel file path, and the matched description.
    """
    matches = set()
    for json_file, json_desc in json_dict.items():
        for excel_file, excel_desc in excel_dict.items():
            similarity = SequenceMatcher(None, str(json_desc), str(excel_desc)).ratio()
            if similarity >= threshold:
                matches.add((json_file, excel_file, json_desc, excel_desc))
    return matches

matches = match_descriptions(json_descriptions, excels_descriptions)
print(len(matches),"description matches:")
for match in matches:
    print("JSON:",match[2], "vs Excel:", match[3])

def transform_string_to_prompt(text: str, role: GptRoles = GptRoles.USER) -> list:
    """
    Process the given Excel content and create a JSON file with the results.
    Parameters
    ----------
    role: GptRoles
        The role of the prompt's messenger.
    text: str
        The content of a prompt's message.

    Returns
    -------
    clean_briefing
        The clean Excel file as a json string.
    """
    conversation = [
        {
            "role": role,
            "content": [{"text": text}],
        }
    ]
    return conversation

example_jsons_path_list = list_json_file_paths(shots_path)
example_jsons = {}

for json_file in example_jsons_path_list:
    with open(json_file, "r") as file:
        json_string = file.read()
    example_jsons[json_file] = json_string

example_briefings_path_list = list_excel_files_path(shots_path)
example_excels = {}
for brf_n in [0,1,2]:
    example_briefing_path = os.path.join(shots_path, f"example_brf_{brf_n + 1}.xlsx")
    example_briefing_str = pd.read_excel(example_briefing_path,sheet_name=0).to_string()
    clean_example_briefing = process_excel_content(excel_content=example_briefing_str)
    example_excels[brf_n] = clean_example_briefing

example_jsons_list = list(example_jsons.values())
example_briefings_list = list(example_excels.values())

claude_prompt = []
claude_prompt.extend(transform_string_to_prompt(rules, GptRoles.USER))

claude_prompt.extend(transform_string_to_prompt(first_example.format(json_1 = example_jsons_list[0], brf_1 = example_briefings_list[0]), GptRoles.USER))
claude_prompt.extend(transform_string_to_prompt(expected_response_1, GptRoles.ASSISTANT))

claude_prompt.extend(transform_string_to_prompt(second_example.format(json_2 = example_jsons_list[1], brf_2 = example_briefings_list[1]), GptRoles.USER))
claude_prompt.extend(transform_string_to_prompt(expected_response_2, GptRoles.ASSISTANT))

claude_prompt.extend(transform_string_to_prompt(third_example.format(json_3 = example_jsons_list[2], brf_3 = example_briefings_list[2]), GptRoles.USER))
claude_prompt.extend(transform_string_to_prompt(expected_response_3, GptRoles.ASSISTANT))

def compare_json_excel(clean_briefing: str, json_path: str, prompt: list, new_request: str) -> str:
    """
    Compares json and excel (Briefing) files in the given directory.

    Parameters
    ----------
    clean_briefing: str
        The clean Excel file as a json string.

    json_path: str
        The directory path to search for JSON files.

    prompt: list
        List containing the prompt messages (context) to send to the model.

    new_request : str
        The new request to send to the model.

    Returns
    -------
    diff
        Text pointing out the differences between both json and briefing.
    """
    with open(json_path, "r") as file:
        json_content = file.read()

    prompt.extend(transform_string_to_prompt(new_request.format(clean_briefing=clean_briefing, json=json_content), GptRoles.USER))

    try:
        response = s3_client.converse(
            modelId=model_id,
            messages=prompt,
            inferenceConfig={"maxTokens": 4096, "temperature": 0.1},
            additionalModelRequestFields={"top_k": 250},
        )

        diff = response["output"]["message"]["content"][0]["text"].rstrip()

    except (ClientError, Exception) as e:
        print(f"ERROR: Can't invoke '{model_id}'. Reason: {e}")
        exit(1)

    return diff

for match in matches:
    excel_str = pd.read_excel(match[1]).to_string()
    clean_briefing = process_excel_content(excel_content=excel_str)
    discrepancies = compare_json_excel(clean_briefing, match[0], prompt = claude_prompt, new_request = new_request)
    json_filename = os.path.basename(match[0])
    excel_filename = os.path.basename(match[1])
    print(f"############################ CHECK ############################\n",
          f"Discrepancies for {json_filename} and {excel_filename}:\n{discrepancies}")
