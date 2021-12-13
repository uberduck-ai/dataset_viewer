import re
import os

import streamlit as st
from annotated_text import annotated_text
from g2p_en import G2p
import pandas as pd
import requests
import sqlite3
import time

g2p = G2p()

CMU_DICT_FILE = os.path.expanduser("~/code/uberdict/src/uberduct/dict/cmudict.dict")
KEY = st.secrets["uberduck_key"]
SECRET = st.secrets["uberduck_secret"]

ADDED_WORDS = {}

class UberduckClient:
    endpoint = "https://api.uberduck.ai/speak"
    status_endpoint = "https://api.uberduck.ai/speak-status"
    def __init__(self, key, secret) -> None:
        self.key = key
        self.secret = secret

    def query(self, speech, voice="lj"):
        response = requests.post(self.endpoint, json=dict(speech=speech, voice=voice), auth=(self.key, self.secret))
        print(response.status_code)
        result = response.json()
        print(result)
        uuid = result["uuid"]
        audio_url = None
        while audio_url is None:
            response = requests.get(self.status_endpoint, params=dict(uuid=uuid))
            result = response.json()
            if result["failed_at"]:
                return
            elif result["finished_at"]:
                audio_url = response.json()["path"]
                return audio_url
            time.sleep(1)

@st.experimental_singleton
def uberduck_client():
    client = UberduckClient(KEY, SECRET)
    return client

@st.experimental_singleton
def words_cache():
    return ADDED_WORDS

@st.experimental_singleton
def sqlite_conn(cmu_dict_file):
    with open(cmu_dict_file, "r") as f:
        lines = f.readlines()
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("CREATE TABLE dict (grapheme, arpa, grapheme_order);")
    cur.execute("CREATE INDEX dict_grapheme ON dict(grapheme_order);")
    cur.execute("CREATE UNIQUE INDEX dict_grapheme_arpa ON dict(grapheme, arpa);")
    for line in lines:
        line = line.strip("\n")
        grapheme, arpa = line.split(" ", 1)
        grapheme_order = grapheme.replace("(", " (")
        cur.execute("INSERT INTO dict VALUES (?, ?, ?)", (grapheme, arpa, grapheme_order))
    return cur

def insert_word(grapheme, arpa, cmu_dict_file):
    grapheme = grapheme.lower()
    _cache = words_cache()
    if grapheme not in _cache:
        _cache[grapheme] = arpa
        cur = sqlite_conn(cmu_dict_file)
        cur.execute("INSERT INTO dict VALUES (?, ?, ?)", (grapheme, arpa, grapheme))
        flush_to_file(cmu_dict_file)

def flush_to_file(cmu_dict_file):
    cur = sqlite_conn(cmu_dict_file)
    rows = cur.execute("SELECT grapheme, arpa FROM dict ORDER BY grapheme_order")
    with open(cmu_dict_file, "w") as f:
        for row in rows:
            g, a = row
            f.write(f"{g} {a}\n")

def run():
    st.set_page_config(layout="wide")
    st.title("TTS Dataset Visualization")
    # Sidebar form
    with st.sidebar:
        st.title("Dataset Submit Form")
        st.warning("WARNING  \nThis will overwrite the filelist. Please use a copy.")
        dataset_path = st.text_input(
            "Dataset path",
            "/path/to/dataset",
            help="Path to location of filelist and audio files",
        )
        dataset_path = os.path.expanduser(dataset_path)
        if os.path.exists(dataset_path):
            st.write(os.listdir(dataset_path))
        else:
            st.write(f"{dataset_path} does not exist!")
        filelist_path = st.text_input(
            "File list",
            "list-copy.txt",
            help="Name of the filelist local to dataset_path  \nWARNING: Submitting edits will overwrite this file",
        )
        # new_filelist = st.text_input("Edited file list location to save", "copy-edited.txt")
        delimiter = st.text_input("Delimiter", "|", help="Delimiter in the filelist")
        st.write("Indices below improve rendering speed for large datasets")
        index_start = st.number_input(
            label="Start index", help="Index of first row to render", step=0
        )
        index_end = st.number_input(
            label="End index", help="Index of last row to render", step=1, value=15
        )
        sort_order = st.selectbox("Sort order", ["index", "unknown_words"])

        st.title("Add to Arpabet dictionary")
        with st.expander("Path to arpabet dict"):
            cmu_dict_file = st.text_input("Arpabet dictionary path", value=CMU_DICT_FILE)
        grapheme = st.text_input(
            "Grapheme", help="Word that you are adding to the Arpabet dictionary"
        )
        default_arpabet = " ".join(g2p(grapheme)) if grapheme else ""
        arpabet = st.text_input("ARPAbet", help="ARBAbet transcription of the word", value=default_arpabet)
        if grapheme:
            lookup = g2p.check_lookup(grapheme)
            st.write("G2P check_lookup results:")
            st.write(lookup)
        add_to_dictionary = st.button("Add to dictionary")
        if add_to_dictionary:
            insert_word(grapheme, arpabet, cmu_dict_file)


        test_arpabet = st.button("Test arpabet 🗣")
        if test_arpabet:
            client = uberduck_client()
            audio_url = client.query(f"{{ {arpabet} }}")
            st.audio(audio_url)

    df = pd.read_csv(
        os.path.join(dataset_path, filelist_path), delimiter=delimiter, header=None
    )
    if sort_order == "unknown_words":
        df = df.iloc[df[1].map(lambda x: -len(g2p.check_lookup(x).get("RNN", []))).argsort(), :]

    for i, row in df[index_start:index_end].iterrows():
        row_n = st.container()
        with row_n:
            # Set up streamlit column width
            audio_col, transcription_col = st.columns((1.3, 3))
            # Get data from DF
            filename, transcription = row[0], row[1]
            transcription_lookups = g2p.check_lookup(transcription)
            audio_col.audio(os.path.join(dataset_path, filename))

            # CMU lookups (probably needs rework)
            with transcription_col:
                transcription_tuple = []
                prior_word = ""

                # Custom checks can be added here
                for word in transcription.split(" "):
                    cleaned_word = re.sub(r"[^a-zA-Z\-' ]", "", word).lower()

                    # CMU check
                    _cache = words_cache()
                    if cleaned_word not in _cache and cleaned_word in transcription_lookups.get("RNN", {}):
                        transcription_tuple.append((word + " ", "CMU", "#faa"))

                    # Repeated word check
                    elif cleaned_word == prior_word:
                        transcription_tuple.append((word + " ", "x2", "#fea"))

                    # All good
                    else:
                        transcription_tuple.append((word + " "))
                    prior_word = cleaned_word

                # Add data to annotated text type
                annotated_text(*transcription_tuple)

                # Edit functionality
                edit_box = st.checkbox("Edit", key=i)
                if edit_box:
                    edited_text = st.text_area(
                        "Editing text",
                        transcription,
                    )
                    if st.button("Submit", key=i):
                        row[1] = edited_text
                        df.to_csv(
                            os.path.join(dataset_path, filelist_path),
                            header=False,
                            sep="|",
                            index=False,
                        )
                        st.success(
                            "Successfully submitted!  \nUncheck the edit box to see results"
                        )

if __name__ == "__main__":
    run()
