import streamlit as st
from annotated_text import annotated_text
from g2p_en import G2p
import pandas as pd

import re
import os

st.set_page_config(layout="wide")
st.title("TTS Dataset Visualization")
g2p = G2p()

# Sidebar form
with st.sidebar.form(key="data_form"):
    st.title("Dataset Submit Form")
    st.warning("WARNING  \nThis will overwrite the filelist. Please use a copy.")
    dataset_path = st.text_input(
        "Dataset path",
        "/path/to/dataset",
        help="Path to location of filelist and audio files",
    )
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
    submit_dataset = st.form_submit_button(label="Visualize 🔎")

df = pd.read_csv(
    os.path.join(dataset_path, filelist_path), delimiter=delimiter, header=None
)

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
            transciption_tuple = []
            prior_word = ""

            # Custom checks can be added here
            for word in transcription.split(" "):
                cleaned_word = re.sub(r"[^a-zA-Z ]", "", word).lower()

                # CMU check
                if (
                    "RNN" in transcription_lookups.keys()
                    and cleaned_word in transcription_lookups["RNN"]
                ):
                    transciption_tuple.append((word + " ", "CMU", "#faa"))

                # Repeated word check
                elif cleaned_word == prior_word:
                    transciption_tuple.append((word + " ", "x2", "#fea"))

                # All good
                else:
                    transciption_tuple.append((word + " "))
                prior_word = cleaned_word

            # Add data to annotated text type
            annotated_text(*transciption_tuple)

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
