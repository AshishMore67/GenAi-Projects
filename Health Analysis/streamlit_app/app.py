from dotenv import load_dotenv
import streamlit as st
import re
from langchain_google_genai import ChatGoogleGenerativeAI


def render_md(text: str) -> str:
    """Lightweight markdown-to-HTML converter (no external dependency,
    so bold/bullets always render instead of showing raw ** / -)."""
    if not text:
        return ""

    lines = text.strip().split("\n")
    html_lines = []
    in_list = False

    def inline(s: str) -> str:
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<em>\1</em>", s)
        return s

    for raw in lines:
        line = raw.strip()
        if not line:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            continue

        bullet_match = re.match(r"^[-*•]\s+(.*)", line)
        if bullet_match:
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{inline(bullet_match.group(1))}</li>")
            continue

        if in_list:
            html_lines.append("</ul>")
            in_list = False

        heading_match = re.match(r"^#{1,4}\s+(.*)", line)
        if heading_match:
            html_lines.append(f"<p><strong>{inline(heading_match.group(1))}</strong></p>")
            continue

        html_lines.append(f"<p>{inline(line)}</p>")

    if in_list:
        html_lines.append("</ul>")

    return "\n".join(html_lines)


load_dotenv()

st.set_page_config(
    page_title="Blood Work Analyzer",
    page_icon="🩸",
    layout="wide",
    initial_sidebar_state="expanded",
)

llm = ChatGoogleGenerativeAI(model="gemma-4-31b-it")

# ---------------------------------------------------------------- STYLES ---
st.markdown("""
<style>
:root {
    --accent: #ff4b6e;
    --accent-soft: rgba(255, 75, 110, 0.16);
    --bg: #121214;
    --card-bg: #1a1a1e;
    --card-bg-alt: #202024;
    --card-border: #2c2c33;
    --text-main: #f2f2f2;
    --text-dim: #a3a3ab;
}

/* force dark shell everywhere, regardless of the viewer's Streamlit theme */
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
    background-color: var(--bg) !important;
    color: var(--text-main) !important;
}
[data-testid="stSidebar"] {
    background-color: #17171a !important;
    color: var(--text-main) !important;
}
[data-testid="stSidebar"] * { color: var(--text-main) !important; }
[data-testid="stHeader"] { background-color: transparent !important; }

/* inputs */
.stTextArea textarea {
    background-color: var(--card-bg-alt) !important;
    color: var(--text-main) !important;
    border: 1px solid var(--card-border) !important;
}
.stTextArea textarea::placeholder { color: var(--text-dim) !important; opacity: 1; }

/* expander */
[data-testid="stExpander"] {
    background-color: var(--card-bg) !important;
    border: 1px solid var(--card-border) !important;
    border-radius: 10px;
}
[data-testid="stExpander"] summary, [data-testid="stExpander"] p { color: var(--text-main) !important; }

/* buttons */
.stButton button {
    border: 1px solid var(--card-border);
}

/* page padding */
.block-container { padding-top: 1.5rem; padding-bottom: 3rem; }

/* header */
.app-header {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 0.25rem;
}
.app-header h1 {
    font-size: 2.1rem;
    margin: 0;
    background: linear-gradient(90deg, #ff4b6e, #ff9a6e);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-weight: 800;
}
.app-subtitle {
    color: var(--text-dim);
    font-size: 0.95rem;
    margin-bottom: 1.5rem;
}

/* section label */
.section-label {
    font-size: 1.05rem;
    font-weight: 700;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--text-main);
}

/* scrollable result cards */
.scroll-box {
    height: 260px;
    overflow-y: auto;
    padding: 16px 18px;
    border: 1px solid var(--card-border);
    border-radius: 12px;
    background-color: var(--card-bg);
    font-size: 0.92rem;
    line-height: 1.7;
    box-shadow: 0 2px 8px rgba(0,0,0,0.25);
}
.scroll-box.empty {
    display: flex;
    align-items: center;
    justify-content: center;
    color: #5a5a62;
    font-style: italic;
}
.scroll-box p, .scroll-box li { color: #e0e0e0; }
.scroll-box ul, .scroll-box ol { padding-left: 1.2rem; }
.scroll-box strong { color: #ff9a6e; }

.scroll-box::-webkit-scrollbar { width: 6px; }
.scroll-box::-webkit-scrollbar-thumb { background: #3a3a42; border-radius: 4px; }

/* status badges */
.badge-row { display: flex; gap: 10px; margin-bottom: 14px; flex-wrap: wrap; }
.badge {
    padding: 4px 12px;
    border-radius: 999px;
    font-size: 0.8rem;
    font-weight: 600;
}
.badge-high { background: rgba(255, 75, 75, 0.15); color: #ff6b6b; border: 1px solid rgba(255,75,75,0.3); }
.badge-low  { background: rgba(255, 190, 60, 0.15); color: #ffbe3c; border: 1px solid rgba(255,190,60,0.3); }
.badge-normal { background: rgba(75, 200, 130, 0.15); color: #4bc882; border: 1px solid rgba(75,200,130,0.3); }

/* disclaimer */
.disclaimer {
    margin-top: 2rem;
    padding: 12px 16px;
    border-left: 3px solid var(--accent);
    background: var(--accent-soft);
    font-size: 0.82rem;
    color: #b8b8bf;
    border-radius: 6px;
}

textarea { font-family: 'SFMono-Regular', Consolas, monospace !important; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------- STATE ----
if "health_summary" not in st.session_state:
    st.session_state.health_summary = ""
if "diet_plan" not in st.session_state:
    st.session_state.diet_plan = ""
if "extracted_values" not in st.session_state:
    st.session_state.extracted_values = ""

SAMPLE_REPORT = """Hemoglobin: 11.2 g/dL (Ref: 13.0-17.0)
Fasting Glucose: 118 mg/dL (Ref: 70-100)
Total Cholesterol: 245 mg/dL (Ref: <200)
HDL: 38 mg/dL (Ref: >40)
LDL: 160 mg/dL (Ref: <100)
TSH: 3.1 uIU/mL (Ref: 0.4-4.0)
Vitamin D: 18 ng/mL (Ref: 30-100)"""

# ---------------------------------------------------------------- SIDEBAR --
with st.sidebar:
    st.markdown("### ℹ️ How it works")
    st.markdown(
        "1. Paste your blood work report\n"
        "2. Click **Analyze**\n"
        "3. Get a plain-language health summary\n"
        "4. Get an Indian-diet plan tailored to your results"
    )
    st.divider()
    if st.button("Load sample report", use_container_width=True):
        st.session_state["blood_report_input"] = SAMPLE_REPORT
        st.rerun()
    st.divider()
    st.caption("Your report is processed only for this session and is not stored.")

# ---------------------------------------------------------------- HEADER ---
st.markdown(
    '<div class="app-header"><h1>Blood Work Analyzer</h1></div>'
    '<div class="app-subtitle">AI-powered lab report analysis with a practical Indian diet plan</div>',
    unsafe_allow_html=True,
)

left_col, right_col = st.columns([1, 1], gap="large")

with left_col:
    st.markdown('<div class="section-label">📄 Blood Work Report</div>', unsafe_allow_html=True)
    blood_report = st.text_area(
        label="Paste your report below",
        height=430,
        placeholder="Paste your blood work report here...\ne.g. Hemoglobin: 11.2 g/dL (Ref: 13.0-17.0)",
        label_visibility="collapsed",
        key="blood_report_input",
    )
    analyze_clicked = st.button("🔍 Analyze", type="primary", use_container_width=True)

    with st.expander("🧪 Extracted lab values", expanded=False):
        if st.session_state.extracted_values:
            st.markdown(st.session_state.extracted_values)
        else:
            st.caption("Run an analysis to see extracted values here.")

with right_col:
    st.markdown('<div class="section-label">💡 Health Summary</div>', unsafe_allow_html=True)
    health_box = st.empty()

    st.markdown('<div class="section-label">🥗 Suggested Diet Plan</div>', unsafe_allow_html=True)
    diet_box = st.empty()


def render_box(box, content: str, empty_text: str):
    if content:
        box.markdown(f'<div class="scroll-box">{render_md(content)}</div>', unsafe_allow_html=True)
    else:
        box.markdown(f'<div class="scroll-box empty">{empty_text}</div>', unsafe_allow_html=True)


def count_badges(extracted: str) -> str:
    high = extracted.upper().count("HIGH")
    low = extracted.upper().count("LOW")
    normal = extracted.upper().count("NORMAL")
    return (
        '<div class="badge-row">'
        f'<span class="badge badge-high">{high} High</span>'
        f'<span class="badge badge-low">{low} Low</span>'
        f'<span class="badge badge-normal">{normal} Normal</span>'
        '</div>'
    )


render_box(health_box, st.session_state.health_summary, "Your health summary will appear here after analysis.")
render_box(diet_box, st.session_state.diet_plan, "Your diet plan will appear here after analysis.")

# ---------------------------------------------------------------- ACTION ---
if analyze_clicked:
    if not blood_report.strip():
        st.warning("⚠️ Please paste a blood work report before analyzing.")
    else:
        with st.status("Analyzing your blood work...", expanded=True) as status:
            st.write("Step 1/2 — Extracting and classifying lab values...")
            extraction_prompt = f"""
You are a medical data extraction assistant.

From the blood report below, extract ALL test values and classify each one as HIGH, LOW, or NORMAL
based on the reference ranges provided in the report.

Format your response as:
- Test Name: value | Status: HIGH/LOW/NORMAL | Reference: range

Blood Report:
{blood_report}
"""
            extraction_response = llm.invoke(extraction_prompt)
            extracted_values = extraction_response.text
            st.session_state.extracted_values = extracted_values

            st.write("Step 2/2 — Generating health summary and Indian diet plan...")
            diet_prompt = f"""
You are a clinical nutritionist specializing in Indian dietary habits.

Based on the blood work analysis below, provide two clearly separated sections:

SECTION 1 - HEALTH SUMMARY:
Write 4-5 lines explaining the patient's condition in simple, non-technical language.

SECTION 2 - INDIAN DIET PLAN:
List foods to eat more of and foods to avoid, using commonly available Indian foods
like dal, sabzi, roti, rice, etc. Keep it practical and concise.

Blood Work Analysis:
{extracted_values}
"""
            diet_response = llm.invoke(diet_prompt)
            full_response = diet_response.text
            status.update(label="Analysis complete", state="complete", expanded=False)

        if "SECTION 2" in full_response:
            parts = full_response.split("SECTION 2")
            health_summary = parts[0].replace("SECTION 1 - HEALTH SUMMARY:", "").replace("SECTION 1", "").strip()
            diet_plan = ("SECTION 2" + parts[1]).replace("SECTION 2 - INDIAN DIET PLAN:", "").replace("SECTION 2", "").strip()
        else:
            health_summary = full_response
            diet_plan = ""

        st.session_state.health_summary = health_summary
        st.session_state.diet_plan = diet_plan if diet_plan else full_response

        st.rerun()

st.markdown(
    '<div class="disclaimer">⚕️ This tool provides general informational summaries only and is '
    'not a substitute for professional medical advice. Please consult a doctor or registered '
    'dietitian before making any health or dietary decisions.</div>',
    unsafe_allow_html=True,
)