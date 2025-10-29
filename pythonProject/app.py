


from jamaibase import JamAI, types as t
PAT: str = "jamai_pat_28cb532b9f67358c9ff8e13755832fda8a404e2bec94bf90"
jamai = JamAI(token="", project_id="proj_23fa99cb91f349d5c0d046f5")
import os
import tempfile
from typing import Dict, List, Optional

import streamlit as st
import pandas as pd


PAT: str = "jamai_pat_28cb532b9f67358c9ff8e13755832fda8a404e2bec94bf90"
PROJECT_ID: str = "proj_23fa99cb91f349d5c0d046f5"

# Action Table identifier (ID/name exactly as it appears in Jamaibase UI)
ACTION_TABLE_NAME: str = "Receipt.s"

# Column IDs (synthetic placeholders; replace with your real column IDs)
# Input FILE column (marked Input in the Action Table)
INPUT_IMAGE_COL: str = "Receipt"

# Output columns (marked Output in the Action Table)
OUTPUT_COLUMNS: List[str] = [
    "Total",
    "Pretax",
    "Shop Name",
    "Tax",
    "Tips",
    "catagory"

    # add more as needed
]

# =========================
# 2) SDK CLIENT
# =========================
try:
    from jamaibase import JamAI, types as t
except Exception:
    raise RuntimeError(
        "Failed to import Jamaibase SDK. Install it with `pip install jamaibase`."
    )

@st.cache_resource(show_spinner=False)
def get_client(project_id: str, pat: str) -> JamAI:
    # Same construction pattern as in docs examples
    # (project_id + token), see PDFs.
    return JamAI(project_id=project_id, token=pat)

def validate_config() -> Optional[str]:
    if not PAT or PAT.startswith("REPLACE_"):
        return "Set a valid PAT at the top of app.py."
    if not PROJECT_ID or PROJECT_ID.startswith("REPLACE_"):
        return "Set a valid PROJECT_ID at the top of app.py."
    if not ACTION_TABLE_NAME or ACTION_TABLE_NAME.startswith("REPLACE_"):
        return "Set a valid ACTION_TABLE_NAME at the top of app.py."
    if not INPUT_IMAGE_COL or INPUT_IMAGE_COL.startswith("REPLACE_"):
        return "Set a valid INPUT_IMAGE_COL at the top of app.py."
    if not OUTPUT_COLUMNS or any(c.startswith("REPLACE_") for c in OUTPUT_COLUMNS):
        return "Set concrete OUTPUT_COLUMNS at the top of app.py."
    return None

def save_to_temp(uploaded_file) -> str:
    suffix = os.path.splitext(uploaded_file.name)[1].lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getvalue())
        return tmp.name

def process_image_file(client: JamAI, image_path: str) -> Dict[str, Optional[str]]:
    # ---- Upload file → returns URI (per docs) ----
    file_resp = client.file.upload_file(image_path)

    # ---- Add row to Action Table with the FILE input column ----
    # Matches the RowAddRequest + TableType.ACTION pattern from the PDFs.
    add_resp = client.table.add_table_rows(
        table_type=t.TableType.ACTION,
        request=t.RowAddRequest(
            table_id=ACTION_TABLE_NAME,
            data=[{INPUT_IMAGE_COL: file_resp.uri}],
            stream=False,  # simple synchronous processing
        ),
    )

    # ---- Read outputs by named columns (use .text commonly for str outputs) ----
    row = add_resp.rows[0]
    results: Dict[str, Optional[str]] = {}
    for col in OUTPUT_COLUMNS:
        cell = row.columns.get(col)
        results[col] = getattr(cell, "text", None) if cell is not None else None
    return results

# =========================
# 3) STREAMLIT UI
# =========================
st.set_page_config(
    page_title="Jamaibase Image Processor",
    page_icon="🧠",
    layout="centered",
)

st.title("🧠 Jamaibase — Image → Action Table")
st.caption("Upload image(s) → send to Action Table input (FILE) → retrieve output columns.")

with st.expander("Configuration (edit in app.py)", expanded=True):
    st.code(
        f"""PAT = "{PAT[:4] + '...' if PAT and not PAT.startswith('REPLACE_') else 'REPLACE_WITH_YOUR_PAT'}"
PROJECT_ID = "{PROJECT_ID}"
ACTION_TABLE_NAME = "{ACTION_TABLE_NAME}"
INPUT_IMAGE_COL = "{INPUT_IMAGE_COL}"
OUTPUT_COLUMNS = {OUTPUT_COLUMNS}""",
        language="python",
    )

# Validate config before continuing
err = validate_config()
if err:
    st.error(err)
    st.stop()

client = get_client(PROJECT_ID, PAT)

st.subheader("Upload images")
files = st.file_uploader(
    "Drag & drop or Browse",
    type=["png", "jpg", "jpeg", "webp", "gif"],
    accept_multiple_files=True,
    help="Multiple files are supported.",
)

clicked = st.button("Process Images", type="primary", disabled=(not files))
results_rows: List[Dict[str, Optional[str]]] = []

if clicked and files:
    status = st.empty()
    progress = st.progress(0, text="Starting…")

    for i, f in enumerate(files, start=1):
        status.info(f"Uploading {f.name} …")
        tmp = save_to_temp(f)
        try:
            status.info(f"Processing {f.name} …")
            outputs = process_image_file(client, tmp)

            row_dict = {"filename": f.name}
            for col in OUTPUT_COLUMNS:
                row_dict[col] = outputs.get(col)
            results_rows.append(row_dict)

        except Exception as e:
            results_rows.append(
                {"filename": f.name, **{col: f"ERROR: {e}" for col in OUTPUT_COLUMNS}}
            )
        finally:
            try:
                os.remove(tmp)
            except Exception:
                pass

        progress.progress(i / len(files), text=f"Processed {i}/{len(files)}")

    status.success("Done!")

    if results_rows:
        st.subheader("Results")
        df = pd.DataFrame(results_rows, columns=["filename"] + OUTPUT_COLUMNS)
        st.dataframe(df, use_container_width=True)

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download CSV",
            data=csv,
            file_name="jamaibase_action_table_results.csv",
            mime="text/csv",
        )

st.markdown("---")
st.caption(
    "Ensure your Action Table has: (1) a FILE Input column matching INPUT_IMAGE_COL, "
    "and (2) named Output columns listed in OUTPUT_COLUMNS. "
    "This app uses `file.upload_file(...)` → `table.add_table_rows(TableType.ACTION, RowAddRequest(...))` → "
    "reads `response.rows[0].columns['<Output>'].text`."
)
