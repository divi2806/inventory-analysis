# Deployment Guide

## Live App

Current deployed Streamlit dashboard:

```text
https://inventoryanalysis.streamlit.app/
```

If visitors are redirected to Streamlit authentication, update the app visibility/sharing settings in Streamlit Community Cloud before sharing the link with recruiters.

## Local Run

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Generate outputs:

```bash
python3 Python/advanced_inventory_analysis.py
```

Run dashboard:

```bash
streamlit run streamlit_app.py
```

Open:

```text
http://localhost:8501
```

## Streamlit Cloud Deployment

1. Push this repository to GitHub.
2. Go to `https://share.streamlit.io/`.
3. Sign in with GitHub.
4. Create a new app.
5. Select the repository.
6. Set branch to `main`.
7. Set main file path:

```text
streamlit_app.py
```

8. Deploy.

Streamlit Cloud will install dependencies from `requirements.txt`.

After deployment, add the live URL to `README.md`.
