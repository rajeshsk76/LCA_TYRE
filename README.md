# LCA_TYRE

Open engineering LCI/LCA platform for end-of-life tyre pyrolysis, recovered carbon black, deashing and circular carbon accounting.

Domain target: https://lca.calvyx.com

Status: early engineering model. Not certified ISO 14040/14044 LCA or EPD yet.

Emission factors are editable placeholders unless verified and referenced.

Install:

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -e engine/opentyre_lca
    pip install -r requirements.txt

Run tests:

    python -m unittest discover tests -v

Run dashboard:

    streamlit run web/streamlit_app.py
